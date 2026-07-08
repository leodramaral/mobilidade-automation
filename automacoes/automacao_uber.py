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
from modelos.corrida import Corrida


class AutomacaoUber(BaseAutomacao):
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

        campo_destino = self.wait.until(
            EC.element_to_be_clickable((By.ID, "com.ubercab:id/edit_text"))
        )
        campo_destino.click()
        time.sleep(0.5)
        campo_destino.clear()
        campo_destino.send_keys(destino)

        container_resultados = self.wait.until(
            EC.presence_of_element_located((By.ID, "com.ubercab:id/ub__text_search_v2_results"))
        )

        for tentativa in range(3):
            try:
                primeiro_resultado = container_resultados.find_element(
                    By.XPATH, ".//android.widget.Button[@content-desc]"
                )
                primeiro_resultado.click()
                break
            except Exception:
                time.sleep(0.5)

        time.sleep(2)

        CATEGORIAS_PERMITIDAS = {"uberx", "comfort", "moto"}
        resultados = []

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
                    if parte_lower in CATEGORIAS_PERMITIDAS:
                        categoria = parte.strip()
                        break
                    if "selecionado" in parte_lower:
                        if i + 1 < len(partes):
                            categoria = partes[i + 1].strip()
                            break

                if not categoria or categoria.lower() not in CATEGORIAS_PERMITIDAS:
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
                    preco_label=f"R$ {preco_str}",
                    estimativa_label=f"{estimativa_min} min",
                ))
            except Exception:
                continue

        return resultados

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
