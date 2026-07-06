import time
from appium import webdriver
from appium.options.android import UiAutomator2Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 1. Configurações de conexão com o seu Moto G86
options = UiAutomator2Options()
options.platform_name = 'Android'
options.automation_name = 'UiAutomator2'
options.device_name = 'MotoG86'
options.app_package = 'com.taxis99'
options.no_reset = True  # Mantém sua conta logada para não pedir SMS

print("Conectando ao Appium Server...")
driver = webdriver.Remote('http://127.0.0.1:4723', options=options)
wait = WebDriverWait(driver, 20)

try:
    # ---------------------------------------------------------
    # PASSO 1: Clicar em "Para onde vamos?" na tela inicial
    # ---------------------------------------------------------
    print("Aguardando a tela inicial da 99...")
    botao_onde_vamos = wait.until(
        EC.element_to_be_clickable((By.ID, "com.taxis99:id/oc_home_where_to_tv"))
    )
    print("Clicando no campo 'Para onde vamos?'...")
    botao_onde_vamos.click()

    # ---------------------------------------------------------
    # PASSO 2: Inputar o endereço de texto
    # ---------------------------------------------------------
    print("Aguardando abertura da tela de busca...")
    wait.until(EC.presence_of_element_located((By.ID, "com.taxis99:id/input_shadow")))
    
    destino_texto = "Amazonas Shopping"
    print(f"Digitando o destino: {destino_texto}")
    
    # Captura o campo de entrada ativo, limpa dados antigos e envia o texto
    campo_texto = driver.switch_to.active_element
    campo_texto.clear()
    campo_texto.send_keys(destino_texto)
    
    # ---------------------------------------------------------
    # PASSO 3: Selecionar o endereço na lista de sugestões (CORRIGIDO)
    # ---------------------------------------------------------
    print("Aguardando a lista de sugestões de endereço carregar...")
    # Usando o ID real verificado no seu Appium Inspector: com.taxis99:id/layout_item
    primeiro_resultado = wait.until(
        EC.element_to_be_clickable((By.ID, "com.taxis99:id/layout_item"))
    )
    print("Sugestão encontrada! Clicando no primeiro resultado da lista...")
    primeiro_resultado.click()

    # ---------------------------------------------------------
    # PASSO 4: Varredura da tela de preços
    # ---------------------------------------------------------
    print("Aguardando carregamento da tela de ofertas...")
    
    # Aguarda o container principal do card Pop carregar
    wait.until(EC.presence_of_element_located((By.ID, "com.taxis99:id/anycar_item_container")))
    
    # Extração dos dados usando os IDs inspecionados
    tipo_corrida = driver.find_element(By.ID, "com.taxis99:id/anycar_item_car_name").text
    preco_texto = driver.find_element(By.ID, "com.taxis99:id/new_estimate_price_text_tv").text
    estimativa_tempo = driver.find_element(By.ID, "com.taxis99:id/mix_eta_tv").text
    
    # Print do resultado limpo no console
    print("\n========================================")
    print("📊 RESULTADO DA SIMULAÇÃO OBTIDO:")
    print(f"🚗 Categoria: {tipo_corrida}")
    print(f"💰 Valor: R$ {preco_texto}")
    print(f"🕒 Estimativa: {estimativa_tempo}")
    print("========================================\n")

except Exception as e:
    print(f"\n❌ Ocorreu um erro durante a automação: {e}\n")

finally:
    print("Encerrando sessão do driver...")
    driver.quit()