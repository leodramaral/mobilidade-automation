import re
import time
from datetime import datetime
from typing import List

from appium import webdriver
from appium.options.android import UiAutomator2Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException

from automacoes.base import BaseAutomacao
from modelos.corrida import Corrida


class Automacao99(BaseAutomacao):
    def __init__(self, config_appium: dict):
        self.server = config_appium['server']
        self.device = config_appium['device']
        self.app_package = config_appium['app_package']
        self.driver = None
        self.wait = None

    def conectar(self) -> None:
        options = UiAutomator2Options()
        options.platform_name = 'Android'
        options.automation_name = 'UiAutomator2'
        options.device_name = self.device
        options.app_package = self.app_package
        options.no_reset = True

        print("Conectando ao Appium Server...")
        self.driver = webdriver.Remote(self.server, options=options)
        self.wait = WebDriverWait(self.driver, 20)

        print("Aguardando app carregar...")
        self.wait.until(
            EC.presence_of_element_located((By.ID, "com.taxis99:id/oc_home_where_to_tv"))
        )

    def coletar_precos(self, destino: str) -> List[Corrida]:
        # 1. Clicar em "Para onde vamos?"
        botao = self.wait.until(
            EC.element_to_be_clickable((By.ID, "com.taxis99:id/oc_home_where_to_tv"))
        )
        botao.click()

        # 2. Digitar destino
        self.wait.until(
            EC.presence_of_element_located((By.ID, "com.taxis99:id/input_shadow"))
        )
        campo_texto = self.driver.switch_to.active_element
        campo_texto.clear()
        campo_texto.send_keys(destino)

        # Capturar origem (Local de embarque)
        try:
            origem = self.driver.find_element(
                By.ID, "com.taxis99:id/et_start"
            ).text
        except Exception:
            origem = "N/A"

        # 3. Selecionar sugestão (com retry para StaleElementReferenceException)
        self.wait.until(
            EC.presence_of_element_located((By.ID, "com.taxis99:id/layout_item"))
        )

        for tentativa in range(3):
            try:
                primeiro_resultado = self.driver.find_element(
                    By.ID, "com.taxis99:id/layout_item"
                )
                primeiro_resultado.click()
                break
            except Exception:
                time.sleep(1)

        # 4. Aguardar ofertas e extrair preços
        self.wait.until(
            EC.presence_of_element_located((By.ID, "com.taxis99:id/anycar_item_container"))
        )

        conteineres = self.driver.find_elements(
            By.ID, "com.taxis99:id/anycar_item_container"
        )

        resultados = []
        for card in conteineres[:4]:
            try:
                categoria = card.find_element(
                    By.ID, "com.taxis99:id/anycar_item_car_name"
                ).text
                preco = card.find_element(
                    By.ID, "com.taxis99:id/new_estimate_price_text_tv"
                ).text
                estimativa_texto = card.find_element(
                    By.ID, "com.taxis99:id/mix_eta_tv"
                ).text
                estimativa_min = int(re.search(r'(\d+)\s*min', estimativa_texto).group(1))

                resultados.append(Corrida(
                    app="99",
                    categoria=categoria,
                    preco=float(preco.replace(".", "").replace(",", ".")),
                    estimativa=estimativa_min,
                    origem=origem,
                    destino=destino,
                    timestamp=datetime.now(),
                ))
            except Exception:
                continue

        return resultados

    def voltar_tela_inicial(self) -> None:
        for tentativa in range(4):
            self.driver.back()
            time.sleep(2)

            elementos_home = self.driver.find_elements(
                By.ID, "com.taxis99:id/oc_home_where_to_tv"
            )
            if len(elementos_home) > 0:
                print("Retornou à tela inicial com sucesso!")
                return

        print("Aviso: Não conseguiu validar a volta para a tela inicial")

    def desconectar(self) -> None:
        if self.driver:
            print("Encerrando sessão...")
            self.driver.quit()
