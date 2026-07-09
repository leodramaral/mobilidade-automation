# Mobilidade

Sistema de monitoramento de precos de aplicativos de transporte (ride-hailing). Coleta precos do app 99 via automacao Appium em um dispositivo Android, armazena snapshots em SQLite e exibe os dados em um dashboard Streamlit.

## Funcionalidades

- **Coleta automatizada**: Conecta ao Appium Server, abre o app 99, busca um destino e captura os precos das categorias disponiveis (Comum, Comfort, Black, etc.)
- **Armazenamento persistente**: Cada coleta e salva como um snapshot no banco SQLite com timestamp e modelo do dispositivo
- **Dashboard interativo**: Interface Streamlit com filtros por categoria e app, exibicao em tabela e exportacao em JSON

## Como funciona

1. O Appium conecta ao dispositivo Android via UiAutomator2
2. Abre o app 99 e digita o destino configurado
3. Seleciona o primeiro resultado da busca
4. Le os cards de precos (categoria, preco, estimativa de tempo)
5. Salva os dados no SQLite e aguarda o intervalo configurado
6. Repete N vezes conforme definido em `config.json`

---

## Executando com o .exe (Windows)

### Pre-requisitos

1. **Node.js** - Necessario para instalar o Appium via npm
   - Baixe em: https://nodejs.org
   - Versao LTS recomendada

2. **Android SDK / Platform Tools** - Para o adb (conexao com o dispositivo)
   - Instale as Platform Tools do Android SDK
   - Adicione o diretorio `platform-tools` ao PATH do sistema

3. **Appium Server** - Instalado via npm (usa o Node.js)
   ```
   npm install -g appium
   ```

4. **Driver UiAutomator2** - Instalado via Appium
   ```
   appium driver install uiautomator2
   ```

5. **Dispositivo Android** - Commodo ligado, com modo desenvolvedor e depuracao USB ativados

### Passos para rodar

#### 1. Iniciar o Appium Server

Abra um terminal (PowerShell ou CMD) e execute:

```
appium
```

O server iniciara em `http://127.0.0.1:4723` (porta padrao). Mantenha este terminal aberto.

#### 2. Verificar conexao com o dispositivo

Em outro terminal, verifique se o dispositivo esta conectado:

```
adb devices
```

Deve listar o dispositivo conectado (ex: `MotoG86`).

#### 3. Configurar o destino

Edite o arquivo `config.json` que esta na mesma pasta do `.exe`:

```json
{
  "app": "99",
  "destino": "Seu destino aqui",
  "limite_consultas": 2,
  "intervalo_segundos": 20,
  "appium": {
    "server": "http://127.0.0.1:4723",
    "device": "MotoG86",
    "app_package": "com.taxis99"
  },
  "persistencia": {
    "tipo": "banco",
    "caminho": "mobilidade.db"
  }
}
```

Ajuste:
- `destino`: endereco ou local de destino para a busca
- `limite_consultas`: numero de coletas a realizar
- `intervalo_segundos`: tempo entre cada coleta
- `device`: nome do dispositivo (use `adb devices` para verificar)
- `app_package`: pacote do app 99 (`com.taxis99`)

#### 4. Executar o dashboard

Clique duas vezes em `Mobilidade.exe` ou execute no terminal:

```
Mobilidade.exe
```

O dashboard abrira automaticamente no navegador em `http://localhost:8501`.

#### 5. Iniciar uma coleta

Na barra lateral do dashboard:
1. Configure o destino e parametros
2. Clique em "Iniciar Coleta"
3. O sistema conectara ao Appium e comecara a coletar precos
4. Os resultados aparecero na tabela e poderao ser exportados em JSON

---

## Estrutura do projeto (desenvolvimento)

```
Mobilidade/
  main.py                  ← CLI para coleta direta
  run_dashboard.py         ← Entry point do .exe (Streamlit)
  config.json              ← Configuracoes de runtime
  build.bat                ← Script de build do executavel
  coletor.py               ← Logica de coleta orchestrada
  automacoes/
    base.py                ← Classe abstrata de automacao
    automacao_99.py        ← Automacao especifica do app 99
  modelos/
    corrida.py             ← Modelos de dados (Corrida, Snapshot)
  persistencia/
    base.py                ← Interface base de persistencia
    repositorio_banco.py   ← Implementacao SQLite
  ui/
    app.py                 ← Dashboard Streamlit
  .streamlit/
    config.toml            ← Configuracao do Streamlit
```

## Banco de dados

Os dados sao salvos em `mobilidade.db` (SQLite) na pasta atual do executavel. Estrutura da tabela `snapshots`:

| Coluna | Tipo | Descricao |
|--------|------|-----------|
| id | INTEGER | Chave primaria auto-incremental |
| timestamp | TEXT | Momento da coleta (ISO 8601) |
| device_model | TEXT | Modelo do dispositivo Android |
| app | TEXT | Aplicativo de coleta (ex: "99", "uber") |
| origem | TEXT | Endereco de origem da coleta |
| destino | TEXT | Endereco de destino da coleta |
| condicao_tempo | TEXT | Condicao do tempo no momento da coleta (reservado para uso futuro) |
| payload_json | TEXT | JSON array com os dados das corridas (categoria, preco, estimativa) |

## Solucao de problemas

**Appium nao conecta:**
- Verifique se o Appium Server esta rodando (`appium` no terminal)
- Confirme a porta (padrao 4723) no `config.json`

**Dispositivo nao encontrado:**
- Execute `adb devices` para verificar a conexao
- Ative a depuracao USB no dispositivo
- Verifique se o nome do dispositivo no `config.json` esta correto

**App 99 nao abre:**
- Confirme que o app esta instalado no dispositivo
- Verifique o `app_package` no `config.json` (deve ser `com.taxis99`)

**Dashboard nao inicia:**
- Verifique se a porta 8501 nao esta em uso
- O `.exe` precisa de permissao de administrador em alguns casos
