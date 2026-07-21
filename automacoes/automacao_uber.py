import logging
import os
import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Optional

import structlog
from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver import Remote as AppiumDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from automacoes.base import BaseAutomacao
from debug_coleta import obter as obter_debug
from modelos.corrida import Corrida, MetricasCorrida

logger = structlog.get_logger("automacao.uber")


class AutomacaoUber(BaseAutomacao):
    CATEGORIAS_PERMITIDAS = {"uberx", "moto", "comfort", "prioridade"}

    def __init__(self, config_appium: dict[str, str]):
        self.server = config_appium['server']
        self.app_package = config_appium['app_package']
        self.driver: Optional[AppiumDriver] = None
        self.wait: Optional[WebDriverWait] = None

    def conectar(self) -> None:
        options = UiAutomator2Options()
        options.platform_name = 'Android'
        options.automation_name = 'UiAutomator2'
        options.app_package = self.app_package
        options.app_wait_duration = 60000
        options.no_reset = True
        options.set_capability('appWaitForLaunch', False)

        logger.info("Conectando ao Appium Server")
        self.driver = webdriver.Remote(self.server, options=options)
        self.device_model = self.driver.capabilities.get('deviceModel', 'desconhecido')
        logger.info("Dispositivo conectado", device_model=self.device_model)
        self.wait = WebDriverWait(self.driver, 20)

        logger.info("Aguardando app carregar")
        try:
            self.wait.until(
                EC.presence_of_element_located((By.XPATH, "//*[@content-desc='Para onde?']"))
            )
        except Exception:
            logger.warning("App não abriu, tentando abrir manualmente")
            self.driver.activate_app(self.app_package)
            self.wait.until(
                EC.presence_of_element_located((By.XPATH, "//*[@content-desc='Para onde?']"))
            )

    def coletar_precos(self, destino: str, origem: str = "") -> List[Corrida]:
        assert self.driver is not None
        assert self.wait is not None

        botao = self.wait.until(
            EC.element_to_be_clickable((By.XPATH, "//*[@content-desc='Para onde?']"))
        )
        botao.click()

        container_origem = "com.ubercab:id/ub__location_edit_search_container_pickup"
        container_destino = "com.ubercab:id/ub__location_edit_search_container_destination"

        if origem:
            origem = self._preencher_campo(origem, container_origem)

        time.sleep(0.5)

        destino = self._preencher_campo(destino, container_destino)

        time.sleep(1)

        try:
            self.wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, "//*[contains(@content-desc,'Preço:')]")
                )
            )
        except Exception:
            logger.debug("Timeout esperando preço")
            try:
                page_source = self.driver.page_source
                if "Nenhuma viagem disponível" in page_source:
                    logger.info("Nenhuma viagem disponível no Uber. Ignorando esta coleta.")
                    return []
            except Exception as e:
                logger.debug("Erro ao verificar mensagem de nenhuma viagem disponível", erro=str(e))

        categorias_para_extrair = {}
        resultados = []

        def _parse_opcoes(categorias_para_extrair, resultados):
            page_source = self.driver.page_source
            root = ET.fromstring(page_source)

            for elem in root.iter():
                content_desc = elem.get('content-desc', '')
                if 'Preço:' not in content_desc:
                    continue

                try:
                    partes = content_desc.split("!")

                    categoria = None
                    for i, parte in enumerate(partes):
                        parte_lower = parte.lower().strip()
                        if parte_lower in self.CATEGORIAS_PERMITIDAS:
                            categoria = parte.strip()
                            break
                        if "selecionado" in parte_lower:
                            if i + 1 < len(partes):
                                categoria = partes[i + 1].strip()
                                break

                    if not categoria or categoria.lower() not in self.CATEGORIAS_PERMITIDAS:
                        continue

                    if categoria.lower() in categorias_para_extrair:
                        continue

                    preco_str = ""
                    for parte in partes:
                        if "Desconto de" in parte:
                            preco_str = parte.replace("Desconto de", "").replace("R$", "").strip()
                            break
                        elif "Preço:" in parte:
                            preco_str = parte.replace("Preço:", "").replace("R$", "").strip()

                    if not preco_str:
                        continue

                    preco = float(preco_str.replace(".", "").replace(",", "."))

                    estimativa_min = 0
                    for parte in partes:
                        match = re.search(r'está a (\d+) minuto', parte)
                        if match:
                            estimativa_min = int(match.group(1))
                            break

                    resultados.append(Corrida(
                        app="uber",
                        categoria=categoria,
                        preco=preco,
                        estimativa=estimativa_min,
                        origem=origem,
                        destino=destino,
                        timestamp=datetime.now(),
                    ))
                    categorias_para_extrair[categoria.lower()] = content_desc
                except Exception as e:
                    logger.debug("Erro parse preço", exc_info=True)
                    continue

        _parse_opcoes(categorias_para_extrair, resultados)

        if len(categorias_para_extrair) < len(self.CATEGORIAS_PERMITIDAS):
            for _scroll in range(1):
                self._scroll_lista_opcoes()
                _parse_opcoes(categorias_para_extrair, resultados)
                if len(categorias_para_extrair) >= len(self.CATEGORIAS_PERMITIDAS):
                    break

        return resultados

    def coletar_metricas(self, corridas: List[Corrida]) -> List[Corrida]:
        assert self.driver is not None
        assert self.wait is not None

        log = obter_debug()

        def _log(msg):
            if log:
                log.debug(msg)

        _log("=== INICIO coletar_metricas ===")
        t_total = time.time()

        # Processar apenas as categorias visiveis no momento.
        # Se alguma categoria permitida nao estiver na tela, sera salva sem metricas.
        categorias_para_extrair = {}
        self._parse_categorias_visiveis(categorias_para_extrair)
        _log(f"Categorias visiveis: {list(categorias_para_extrair.keys())}")

        categorias_processadas = set()

        for nome_categoria in list(categorias_para_extrair.keys()):
            if nome_categoria in categorias_processadas:
                continue

            t_categoria = time.time()
            _log(f"--- Categoria: {nome_categoria} ---")

            try:
                info = categorias_para_extrair[nome_categoria]
                nome_original = info["nome_original"]
                ja_selecionado = info["content_desc"].lower().startswith("selecionado")
                _log(f"Ja selecionado: {ja_selecionado}")

                # XPath direto usando nome original (ex: "UberX", nao "uberx")
                xpath_categoria = f".//*[contains(@content-desc,'!{nome_original}!')]"
                xpath_pai = f"//*[@clickable='true' and {xpath_categoria}]"

                t0 = time.time()
                el_pai = None
                try:
                    el_pai = self.driver.find_element(By.XPATH, xpath_pai)
                except Exception:
                    # Fallback: tentar sem o "!" delimitador
                    xpath_pai_fallback = f"//*[@clickable='true' and .//*[contains(@content-desc,'{nome_original}')]]"
                    try:
                        el_pai = self.driver.find_element(By.XPATH, xpath_pai_fallback)
                    except Exception:
                        _log(f"Elemento nao encontrado para {nome_categoria}")
                        continue
                _log(f"find_element (xpath direto): {time.time()-t0:.2f}s")

                if not ja_selecionado:
                    t0 = time.time()
                    _log(f"Clicando para selecionar (clique 1)...")
                    el_pai.click()
                    try:
                        WebDriverWait(self.driver, 3).until(
                            EC.staleness_of(el_pai)
                        )
                    except Exception:
                        pass
                    _log(f"Clique 1 (selecionar): {time.time()-t0:.2f}s")

                    # Re-encontrar apos mudanca de estado
                    t0 = time.time()
                    try:
                        el_pai = self.driver.find_element(By.XPATH, xpath_pai)
                    except Exception:
                        try:
                            el_pai = self.driver.find_element(By.XPATH, xpath_pai_fallback)
                        except Exception:
                            _log(f"Elemento nao encontrado apos clique 1")
                            continue
                    _log(f"Re-find apos clique 1: {time.time()-t0:.2f}s")

                t0 = time.time()
                _log(f"Clicando para detalhes (clique 2)...")
                el_pai.click()
                try:
                    WebDriverWait(self.driver, 3).until(
                        EC.presence_of_element_located(
                            (By.XPATH, "//*[contains(@content-desc,'capacidade estimada')]")
                        )
                    )
                except Exception:
                    logger.debug("Timeout capacidade estimada")
                _log(f"Clique 2 (detalhes): {time.time()-t0:.2f}s")

                # Passo 3: Abrir tela de metricas (clicar no card com "capacidade estimada")
                t0 = time.time()
                card_xpath = (
                    "//com.uber.rib.core.compose.root.UberComposeView"
                    "//*[contains(@content-desc,'capacidade estimada')]"
                    "//*[@clickable='true']"
                )
                try:
                    card_view = WebDriverWait(self.driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, card_xpath))
                    )
                    _log("Card view encontrado, clicando...")
                    card_view.click()
                    try:
                        WebDriverWait(self.driver, 5).until(
                            EC.presence_of_element_located(
                                (By.XPATH, "//*[@resource-id='com.ubercab:id/line_items_container']")
                            )
                        )
                        _log("line_items_container encontrado")
                    except Exception:
                        _log("Timeout line_items_container, verificando title_text...")
                        try:
                            self.driver.find_element(
                                By.XPATH, "//*[@resource-id='com.ubercab:id/title_text']"
                            )
                            _log("Elementos de metricas encontrados via title_text")
                        except Exception:
                            _log("Nenhum elemento de metricas encontrado")
                    _log(f"Clique 3 (card_view): {time.time()-t0:.2f}s")
                except Exception as e:
                    _log(f"Card view NAO encontrado/clicavel: {e}")
                    logger.debug("Card view não encontrado")

                t0 = time.time()
                campos = self._extrair_detalhamento_preco()
                _log(f"Extrair metricas: {campos}, {time.time()-t0:.2f}s")

                # Atribuir metricas ao objeto Corrida (mesmo parciais, antes de voltar)
                if campos:
                    for corrida in corridas:
                        if (
                            corrida.categoria.lower() == nome_categoria.lower()
                            and corrida.app == "uber"
                        ):
                            corrida.metricas = MetricasCorrida(
                                preco_base=campos.get("preco_base"),
                                preco_minimo=campos.get("preco_minimo"),
                                adicional_por_minuto=campos.get("adicional_por_minuto"),
                                adicional_por_km=campos.get("adicional_por_km"),
                                custo_fixo=campos.get("custo_fixo"),
                            )
                            _log(f"Metricas atribuidas a {corrida.categoria}: {list(campos.keys())}")
                            break
                else:
                    _log("Nenhuma metrica extraida para esta categoria")

                # Voltar da tela de metricas para a lista (state-aware, sem activate_app)
                t0 = time.time()
                _log("Voltando para lista...")

                for tentativa in range(2):
                    tela = self._tela_atual()
                    _log(f"Tentativa {tentativa+1}: tela={tela}")

                    if tela == "lista":
                        break

                    try:
                        self.driver.back()
                    except Exception:
                        _log("driver.back() falhou")
                        break
                    time.sleep(1.5)

                tela_final = self._tela_atual()
                if tela_final != "lista":
                    _log(f"Tela final nao e lista ({tela_final}); seguindo para proxima categoria")
                else:
                    _log("Lista encontrada")

                _log(f"Voltar total: {time.time()-t0:.2f}s")

                categorias_processadas.add(nome_categoria)
                _log(f"--- FIM {nome_categoria}: {time.time()-t_categoria:.2f}s ---")
            except Exception as e:
                _log(f"ERRO na categoria {nome_categoria}: {e}")
                logger.error("Erro ao capturar métricas", categoria=nome_categoria, erro=str(e), exc_info=True)
                try:
                    self.driver.back()
                except Exception:
                    pass
                continue

        # Apos processar visiveis, fazer 1 scroll para revelar novas categorias
        pendentes = self._categorias_pendentes(categorias_processadas)
        if pendentes:
            _log(f"Categorias pendentes: {sorted(pendentes)}; fazendo scroll...")
            self._scroll_lista_opcoes()
            time.sleep(1.0)

            categorias_para_extrair = {}
            self._parse_categorias_visiveis(categorias_para_extrair)
            _log(f"Apos scroll, categorias visiveis: {list(categorias_para_extrair.keys())}")

            for nome_categoria in list(categorias_para_extrair.keys()):
                if nome_categoria in categorias_processadas:
                    continue

                t_categoria = time.time()
                _log(f"--- Categoria: {nome_categoria} (pos-scroll) ---")

                try:
                    info = categorias_para_extrair[nome_categoria]
                    nome_original = info["nome_original"]
                    ja_selecionado = info["content_desc"].lower().startswith("selecionado")
                    _log(f"Ja selecionado: {ja_selecionado}")

                    xpath_categoria = f".//*[contains(@content-desc,'!{nome_original}!')]"
                    xpath_pai = f"//*[@clickable='true' and {xpath_categoria}]"

                    t0 = time.time()
                    el_pai = None
                    try:
                        el_pai = self.driver.find_element(By.XPATH, xpath_pai)
                    except Exception:
                        xpath_pai_fallback = f"//*[@clickable='true' and .//*[contains(@content-desc,'{nome_original}')]]"
                        try:
                            el_pai = self.driver.find_element(By.XPATH, xpath_pai_fallback)
                        except Exception:
                            _log(f"Elemento nao encontrado para {nome_categoria}")
                            continue
                    _log(f"find_element: {time.time()-t0:.2f}s")

                    if not ja_selecionado:
                        t0 = time.time()
                        el_pai.click()
                        try:
                            WebDriverWait(self.driver, 3).until(EC.staleness_of(el_pai))
                        except Exception:
                            pass
                        _log(f"Clique 1: {time.time()-t0:.2f}s")

                        t0 = time.time()
                        try:
                            el_pai = self.driver.find_element(By.XPATH, xpath_pai)
                        except Exception:
                            try:
                                el_pai = self.driver.find_element(By.XPATH, xpath_pai_fallback)
                            except Exception:
                                _log("Elemento nao encontrado apos clique 1")
                                continue
                        _log(f"Re-find: {time.time()-t0:.2f}s")

                    t0 = time.time()
                    el_pai.click()
                    try:
                        WebDriverWait(self.driver, 3).until(
                            EC.presence_of_element_located(
                                (By.XPATH, "//*[contains(@content-desc,'capacidade estimada')]")
                            )
                        )
                    except Exception:
                        logger.debug("Timeout capacidade estimada")
                    _log(f"Clique 2: {time.time()-t0:.2f}s")

                    t0 = time.time()
                    card_xpath = (
                        "//com.uber.rib.core.compose.root.UberComposeView"
                        "//*[contains(@content-desc,'capacidade estimada')]"
                        "//*[@clickable='true']"
                    )
                    try:
                        card_view = WebDriverWait(self.driver, 5).until(
                            EC.element_to_be_clickable((By.XPATH, card_xpath))
                        )
                        _log("Card view encontrado, clicando...")
                        card_view.click()
                        try:
                            WebDriverWait(self.driver, 5).until(
                                EC.presence_of_element_located(
                                    (By.XPATH, "//*[@resource-id='com.ubercab:id/line_items_container']")
                                )
                            )
                        except Exception:
                            _log("Timeout line_items_container")
                        _log(f"Clique 3: {time.time()-t0:.2f}s")
                    except Exception as e:
                        _log(f"Card view NAO encontrado: {e}")

                    t0 = time.time()
                    campos = self._extrair_detalhamento_preco()
                    _log(f"Extrair metricas: {campos}, {time.time()-t0:.2f}s")

                    if campos:
                        for corrida in corridas:
                            if (
                                corrida.categoria.lower() == nome_categoria.lower()
                                and corrida.app == "uber"
                            ):
                                corrida.metricas = MetricasCorrida(
                                    preco_base=campos.get("preco_base"),
                                    preco_minimo=campos.get("preco_minimo"),
                                    adicional_por_minuto=campos.get("adicional_por_minuto"),
                                    adicional_por_km=campos.get("adicional_por_km"),
                                    custo_fixo=campos.get("custo_fixo"),
                                )
                                _log(f"Metricas atribuidas a {corrida.categoria}: {list(campos.keys())}")
                                break
                    else:
                        _log("Nenhuma metrica extraida")

                    t0 = time.time()
                    _log("Voltando para lista...")
                    for tentativa in range(2):
                        tela = self._tela_atual()
                        _log(f"Tentativa {tentativa+1}: tela={tela}")
                        if tela == "lista":
                            break
                        try:
                            self.driver.back()
                        except Exception:
                            _log("driver.back() falhou")
                            break
                        time.sleep(1.5)

                    tela_final = self._tela_atual()
                    _log(f"Tela final: {tela_final}; voltar: {time.time()-t0:.2f}s")

                    categorias_processadas.add(nome_categoria)
                    _log(f"--- FIM {nome_categoria}: {time.time()-t_categoria:.2f}s ---")
                except Exception as e:
                    _log(f"ERRO na categoria {nome_categoria}: {e}")
                    logger.error("Erro ao capturar métricas", categoria=nome_categoria, erro=str(e), exc_info=True)
                    try:
                        self.driver.back()
                    except Exception:
                        pass
                    continue

        # Logar categorias permitidas que ficaram sem metricas
        nao_visiveis = self._categorias_pendentes(categorias_processadas)
        if nao_visiveis:
            _log(f"Categorias sem metricas extraidas (nao visiveis): {sorted(nao_visiveis)}")

        _log(f"=== FIM coletar_metricas: {time.time()-t_total:.2f}s ===")

        return corridas

    def _preencher_campo(self, endereco: str, container_id: str) -> str:
        assert self.driver is not None
        assert self.wait is not None

        log = obter_debug()
        if log:
            log.debug("Preenchendo campo  container_id=%s  endereco=%s", container_id, endereco)

        container = self.wait.until(
            EC.element_to_be_clickable((By.ID, container_id))
        )
        if log:
            log.debug("Clicando container  container_id=%s", container_id)
        container.click()

        campo_texto = self.wait.until(
            EC.presence_of_element_located((By.ID, "com.ubercab:id/edit_text"))
        )
        if log:
            log.debug("edit_text encontrado, enviando endereco")
        time.sleep(0.3)
        campo_texto.clear()
        campo_texto.send_keys(endereco)

        if log:
            log.debug("Aguardando ub__text_search_v2_results")
        container_resultados = self.wait.until(
            EC.presence_of_element_located((By.ID, "com.ubercab:id/ub__text_search_v2_results"))
        )
        if log:
            log.debug("ub__text_search_v2_results encontrado, clicando primeiro resultado")

        selecionado = endereco
        for tentativa in range(3):
            try:
                primeiro_resultado = container_resultados.find_element(
                    By.XPATH, ".//android.widget.Button[@content-desc]"
                )
                selecionado = primeiro_resultado.get_attribute("content-desc") or endereco
                if log:
                    log.debug("Clicando resultado  selecionado=%s", selecionado[:60])
                primeiro_resultado.click()
                break
            except Exception as e:
                if log:
                    log.debug("Falha ao selecionar resultado  tentativa=%d  erro=%s", tentativa + 1, str(e)[:80])
                time.sleep(0.5)

        return selecionado

    def _scroll_lista_opcoes(self, para_cima: bool = False) -> None:
        assert self.driver is not None

        size = self.driver.get_window_size()
        width = size['width']
        height = size['height']

        start_y = int(height * 0.8) if not para_cima else int(height * 0.4)
        end_y = int(height * 0.4) if not para_cima else int(height * 0.8)
        start_x = width // 2

        self.driver.swipe(start_x, start_y, start_x, end_y, 800)

    def _elemento_visivel(self, xpath: str) -> bool:
        """Verifica se um elemento está visível na tela."""
        assert self.driver is not None
        try:
            elementos = self.driver.find_elements(By.XPATH, xpath)
            return len(elementos) > 0
        except Exception:
            return False

    def _parse_categorias_visiveis(self, categorias_para_extrair: dict) -> None:
        """Varre o page_source atual e adiciona categorias permitidas ao dicionario."""
        assert self.driver is not None
        page_source = self.driver.page_source
        root = ET.fromstring(page_source)

        for elem in root.iter():
            content_desc = elem.get('content-desc', '')
            if 'Preço:' not in content_desc:
                continue
            partes = content_desc.split("!")
            for i, parte in enumerate(partes):
                parte_lower = parte.lower().strip()
                if parte_lower in self.CATEGORIAS_PERMITIDAS:
                    if parte_lower not in categorias_para_extrair:
                        categorias_para_extrair[parte_lower] = {
                            "content_desc": content_desc,
                            "nome_original": parte.strip(),
                        }
                    break
                if "selecionado" in parte_lower and i + 1 < len(partes):
                    cat_lower = partes[i + 1].strip().lower()
                    if cat_lower in self.CATEGORIAS_PERMITIDAS and cat_lower not in categorias_para_extrair:
                        categorias_para_extrair[cat_lower] = {
                            "content_desc": content_desc,
                            "nome_original": partes[i + 1].strip(),
                        }
                    break

    def _categorias_pendentes(self, categorias_processadas: set) -> set:
        """Retorna as categorias permitidas que ainda nao foram detalhadas."""
        return self.CATEGORIAS_PERMITIDAS - categorias_processadas

    def _tela_atual(self) -> str:
        """Identifica a tela atual baseado no page_source."""
        assert self.driver is not None
        try:
            page_source = self.driver.page_source
            if "line_items_container" in page_source:
                return "metricas"
            if "capacidade estimada" in page_source:
                return "detalhes"
            if "Preço:" in page_source:
                return "lista"
            return "desconhecida"
        except Exception:
            return "erro"

    def _extrair_detalhamento_preco(self) -> dict:
        assert self.driver is not None

        log = obter_debug()
        campos = {}

        try:
            grupos = self.driver.find_elements(
                By.XPATH,
                "//*[@resource-id='com.ubercab:id/line_items_container']"
                "/android.view.ViewGroup",
            )
            if log:
                log.debug("  _extrair: %d grupos encontrados em line_items_container", len(grupos))
            for grupo in grupos:
                try:
                    title_elem = grupo.find_element(
                        By.XPATH,
                        ".//*[@resource-id='com.ubercab:id/title_text']",
                    )
                    value_elem = grupo.find_element(
                        By.XPATH,
                        ".//*[@resource-id='com.ubercab:id/primary_end_text']",
                    )
                    title = title_elem.text.strip()
                    value_text = (
                        value_elem.text.strip()
                        .replace("R$", "")
                        .replace(".", "")
                        .replace(",", ".")
                        .strip()
                    )
                    valor = float(value_text)

                    if log:
                        log.debug("  _extrair: campo='%s' valor=%s", title, valor)

                    title_lower = title.lower()
                    if "preço base" in title_lower or "preco base" in title_lower:
                        campos["preco_base"] = valor
                    elif (
                        "preço mínimo" in title_lower
                        or "preco minimo" in title_lower
                    ):
                        campos["preco_minimo"] = valor
                    elif "por minuto" in title_lower:
                        campos["adicional_por_minuto"] = valor
                    elif (
                        "por quilômetro" in title_lower
                        or "por quilometro" in title_lower
                    ):
                        campos["adicional_por_km"] = valor
                    elif "custo fixo" in title_lower:
                        campos["custo_fixo"] = valor
                except Exception as e:
                    if log:
                        log.debug("  _extrair: erro parse grupo: %s", e)
                    continue
        except Exception as e:
            if log:
                log.debug("  _extrair: line_items_container nao encontrado: %s", e)

        return campos

    def voltar_tela_inicial(self) -> None:
        assert self.driver is not None

        for tentativa in range(4):
            self.driver.back()
            time.sleep(1)

            elementos_home = self.driver.find_elements(
                By.XPATH, "//*[@content-desc='Para onde?']"
            )
            if len(elementos_home) > 0:
                return

    def desconectar(self) -> None:
        if self.driver:
            self.driver.terminate_app(self.app_package)
            self.driver.quit()
