Read [](file:///c%3A/Users/Rafael/Documents/Rafa/GitHub/google-sheets-gemini-automation/README.md)

Aqui está o seu arquivo README.md totalmente atualizado e revisado para refletir o estado atual do projeto (com as melhorias recentes como o sistema interativo de exclusão de estimativas usando ia semântica, suporte a gráficos, múltiplos usuários, resumos semanais e mensais):

```markdown
# 📊 Termômetro Financeiro - Bot Telegram

Automação da "Planilha do Breno" (Termômetro Financeiro) através de um bot do Telegram com IA (Gemini) para registro inteligente de gastos e economias por voz.

![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![Telegram Bot](https://img.shields.io/badge/telegram-bot-blue.svg)
![Google Sheets](https://img.shields.io/badge/google-sheets-green.svg)
![Gemini AI](https://img.shields.io/badge/gemini-ai-orange.svg)
![IA Semântica](https://img.shields.io/badge/sentence--transformers-blueviolet.svg)

## Sobre o Projeto

Este projeto automatiza o controle financeiro pessoal através de um bot do Telegram que:
- **Processa áudios** enviados pelo usuário usando Gemini AI
- **Classifica automaticamente** gastos em categorias (receita, despesa fixa, despesa diária, economia)
- **Atualiza o Google Sheets** em tempo real
- **Gerencia economias** em aba dedicada
- **Substitui estimativas** por valores reais automaticamente de forma interativa, através de busca semântica (CrossEncoder)

## Funcionalidades

### Processamento Inteligente de Áudio
- Envie áudios naturais como: *"Gastei 25 reais no mercado"*
- A IA identifica automaticamente:
  - Tipo de transação (receita, despesa fixa, despesa diária, economia)
  - Valor
  - Categoria
  - Data (hoje ou data específica)
  - Descrição

### Categorização Automática

| Tipo | Exemplos | Destino na Planilha |
|------|----------|---------------------|
| **Receita** | Salário, reembolso | Coluna "Entrada" |
| **Despesa Fixa** | Energia, água, internet | Coluna "Saída" |
| **Despesa Diária** | Mercado, lanche, transporte | Coluna "Diário" |
| **Economia** | Guardei na caixinha | Coluna "Saída" + Aba "Economia" |

### Recursos Especiais

- **Busca Semântica de Estimativas**: Toda vez que um gasto é registrado, uma Inteligência Artificial busca no mês inteiro se havia alguma estimativa correspondente cadastrada com `*` na frente da nota. Se encontrar um match forte, o bot pergunta se você deseja apagar a estimativa automaticamente.
- **Placeholder Inteligente**: Detecta `R$ 33,36` (valor específico do gasto Diário) como valor provisório e substitui automaticamente.
- **Dia Sem Gastos**: Ao dizer *"hoje não gastei nada"*, limpa valores e remove estimativas.
- **Múltiplos Gastos**: Soma automaticamente gastos adicionais lançados no mesmo dia.
- **Gráficos e Resumos**: 
  - `/grafico_saldo` - Gera um gráfico com a evolução diária do saldo no mês atual.
  - `/resumo_semanal` e `/resumo_mensal` para visualizar agregados detalhados de saídas, entradas e "performance".
- **Suporte Multi-usuário**: Múltiplos usuários podem registrar na mesma ou em planilhas diferentes.

## Tecnologias Utilizadas

- **Python 3.11+**
- **python-telegram-bot**: Criação do bot do Telegram
- **Google Gemini AI**: Processamento de linguagem natural e transcrição de áudio
- **Google Sheets API** (`gspread`, `google-api-python-client`): Atualização automática da planilha
- **Sentence Transformers** (CrossEncoder): Encontra matches de estimativas por similaridade semântica
- **Matplotlib**: Geração do gráfico de saldo

## Pré-requisitos

### 1. API Keys e Credenciais

- **Bot do Telegram**: Token obtido via [@BotFather](https://t.me/botfather)
- **Google Gemini API**: Chave da [Google AI Studio](https://aistudio.google.com/app/apikey)
- **Google Service Account**: Credenciais JSON da [Google Cloud Console](https://console.cloud.google.com/)
- **Google Sheets**: ID da planilha a ser atualizada

### 2. Planilha Google Sheets

Estrutura esperada:

**Aba Principal (ano atual, ex: "2026"):**
- Colunas organizadas por mês (Jan, Fev, Mar...)
- Para cada mês: Data | Entrada | Saída | Diário | Saldo
- Dias do mês nas linhas (dia 1 = linha 3, dia 2 = linha 4, etc.)

**Aba "Economia":**
- Coluna I (9): Valor economizado
- Linha 5: Janeiro
- Linha 6: Fevereiro
- ... (uma linha por mês)

### 3. APIs Habilitadas no Google Cloud

- Google Sheets API
- Google Drive API

## 🚀 Instalação

### 1. Clone o Repositório

```bash
git clone https://github.com/seu-usuario/google-sheets-gemini-automation.git
cd google-sheets-gemini-automation
```

### 2. Crie um Ambiente Virtual

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 3. Instale as Dependências

```bash
pip install -r requirements.txt
```

### 4. Configure as Variáveis de Ambiente

Crie um arquivo .env na raiz do projeto:

```env
TELEGRAM_TOKEN=seu_token_do_botfather
GOOGLE_API_KEY=sua_chave_gemini_api
GOOGLE_CREDENTIALS_JSON={"type":"service_account"...} # Opcional se usar arquivo credentials.json físico

# (Para único usuário)
GOOGLE_SHEETS_ID=id_da_sua_planilha
DEFAULT_TELEGRAM_USER_ID=seu_user_id_do_telegram

# (Para múltiplos usuários / Multi-planilha)
# USER_CONFIG_JSON={"users":[{"telegram_user_id":123,"name":"João","spreadsheet_id":"ABC","placeholder_value": 0.0, "timezone": "America/Sao_Paulo", "active": true}]}
```

### 5. Adicione as Credenciais do Google

Coloque o arquivo credentials.json (Service Account) na raiz do projeto, ou passe o JSON via `GOOGLE_CREDENTIALS_JSON` em ambientes Cloud.

### 6. Compartilhe a Planilha

1. Copie o valor do campo `"client_email"` do seu arquivo credentials.
2. Compartilhe sua planilha Google Sheets com esse email (permissão de Editor).

## Como Usar

### Iniciar o Bot

```bash
python main.py
```

Você verá: `Bot iniciado...`

### Comandos do Bot

- `/start` - Inicia a conversa e mostra instruções
- `/ajuda` - Dicas de como falar as despesas
- `/resumo_semanal` - Envia um compilado dos gastos da semana
- `/resumo_mensal` - Mostra um compilado dos gastos do mês corrente
- `/grafico_saldo` - Retorna imagem estatística de salto até a data corrente

### Exemplos de Uso

#### Registrar Despesa e Tratar Estimativa (Match Semântico)
**Setup:** Célula do dia 20 tem nota `*Pagamento wifi` (estimativa).

**Áudio:** *"Gastei 119 reais hoje de wifi."*

**Resultado:**
1. O valor é adicionado no dia e categoria correspondentes.
2. O bot responde: *Encontrei uma estimativa que pode ser referente a este gasto: "Pagamento wifi" no dia 20/04. Deseja apagar essa estimativa? Responda sim ou não.*
3. Ao responder "sim", ele remove valor e nota estimadas no dia 20 mantendo só o real.

#### Dia Sem Gastos
**Áudio:** *"Hoje não gastei nada"*

**Resultado:**
- Coluna "Diário": zerada (0.0)
- Coluna "Saída": limpa (remove estimativas atreladas à célula correspondente)

## Estrutura do Projeto

```
google-sheets-gemini-automation/
├── main.py                 # Bot do Telegram e handlers (incluindo handler interativo)
├── gemini_parser.py        # Integração com Gemini AI
├── sheets_writer.py        # Escrita e limpeza da Planilha do Google Sheets
├── sheets_reader.py        # Leitura da planilha para resumos e gráficos
├── estimate_scanner.py     # Varredor de notas com estimativas '*'
├── matcher.py              # Motor de NLP (CrossEncoder)
├── utils.py                # Funções de data, coluna/linha
├── user_config.py          # Gestão de múltiplos usuários baseada no telegram_id
├── requirements.txt        # Dependências Python
├── .env                    # Variáveis de ambiente (não commitado)
├── credentials.json        # Credenciais Google (não commitado)
├── temp/                   # Pasta para arquivos de áudio temporários
└── README.md               # Documentação
```

## Troubleshooting

### Erro de credenciais ou "Aba não encontrada"
- Certifique-se de que a aba tem o ano atual (ex: "2026") criado e bem formatado.
- Verifique se a planilha foi compartilhada com o email da Service Account.

### Confirmações / Respostas pendentes
- O bot não exclui a estimativa a não ser que você valide com texto ("sim", "não"). 

##  TODO / Melhorias Futuras
- [ ] Adicionar um valor de "gasto diário" personalizado nativo no prompt (system_prompt).
- [ ] Suporte a validação por extração em fotos/recibos fiscais (OCR multi-modal pelo Gemini).

---

⭐ Se este projeto te ajudou, considere dar uma estrela no GitHub!

📧 Dúvidas ou sugestões? Abra uma [issue](https://github.com/rafaPassarinho/google-sheets-gemini-automation/issues)!
