import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from typing import List, Optional

from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver import Remote as AppiumDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from automacoes.base import BaseAutomacao
from modelos.corrida import Corrida, MetricasCorrida


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
        options.app_wait_duration = 30000
        options.no_reset = True
        options.set_capability('appWaitForLaunch', False)

        self.driver = webdriver.Remote(self.server, options=options)
        self.device_model = self.driver.capabilities.get('deviceModel', 'desconhecido')
        self.wait = WebDriverWait(self.driver, 10)

        try:
            self.wait.until(
                EC.presence_of_element_located((By.XPATH, "//*[@content-desc='Para onde?']"))
            )
        except Exception:
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

        if origem:
            origem = self._preencher_campo(
                origem, "com.ubercab:id/ub__location_edit_search_container_pickup"
            )

        time.sleep(1)

        destino = self._preencher_campo(
            destino, "com.ubercab:id/edit_text"
        )

        time.sleep(2)

        try:
            self.wait.until(
                EC.presence_of_element_located(
                    (By.XPATH, "//*[contains(@content-desc,'Preço:')]")
                )
            )
        except Exception:
            pass

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
                except Exception:
                    continue

        _parse_opcoes(categorias_para_extrair, resultados)

        if len(categorias_para_extrair) < len(self.CATEGORIAS_PERMITIDAS):
            for _scroll in range(3):
                self._scroll_lista_opcoes()
                _parse_opcoes(categorias_para_extrair, resultados)
                if len(categorias_para_extrair) >= len(self.CATEGORIAS_PERMITIDAS):
                    break

        return resultados

    def coletar_metricas(self, corridas: List[Corrida]) -> List[Corrida]:
        assert self.driver is not None
        assert self.wait is not None

        page_source = self.driver.page_source
        root = ET.fromstring(page_source)

        categorias_para_extrair = {}
        for elem in root.iter():
            content_desc = elem.get('content-desc', '')
            if 'Preço:' not in content_desc:
                continue
            partes = content_desc.split("!")
            for i, parte in enumerate(partes):
                parte_lower = parte.lower().strip()
                if parte_lower in self.CATEGORIAS_PERMITIDAS:
                    categorias_para_extrair[parte_lower] = content_desc
                    break
                if "selecionado" in parte_lower and i + 1 < len(partes):
                    categorias_para_extrair[partes[i + 1].strip().lower()] = content_desc
                    break

        categorias_processadas = set()

        for nome_categoria in list(categorias_para_extrair.keys()):
            if nome_categoria in categorias_processadas:
                continue

            try:
                ja_selecionado = categorias_para_extrair[nome_categoria].lower().startswith("selecionado")

                if not ja_selecionado:
                    todos_elementos = self.driver.find_elements(
                        By.XPATH,
                        "//*[@clickable='true' and .//*[contains(@content-desc,'Preço:')]]"
                    )
                    for el in todos_elementos:
                        try:
                            child = el.find_element(By.XPATH, ".//*[contains(@content-desc,'Preço:')]")
                            desc = child.get_attribute("content-desc").lower()
                            if f"!{nome_categoria}!" in desc or desc.startswith(nome_categoria):
                                el.click()
                                try:
                                    self.wait.until(
                                        EC.presence_of_element_located(
                                            (By.XPATH,
                                             "//*[@clickable='true' and .//*[contains(@content-desc,'Preço:')]]")
                                        )
                                    )
                                except Exception:
                                    time.sleep(1)
                                break
                        except Exception:
                            continue

                todos_elementos = self.driver.find_elements(
                    By.XPATH,
                    "//*[@clickable='true' and .//*[contains(@content-desc,'Preço:')]]"
                )
                for el in todos_elementos:
                    try:
                        child = el.find_element(By.XPATH, ".//*[contains(@content-desc,'Preço:')]")
                        desc = child.get_attribute("content-desc").lower()
                        if f"!{nome_categoria}!" in desc or desc.startswith(nome_categoria):
                            el.click()
                            try:
                                WebDriverWait(self.driver, 5).until(
                                    EC.presence_of_element_located(
                                        (By.XPATH,
                                         "//*[contains(@content-desc,'capacidade estimada')]")
                                    )
                                )
                            except Exception:
                                time.sleep(1)
                            break
                    except Exception:
                        continue

                try:
                    card_view = self.driver.find_element(
                        By.XPATH,
                        "//com.uber.rib.core.compose.root.UberComposeView"
                        "//*[contains(@content-desc,'Preço:') "
                        "and contains(@content-desc,'capacidade estimada')]"
                    )
                    try:
                        clickable = card_view.find_element(
                            By.XPATH, ".//*[@clickable='true']"
                        )
                        clickable.click()
                        try:
                            WebDriverWait(self.driver, 5).until(
                                EC.presence_of_element_located(
                                    (By.XPATH,
                                     "//*[@resource-id='com.ubercab:id/line_items_container']")
                                )
                            )
                        except Exception:
                            time.sleep(1)
                    except Exception:
                        try:
                            card_view.click()
                            try:
                                WebDriverWait(self.driver, 5).until(
                                    EC.presence_of_element_located(
                                        (By.XPATH,
                                         "//*[@resource-id='com.ubercab:id/line_items_container']")
                                    )
                                )
                            except Exception:
                                time.sleep(1)
                        except Exception:
                            pass
                except Exception:
                    pass

                campos = self._extrair_detalhamento_preco()
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
                            break

                try:
                    voltar = self.driver.find_element(
                        By.XPATH, "//*[@content-desc='Voltar']"
                    )
                    voltar.click()
                except Exception:
                    pass

                self.driver.back()
                time.sleep(1)

                self._scroll_lista_opcoes()

                try:
                    self.wait.until(
                        EC.presence_of_element_located(
                            (By.XPATH,
                             "//*[@clickable='true' and .//*[contains(@content-desc,'Preço:')]]")
                        )
                    )
                except Exception:
                    self.driver.activate_app(self.app_package)
                    time.sleep(1)
                    try:
                        self.wait.until(
                            EC.presence_of_element_located(
                                (By.XPATH,
                                 "//*[@clickable='true' and .//*[contains(@content-desc,'Preço:')]]")
                            )
                        )
                    except Exception:
                        break

                categorias_processadas.add(nome_categoria)
            except Exception as e:
                print(f"Erro ao capturar {nome_categoria}: {e}")
                try:
                    self.driver.back()
                    time.sleep(1)
                except Exception:
                    pass
                continue

        return corridas

    def _preencher_campo(self, endereco: str, container_id: str) -> str:
        assert self.driver is not None
        assert self.wait is not None

        container = self.wait.until(
            EC.element_to_be_clickable((By.ID, container_id))
        )
        container.click()
        time.sleep(0.5)

        campo_texto = self.driver.find_element(By.ID, "com.ubercab:id/edit_text")
        campo_texto.clear()
        campo_texto.send_keys(endereco)

        container_resultados = self.wait.until(
            EC.presence_of_element_located((By.ID, "com.ubercab:id/ub__text_search_v2_results"))
        )

        selecionado = endereco
        for tentativa in range(3):
            try:
                primeiro_resultado = container_resultados.find_element(
                    By.XPATH, ".//android.widget.Button[@content-desc]"
                )
                selecionado = primeiro_resultado.get_attribute("content-desc") or endereco
                primeiro_resultado.click()
                break
            except Exception:
                time.sleep(0.5)

        return selecionado

    def _scroll_lista_opcoes(self) -> None:
        assert self.driver is not None

        self.driver.swipe(360, 900, 360, 400, 800)

    def _extrair_detalhamento_preco(self) -> dict:
        assert self.driver is not None

        campos = {}

        try:
            grupos = self.driver.find_elements(
                By.XPATH,
                "//*[@resource-id='com.ubercab:id/line_items_container']"
                "/android.view.ViewGroup",
            )
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
                except Exception:
                    continue
        except Exception:
            pass

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
