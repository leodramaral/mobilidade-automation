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
                EC.presence_of_element_located((By.XPATH, "//*[@content-desc='Para onde?']"))
            )
        except Exception:
            print("App não abriu automaticamente, tentando abrir manualmente...")
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
        print("Clicou no input 'Para onde?'")

        # Validação: aguardar campo de busca aparecer
        time.sleep(2)

        # TODO: Próximos passos - preencher origem, destino, extrair preços
        print("Passo 1 concluído: input de busca aberto")

        return []

    def voltar_tela_inicial(self) -> None:
        assert self.driver is not None

        for tentativa in range(4):
            self.driver.back()
            time.sleep(2)

            elementos_home = self.driver.find_elements(
                By.XPATH, "//*[@content-desc='Para onde?']"
            )
            if len(elementos_home) > 0:
                print("Retornou à tela inicial com sucesso!")
                return

        print("Aviso: Não conseguiu validar a volta para a tela inicial")

    def desconectar(self) -> None:
        if self.driver:
            print("Encerrando sessão...")
            self.driver.quit()
