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
from modelos.corrida import Corrida

logger = structlog.get_logger("automacao.99")


class Automacao99(BaseAutomacao):
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

        log = obter_debug()
        if log:
            log.debug("=== INICIO conectar 99 ===")

        logger.info("Conectando ao Appium Server")
        self.driver = webdriver.Remote(self.server, options=options)
        self.device_model = self.driver.capabilities.get('deviceModel', 'desconhecido')
        logger.info("Dispositivo conectado", device_model=self.device_model)
        self.wait = WebDriverWait(self.driver, 20)

        logger.info("Aguardando app carregar")
        try:
            self.wait.until(
                EC.presence_of_element_located((By.ID, "com.taxis99:id/oc_home_where_to_tv"))
            )
        except Exception:
            logger.warning("App não abriu, tentando abrir manualmente")
            self.driver.activate_app(self.app_package)
            self.wait.until(
                EC.presence_of_element_located((By.ID, "com.taxis99:id/oc_home_where_to_tv"))
            )

        if log:
            log.debug("=== FIM conectar 99 ===")

    def coletar_precos(self, destino: str, origem: str = "") -> List[Corrida]:
        assert self.driver is not None
        assert self.wait is not None

        log = obter_debug()
        if log:
            log.debug("=== INICIO coletar_precos 99 ===  origem=%s  destino=%s", origem, destino)

        botao = self.wait.until(
            EC.element_to_be_clickable((By.ID, "com.taxis99:id/oc_home_where_to_tv"))
        )
        botao.click()

        self.wait.until(
            EC.presence_of_element_located((By.ID, "com.taxis99:id/input_shadow"))
        )

        if origem:
            campo_origem = self.wait.until(
                EC.element_to_be_clickable((By.ID, "com.taxis99:id/et_start"))
            )
            campo_origem.click()

            time.sleep(1)
            campo_texto = self.driver.switch_to.active_element
            campo_texto.clear()
            campo_texto.send_keys(origem)

            self.wait.until(
                EC.presence_of_element_located((By.ID, "com.taxis99:id/layout_item"))
            )

            time.sleep(1)
            try:
                page_source = self.driver.page_source
                root = ET.fromstring(page_source)
                nome = ""
                endereco = ""
                for elem in root.iter():
                    rid = elem.get('resource-id', '')
                    if rid == 'com.taxis99:id/sug_name':
                        nome = elem.get('text', '')
                    elif rid == 'com.taxis99:id/sug_addr':
                        endereco = elem.get('text', '')
                        break
                if nome and endereco:
                    origem = f"{nome}, {endereco}"
            except Exception as e:
                logger.debug("Falha parse endereço origem", exc_info=True)

            self.driver.find_element(By.ID, "com.taxis99:id/layout_item").click()

        time.sleep(1)

        campo_destino = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.ID, "com.taxis99:id/et_end"))
        )
        campo_destino.click()
        campo_destino.clear()
        campo_destino.send_keys(destino)

        self.wait.until(
            EC.presence_of_element_located((By.ID, "com.taxis99:id/layout_item"))
        )

        time.sleep(1)
        try:
            page_source = self.driver.page_source
            root = ET.fromstring(page_source)
            nome = ""
            endereco = ""
            for elem in root.iter():
                rid = elem.get('resource-id', '')
                if rid == 'com.taxis99:id/sug_name':
                    nome = elem.get('text', '')
                elif rid == 'com.taxis99:id/sug_addr':
                    endereco = elem.get('text', '')
                    break
            if nome and endereco:
                destino = f"{nome}, {endereco}"
        except Exception as e:
            logger.debug("Falha parse endereço destino", exc_info=True)

        self.driver.find_element(By.ID, "com.taxis99:id/layout_item").click()

        time.sleep(1)

        self._fechar_dialog_amigo()

        self.wait.until(
            EC.presence_of_element_located((By.ID, "com.taxis99:id/anycar_item_container"))
        )

        CATEGORIAS_PERMITIDAS = {"moto", "pop", "pop expresso", "plus"}
        resultados = []

        page_source = self.driver.page_source
        root = ET.fromstring(page_source)

        containers = []
        for elem in root.iter():
            if elem.get('resource-id') == 'com.taxis99:id/anycar_item_container':
                containers.append(elem)

        for container in containers:
            try:
                categoria = None
                preco = None
                estimativa_text = None

                for child in container.iter():
                    rid = child.get('resource-id', '')
                    if rid == 'com.taxis99:id/anycar_item_car_name':
                        categoria = child.get('text', '')
                    elif rid == 'com.taxis99:id/new_estimate_price_text_tv':
                        preco = child.get('text', '')
                    elif rid == 'com.taxis99:id/mix_eta_tv':
                        estimativa_text = child.get('text', '')

                if not categoria or categoria.lower() not in CATEGORIAS_PERMITIDAS:
                    continue
                if not preco:
                    continue

                match = re.search(r'(\d+)\s*min', estimativa_text or '')
                estimativa_min = int(match.group(1)) if match else 0

                resultados.append(Corrida(
                    app="99",
                    categoria=categoria,
                    preco=float(preco.replace(".", "").replace(",", ".")),
                    estimativa=estimativa_min,
                    origem=origem,
                    destino=destino,
                    timestamp=datetime.now(),
                ))
            except Exception as e:
                logger.debug("Erro parse container", exc_info=True)
                continue

        if log:
            precos = [(r.categoria, r.preco) for r in resultados]
            log.debug("=== FIM coletar_precos 99 ===  quantidade=%d  precos=%s", len(resultados), precos)

        return resultados

    def coletar_metricas(self, corridas: List[Corrida]) -> List[Corrida]:
        log = obter_debug()
        if log:
            log.debug("coletar_metricas 99: sem metricas detalhadas para este app")
        return corridas

    def _fechar_dialog_amigo(self) -> None:
        assert self.driver is not None
        try:
            time.sleep(2)
            botao = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.ID, "com.taxis99:id/s_call_close_img"))
            )
            botao.click()
            time.sleep(3)
        except Exception:
            logger.debug("Dialog não encontrado, tentando tap alternativo")
            try:
                time.sleep(1)
                self.driver.tap([(628, 718)])
                time.sleep(3)
            except Exception:
                logger.debug("Tap alternativo também falhou")

    def voltar_tela_inicial(self) -> None:
        assert self.driver is not None

        for tentativa in range(4):
            self.driver.back()
            time.sleep(2)

            elementos_home = self.driver.find_elements(
                By.ID, "com.taxis99:id/oc_home_where_to_tv"
            )
            if len(elementos_home) > 0:
                logger.info("Retornou à tela inicial")
                return

        logger.warning("Não conseguiu validar volta à tela inicial")

    def desconectar(self) -> None:
        if self.driver:
            self.driver.terminate_app(self.app_package)
            self.driver.quit()
