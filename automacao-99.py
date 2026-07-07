import time
from datetime import datetime
from appium import webdriver
from appium.options.android import UiAutomator2Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Configurações de conexão
options = UiAutomator2Options()
options.platform_name = 'Android'
options.automation_name = 'UiAutomator2'
options.device_name = 'MotoG86'
options.app_package = 'com.taxis99'
options.no_reset = True

print("Conectando ao Appium Server...")
driver = webdriver.Remote('http://127.0.0.1:4723', options=options)
wait = WebDriverWait(driver, 20)

LIMITE_CONSULTAS = 120
INTERVALO_SEGUNDOS = 20 
ARQUIVO_MD = "dados_corridas.md"
DESTINO = "Amazonas Shopping"

# Cria/limpa o arquivo e adiciona o cabeçalho inicial
with open(ARQUIVO_MD, "w", encoding="utf-8") as f:
    f.write(f"# Relatório de Monitoramento 99 - {DESTINO}\n")
    f.write(f"Início da coleta: {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}\n\n")

try:
    for rodada in range(1, LIMITE_CONSULTAS + 1):
        agora = datetime.now().strftime('%H:%M:%S')
        print(f"\n[{agora}] Iniciando rodada {rodada}/{LIMITE_CONSULTAS}...")

        # 1. Clicar em "Para onde vamos?"
        botao_onde_vamos = wait.until(EC.element_to_be_clickable((By.ID, "com.taxis99:id/oc_home_where_to_tv")))
        botao_onde_vamos.click()

        # 2. Inputar o endereço e selecionar a sugestão
        wait.until(EC.presence_of_element_located((By.ID, "com.taxis99:id/input_shadow")))
        campo_texto = driver.switch_to.active_element
        campo_texto.clear()
        campo_texto.send_keys(DESTINO)
        
        wait.until(EC.presence_of_element_located((By.ID, "com.taxis99:id/layout_item")))

        for tentativa in range(3):
            try:
                primeiro_resultado = driver.find_element(By.ID, "com.taxis99:id/layout_item")
                primeiro_resultado.click()
                break
            except Exception:
                time.sleep(1)

        # 3. Aguardar a tela de ofertas carregar os contêineres de corrida
        wait.until(EC.presence_of_element_located((By.ID, "com.taxis99:id/anycar_item_container")))
        
        # Coleta TODOS os contêineres de carros visíveis na tela
        conteineres_carros = driver.find_elements(By.ID, "com.taxis99:id/anycar_item_container")
        
        resultados_rodada = []
        
        # Pega apenas os 4 primeiros resultados (ou menos, se não houver 4 na tela)
        for card in conteineres_carros[:4]:
            try:
                tipo = card.find_element(By.ID, "com.taxis99:id/anycar_item_car_name").text
                preco = card.find_element(By.ID, "com.taxis99:id/new_estimate_price_text_tv").text
                tempo = card.find_element(By.ID, "com.taxis99:id/mix_eta_tv").text
                resultados_rodada.append((tipo, preco, tempo))
            except Exception as e:
                # Ignora se algum card estiver incompleto ou carregando
                continue

        # 4. Salvar no arquivo .md
        with open(ARQUIVO_MD, "a", encoding="utf-8") as f:
            f.write(f"### 🕒 Consulta {rodada} - {agora}\n")
            f.write("| Categoria | Preço (R$) | Estimativa |\n")
            f.write("| :--- | :--- | :--- |\n")
            for tipo, preco, tempo in resultados_rodada:
                f.write(f"| {tipo} | {preco} | {tempo} |\n")
                print(f"  -> {tipo}: R${preco} ({tempo})")
            f.write("\n---\n\n")

        # Se não for a última rodada, clica em Voltar e aguarda
        if rodada < LIMITE_CONSULTAS:
            print("Voltando para a tela inicial...")
            
            # Loop de fuga: Aperta o voltar nativo do Android até achar a tela inicial
            tela_inicial_encontrada = False
            for tentativa in range(4): # Tenta voltar no máximo 4 vezes
                driver.back() # Simula o botão físico de voltar do celular
                time.sleep(2) # Dá um tempo para a animação do Android acontecer
                
                # Verifica se o campo "Para onde vamos?" já apareceu na tela
                elementos_home = driver.find_elements(By.ID, "com.taxis99:id/oc_home_where_to_tv")
                if len(elementos_home) > 0:
                    print("✅ Retornou à tela inicial do mapa com sucesso!")
                    tela_inicial_encontrada = True
                    break
            
            if not tela_inicial_encontrada:
                print("⚠️ Aviso: Não conseguiu validar a volta para a tela inicial, tentando continuar mesmo assim...")
            
            print(f"Aguardando {INTERVALO_SEGUNDOS} segundos para a próxima consulta...")
            time.sleep(INTERVALO_SEGUNDOS)

except Exception as e:
    print(f"\n❌ Erro durante o loop de automação: {e}\n")

finally:
    print("\n✅ Monitoramento finalizado. Encerrando sessão...")
    driver.quit()