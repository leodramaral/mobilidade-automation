# Descreve o fluxo para obter as métricas de precificação usada em [automação uber](./../../automacoes/automacao_uber.py)

## Objetivo

Capturar as métricas de preço:
- `preco_base`
- `preco_minimo`
- `adicional_por_minuto`
- `adicional_por_km`
- `custo_fixo`

## Telas do fluxo

| Tela | Descrição | Template |
|------|-----------|----------|
| 1. Lista de opções | Modal com categorias (UberX, Moto, etc.) | [lista-opcao-corrida.xml](./lista-opcao-corrida.xml) |
| 2. Detalhes da corrida | "Confirmar informações" + "Viagens baratas" | [detalhes-corrida-selecionada.xml](./detalhes-corrida-selecionada.xml) |
| 3. Métricas de preço | `line_items_container` com detalhamento | [metricas-de-preco.xml](./metricas-de-preco.xml) |

## Fluxo por categoria

### Passo 1: Selecionar categoria (Tela 1 → Tela 1)

A lista aparece após preencher origem e destino. Cada item tem `content-desc` no formato:
```
selecionado!UberX!Preço: R$ 7,17!Desconto de R$ 11,95!tempo estimado...!capacidade estimada: 4!Mais rápido
```

- Se a categoria já está "selecionada", pular para o Passo 2
- Se não está selecionada, clicar no elemento para selecioná-la
- **XPaths:**
  - Elemento clicável: `//*[@clickable='true' and .//*[contains(@content-desc,'!UberX!')]]`
  - Verificar se está selecionado: checar se `content-desc` começa com "selecionado"

### Passo 2: Abrir detalhes (Tela 1 → Tela 2)

Clicar novamente no mesmo elemento selecionado para abrir os detalhes da corrida.

- **Elemento:** O mesmo elemento clicável do Passo 1
- **Esperar:** Texto "Confirmar informações" ou `content-desc` contendo "capacidade estimada"

### Passo 3: Abrir métricas (Tela 2 → Tela 3)

Na tela de detalhes, existe uma seção clicável que varia por categoria:

| Categoria | Texto clicável |
|-----------|----------------|
| UberX | "Viagens baratas" |
| Moto | "Viagens de motocicleta acessíveis" |
| Prioridade | "Embarque Priorizado" |
| Confort | "Carros mais novos e espaçosos para maior conforto" |

**Importante:** O texto muda mas a estrutura é a mesma — é um elemento View clicável dentro do `UberComposeView`.

- **XPaths para encontrar (genérico):**
  - Buscar elemento com `content-desc` contendo "capacidade estimada" (presente em todas as categorias)
  - `//com.uber.rib.core.compose.root.UberComposeView//*[@clickable='true' and .//*[contains(@content-desc,'capacidade estimada')]]`
- **Esperar:** `//*[@resource-id='com.ubercab:id/line_items_container']`

### Passo 4: Extrair métricas (Tela 3)

O `line_items_container` contém `ViewGroup`s filhos, cada um com:
- `title_text`: nome do campo (ex: "Preço base", "Preço mínimo", "+ por minuto", "+ por quilômetro", "Custo fixo")
- `primary_end_text`: valor (ex: "R$ 3,28")

- **XPaths:**
  - Grupos: `//*[@resource-id='com.ubercab:id/line_items_container']/android.view.ViewGroup`
  - Título: `.//*[@resource-id='com.ubercab:id/title_text']`
  - Valor: `.//*[@resource-id='com.ubercab:id/primary_end_text']`

### Passo 5: Voltar para lista (Tela 3 → Tela 1)

Navegação com 2x `driver.back()`:
1. `driver.back()` → volta de Métricas para Detalhes
2. Verificar se já estamos na lista (buscar `//*[contains(@content-desc,'Preço:')]`)
3. Se não estiver na lista, `driver.back()` novamente → volta de Detalhes para Lista

## Conhecimentos importantes

### Performance do Appium

- **`get_attribute("content-desc")` é extremamente lento** (~20-40s por chamada via UiAutomator2)
- **Solução:** Usar XPath direto com o nome da categoria em vez de iterar elementos e ler atributos
- **Exemplo:** `//*[@clickable='true' and .//*[contains(@content-desc,'!UberX!')]]`

### Case sensitivity

- O XPath é case-sensitive: `!uberx!` não encontra `!UberX!`
- **Solução:** Guardar o case original do content-desc e usá-lo no XPath

### Scrolls na lista

- A lista de opções pode ter itens fora da tela visível
- Usar `_scroll_lista_opcoes()` para acessar itens não visíveis
- Após scroll, re-buscar os elementos

### Navegação entre telas

- Tela 3 (Métricas) → Tela 2 (Detalhes): 1x `driver.back()`
- Tela 2 (Detalhes) → Tela 1 (Lista): 1x `driver.back()`
- **NÃO usar botão "Voltar" (x) da toolbar** — usar `driver.back()` padrão

### Erros comuns

- `StaleElementReferenceException`: Elemento ficou obsoleto após mudança de estado da tela
- `TimeoutException`: Elemento não encontrado no tempo esperado — pode indicar que a tela mudou
- Card view não encontrado: O clique pode não ter aberto a tela de métricas

## Arquivo de debug

Ao executar, é gerado um arquivo em `debugs/<timestamp>.log` no diretório raiz com timestamps de cada operação para diagnóstico. Um novo arquivo é criado a cada coleta.
