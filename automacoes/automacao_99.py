import re
import time
from datetime import datetime
from typing import List, Optional

from appium import webdriver
from appium.options.android import UiAutomator2Options
from appium.webdriver import Remote as AppiumDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException

from automacoes.base import BaseAutomacao
from modelos.corrida import Corrida


class Automacao99(BaseAutomacao):
    def __init__(self, config_appium: dict[str, str]):
        self.server = config_appium['server']
        self.device = config_appium['device']
        self.app_package = config_appium['app_package']
        self.driver: Optional[AppiumDriver] = None
        self.wait: Optional[WebDriverWait] = None

    def conectar(self) -> None:
        options = UiAutomator2Options()
        options.platform_name = 'Android'
        options.automation_name = 'UiAutomator2'
        options.device_name = self.device
        options.app_package = self.app_package
        options.app_wait_duration = 60000
        options.no_reset = True
        options.set_capability('appWaitForLaunch', False)

        print("Conectando ao Appium Server...")
        self.driver = webdriver.Remote(self.server, options=options)
        self.device_model = self.driver.capabilities.get('deviceModel', 'desconhecido')
        print(f"Dispositivo conectado: {self.device_model}")
        self.wait = WebDriverWait(self.driver, 20)

        print("Aguardando app carregar...")
        try:
            self.wait.until(
                EC.presence_of_element_located((By.ID, "com.taxis99:id/oc_home_where_to_tv"))
            )
        except Exception:
            print("App não abriu automaticamente, tentando abrir manualmente...")
            self.driver.activate_app(self.app_package)
            self.wait.until(
                EC.presence_of_element_located((By.ID, "com.taxis99:id/oc_home_where_to_tv"))
            )

    def coletar_precos(self, destino: str, origem: str = "") -> List[Corrida]:
        assert self.driver is not None
        assert self.wait is not None

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

            for tentativa in range(3):
                try:
                    primeiro_resultado = self.driver.find_element(
                        By.ID, "com.taxis99:id/layout_item"
                    )
                    primeiro_resultado.click()
                    break
                except Exception:
                    time.sleep(1)

        time.sleep(1)
        campo_destino = WebDriverWait(self.driver, 10).until(
            EC.element_to_be_clickable((By.ID, "com.taxis99:id/et_end"))
        )
        campo_destino.click()
        campo_destino.clear()
        campo_destino.send_keys(destino)

        try:
            origem = self.driver.find_element(
                By.ID, "com.taxis99:id/et_start"
            ).text
        except Exception:
            origem = "N/A"

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

        self._fechar_dialog_amigo()

        self.wait.until(
            EC.presence_of_element_located((By.ID, "com.taxis99:id/anycar_item_container"))
        )

        conteineres = self.driver.find_elements(
            By.ID, "com.taxis99:id/anycar_item_container"
        )

        CATEGORIAS_PERMITIDAS = {"moto", "pop", "pop expresso", "plus"}

        resultados = []
        for card in conteineres:
            try:
                categoria = card.find_element(
                    By.ID, "com.taxis99:id/anycar_item_car_name"
                ).text

                if categoria.lower() not in CATEGORIAS_PERMITIDAS:
                    continue

                preco = card.find_element(
                    By.ID, "com.taxis99:id/new_estimate_price_text_tv"
                ).text
                estimativa_label = card.find_element(
                    By.ID, "com.taxis99:id/mix_eta_tv"
                ).text
                match = re.search(r'(\d+)\s*min', estimativa_label)
                estimativa_min = int(match.group(1)) if match else 0

                resultados.append(Corrida(
                    app="99",
                    categoria=categoria,
                    preco=float(preco.replace(".", "").replace(",", ".")),
                    estimativa=estimativa_min,
                    origem=origem,
                    destino=destino,
                    timestamp=datetime.now(),
                    preco_label=preco,
                    estimativa_label=estimativa_label,
                ))
            except Exception:
                continue

        return resultados

    def _fechar_dialog_amigo(self) -> None:
        assert self.driver is not None
        try:
            time.sleep(2)
            botao = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.ID, "com.taxis99:id/s_call_close_img"))
            )
            botao.click()
            print("Dialog 'Pedindo para um amigo' detectado e fechado.")
            time.sleep(3)
        except Exception:
            try:
                time.sleep(1)
                self.driver.tap([(628, 718)])
                print("Dialog 'Pedindo para um amigo' fechado via tap coordenado.")
                time.sleep(3)
            except Exception:
                pass

    def voltar_tela_inicial(self) -> None:
        assert self.driver is not None

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
