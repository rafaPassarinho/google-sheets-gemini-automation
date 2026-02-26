# 📊 Termômetro Financeiro - Bot Telegram

Automação da "Planilha do Breno" (Termômetro Financeiro) através de um bot do Telegram com IA (Gemini) para registro inteligente de gastos e economias por voz.

![Python](https://img.shields.io/badge/python-3.11+-blue.svg)
![Telegram Bot](https://img.shields.io/badge/telegram-bot-blue.svg)
![Google Sheets](https://img.shields.io/badge/google-sheets-green.svg)
![Gemini AI](https://img.shields.io/badge/gemini-ai-orange.svg)

## 🎯 Sobre o Projeto

Este projeto automatiza o controle financeiro pessoal através de um bot do Telegram que:
- 🎤 **Processa áudios** enviados pelo usuário usando Gemini AI
- 📝 **Classifica automaticamente** gastos em categorias (receita, despesa fixa, despesa diária, economia)
- 📊 **Atualiza o Google Sheets** em tempo real
- 💰 **Gerencia economias** em aba dedicada
- 🔄 **Substitui estimativas** por valores reais automaticamente

## ✨ Funcionalidades

### 🎙️ Processamento Inteligente de Áudio
- Envie áudios naturais como: *"Gastei 25 reais no mercado"*
- IA identifica automaticamente:
  - Tipo de transação (receita, despesa fixa, despesa diária, economia)
  - Valor
  - Categoria
  - Data (hoje ou data específica)
  - Descrição

### 📈 Categorização Automática

| Tipo | Exemplos | Destino na Planilha |
|------|----------|---------------------|
| **Receita** | Salário, reembolso | Coluna "Entrada" |
| **Despesa Fixa** | Energia, água, internet | Coluna "Saída" |
| **Despesa Diária** | Mercado, lanche, transporte | Coluna "Diário" |
| **Economia** | Guardei na caixinha | Coluna "Saída" + Aba "Economia" |

### 🎯 Recursos Especiais

- **Placeholder Inteligente**: Detecta `R$ 33,36` como valor provisório e substitui automaticamente
- **Estimativas com Asterisco**: Notas com `*` indicam valores estimados que serão substituídos
- **Dia Sem Gastos**: Ao dizer *"hoje não gastei nada"*, limpa valores e remove estimativas
- **Múltiplos Gastos**: Soma automaticamente gastos adicionais no mesmo dia
- **Histórico em Notas**: Mantém registro detalhado de cada transação nas notas das células

### 💾 Integração com Google Sheets

- **Aba Principal (Ano)**: Registra transações diárias organizadas por mês
- **Aba Economia**: Acumula valores guardados mensalmente

## 🛠️ Tecnologias Utilizadas

- **Python 3.11+**
- **python-telegram-bot**: Criação do bot do Telegram
- **Google Gemini AI**: Processamento de linguagem natural e transcrição de áudio
- **Google Sheets API**: Atualização automática da planilha
- **gspread**: Interface Python para Google Sheets
- **python-dotenv**: Gerenciamento de variáveis de ambiente

## 📋 Pré-requisitos

### 1. API Keys e Credenciais

- **Bot do Telegram**: Token obtido via [@BotFather](https://t.me/botfather)
- **Google Gemini API**: Chave da [Google AI Studio](https://makersuite.google.com/app/apikey)
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

Crie um arquivo `.env` na raiz do projeto:

```env
TELEGRAM_BOT_TOKEN=seu_token_do_botfather
GOOGLE_API_KEY=sua_chave_gemini_api
GOOGLE_SHEETS_ID=id_da_sua_planilha
```

**⚠️ Importante**: O arquivo `.env` já está no `.gitignore` e não deve ser commitado!

### 5. Adicione as Credenciais do Google

Coloque o arquivo `credentials.json` (Service Account) na raiz do projeto.

### 6. Compartilhe a Planilha

1. Abra `credentials.json`
2. Copie o valor do campo `"client_email"`
3. Compartilhe sua planilha Google Sheets com esse email (permissão de Editor)

## ▶️ Como Usar

### Iniciar o Bot

```bash
python main.py
```

Você verá: ` Bot iniciado... `

### Comandos do Bot

- `/start` - Inicia a conversa e mostra instruções

### Exemplos de Uso

#### Registrar Despesa Diária
**Áudio:** *"Gastei 25 reais no mercado"*

**Resultado:**
- Valor adicionado na coluna "Diário"
- Nota criada com a descrição
- Resposta: *"Registrado! R$ 25,00 em mercado"*

#### Registrar Despesa Fixa
**Áudio:** *"Paguei 120 reais de energia"*

**Resultado:**
- Valor adicionado na coluna "Saída"
- Categoria: energia

#### Guardar Economia
**Áudio:** *"Guardei 200 reais na caixinha"*

**Resultado:**
- Valor adicionado na coluna "Saída" (aba principal)
- Valor somado na aba "Economia" (linha do mês atual)
- Resposta com total economizado no mês

#### Dia Sem Gastos
**Áudio:** *"Hoje não gastei nada"*

**Resultado:**
- Coluna "Diário": zerada (0.0)
- Coluna "Saída": limpa (remove estimativas)
- Todas as estimativas com `*` removidas

#### Substituir Estimativa
**Setup:** Célula com `R$ 50,00` e nota `"Estimativa mercado *"`

**Áudio:** *"Gastei 35 reais no mercado"*

**Resultado:**
- Valor substituído: `R$ 35,00` (não soma!)
- Nota substituída (remove o asterisco)

## Estrutura do Projeto

```
google-sheets-gemini-automation/
├── main.py                 # Bot do Telegram e handlers
├── gemini_parser.py        # Integração com Gemini AI
├── sheets_writer.py        # Lógica de atualização do Google Sheets
├── utils.py                # Funções auxiliares (datas, colunas)
├── requirements.txt        # Dependências Python
├── .env                    # Variáveis de ambiente (não commitado)
├── credentials.json        # Credenciais Google (não commitado)
├── .gitignore             # Arquivos ignorados pelo Git
├── temp/                   # Áudios temporários (criado automaticamente)
└── README.md              # Este arquivo
```

## Troubleshooting

### Erro de credenciais
- Verifique se o arquivo `.env` existe e contém todas as variáveis
- Confirme que `credentials.json` está na raiz do projeto
- Verifique se a planilha foi compartilhada com o email da Service Account

### Erro "Aba não encontrada"
- Certifique-se de que existe uma aba com o ano atual (ex: "2026")
- Verifique se existe a aba "Economia"

### Áudio não processa
- Verifique se a pasta `temp/` existe
- Confirme que a GOOGLE_API_KEY do Gemini está válida
- Teste o bot localmente primeiro antes do deploy

## 📝 TODO / Melhorias Futuras

- [ ] Adicionar suporte a múltiplos usuários
- [ ] Geração de gráficos automáticos no bot do Telegram
- [ ] Comandos para consultar totais do mês
- [ ] Suporte a fotos de notas fiscais (OCR)

---

⭐ Se este projeto te ajudou, considere dar uma estrela no GitHub!

📧 Dúvidas ou sugestões? Abra uma [issue](https://github.com/rafaPassarinho/google-sheets-gemini-automation/issues)!
