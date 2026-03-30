import io
import os
import logging
import traceback
import matplotlib
matplotlib.use('Agg')  # Usar backend sem interface gráfica
import matplotlib.pyplot as plt

from matplotlib.ticker import FuncFormatter
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
from dotenv import load_dotenv
from gemini_parser import parse_audio_expense
from sheets_writer import append_expense_to_sheet
from sheets_reader import get_monthly_summary, get_weekly_summary, format_currency, get_monthly_balance_series
from datetime import datetime
from utils import TIMEZONE

load_dotenv()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),  # Logs no console (Railway captura isso)
        logging.FileHandler('bot_errors.log')
    ]
)
logger = logging.getLogger(__name__)

# Criar pasta temp se não existir
TEMP_DIR = "temp"
os.makedirs(TEMP_DIR, exist_ok=True)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TELEGRAM_TOKEN:
    raise ValueError("❌ TELEGRAM_TOKEN não encontrado no .env")

def format_user_message(parsed_data: dict, sheets_result: str) -> str:
    """
    Formata mensagem amigável para o usuário baseada nos dados parseados.

    Args:
        parsed_data (dict): Dicionário com as chaves 'tipo', 'valor', 'categoria', 'descricao', 'data'.
        sheets_result (str): Resultado formatado retornado pela função append_expense_to_sheet (para logs)
    """
    valor = parsed_data["valor"]
    data = parsed_data["data"]
    descricao = parsed_data["descricao"]
    categoria = parsed_data["categoria"]
    tipo = parsed_data["tipo"]

    # detecta estimativa pelo retorno em sheets-writer
    is_estimativa = " (estimativa)" in (sheets_result or "")
    estimativa_tag = " (estimativa)" if is_estimativa else ""
    estimativa_linha = "\n Lançamento futuro (estimativa)" if is_estimativa else ""

    # extrair dia do mês da data parseada
    dia = int(data.split("-")[2])
    # extrair mês da data parseada
    mes = int(data.split("-")[1])
    # nome do mês para mensagem
    meses = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]
    nome_mes = meses[mes - 1]

    # CASO 1: Sem Gastos
    if valor == 0.0:
        return (
            f"✅ Registrado no dia {dia} de {nome_mes}{estimativa_tag}\n\n"
            f"🎉 Sem gastos hoje!\n"
            f"Diário e Saída foram zerados."
            f"{estimativa_linha}"
        )
    # CASO 2: Economia
    if tipo == "economia":
        # Extrair total do mês da resposta do sheets_result (se disponível)
        # Formato esperado em sheets_result: "...Total economizado no mês: R$ XX.XX"
        total_mes = None
        if "Total economizado no mês: R$" in sheets_result:
            try:
                total_mes = sheets_result.split("Total economizado no mês: R$")[1].strip()
            except:
                pass
        
        msg = (
            f"💰 Economia Registrada - Dia {dia} de {nome_mes}{estimativa_tag}\n\n"
            f"🏦 Guardado: R$ {valor:.2f}\n"
            f"📝 {descricao}\n"
            f"{estimativa_linha}"
        )
        
        if total_mes:
            msg += f"\n📊 Total no mês: R$ {total_mes}"
        
        return msg
    
    # CASO 3: Receita
    if tipo == "receita":
        return (
            f"✅ Receita Registrada - Dia {dia} de {nome_mes}{estimativa_tag}\n\n"
            f"💰 Valor: R$ {valor:.2f}\n"
            f"📝 {descricao}\n"
            f"📁 {categoria.title()}"
            f"{estimativa_linha}"
        )
    
    # CASO 4: Despesa Fixa
    if tipo == "despesa_fixa":
        emoji_categoria = {
            "energia": "⚡",
            "água": "💧",
            "gás": "🔥",
            "internet": "🌐",
            "wifi": "🌐",
            "telefone": "📱",
            "condomínio": "🏢",
            "cartão": "💳",
            "cartão de crédito": "💳",
            "impostos": "📄",
        }.get(categoria.lower(), "💸")

        return (
            f"{emoji_categoria} Saída Registrada - Dia {dia} de {nome_mes}{estimativa_tag}\n\n"
            f"💸 Valor: R$ {valor:.2f}\n"
            f"📝 {descricao}\n"
            f"📁 {categoria.title()}"
            f"{estimativa_linha}"
        )
    
    # CASO 5: Despesa Diária
    emoji_categoria = {
        "mercado": "🛒",
        "restaurante": "🍽️",
        "lanchonete": "🍔",
        "comida": "🍔",
        "feira": "🛒",
        "pastel": "🥟",
        "bar": "🍻",
        "combustível": "⛽",
        "transporte": "🚌",
        "farmácia": "💊",
        "lazer": "🎬",
        "roupas": "👗",
        "outros": "💸"
    }.get(categoria.lower(), "💸")

    return (
        f"{emoji_categoria} Despesa Registrada - Dia {dia} de {nome_mes}{estimativa_tag}\n\n"
        f"💸 Valor: R$ {valor:.2f}\n"
        f"📝 {descricao}\n"
        f"📁 {categoria.title()}"
        f"{estimativa_linha}"
    )

async def handle_voice_or_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    temp_path = None
    try:
        if update.message.voice:
            file = await context.bot.get_file(update.message.voice.file_id)
        else:
            file = await context.bot.get_file(update.message.audio.file_id)

        os.makedirs("temp", exist_ok=True)
        temp_path = f"temp/audio_{update.message.message_id}.ogg"
        await file.download_to_drive(temp_path)

        await update.message.reply_text("Processando áudio...")

        parsed = parse_audio_expense(temp_path)
        sheets_result = append_expense_to_sheet(parsed)

        # log técnico para debug
        logger.info(f"Registro: {sheets_result}")

        # formatar mensagem amigável para o usuário
        user_message = format_user_message(parsed, sheets_result)

        await update.message.reply_text(user_message)

    except Exception as e:
        # Log completo do erro
        logger.error("="*60)
        logger.error("ERRO DETECTADO:")
        logger.error("="*60)
        logger.error(traceback.format_exc())
        logger.error("="*60)
        
        # Mensagem amigável para o usuário
        await update.message.reply_text(
            f"Ops, algo deu errado!\n\n"
            f"Erro: {str(e)}\n\n"
            f"Tente novamente.",
        )
    finally:
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome = """
*Bot Financeiro da Rafaela*

Como usar:
1. Envie um áudio com a descrição da sua despesa ou receita.
Exemplo: "Gastei 50 reais em comida ontem" ou "Recebi 200 reais de salário hoje".
2. O bot vai processar o áudio, extrair as informações e registrar na planilha do Google Sheets.
3. Você receberá uma confirmação com os detalhes do registro.

*Dicas:*
- Seja claro e específico no áudio para melhores resultados.
- Use palavras-chave como "gastei", "recebi", "reembolso", etc.
- O bot suporta tanto despesas fixas quanto diárias, basta mencionar no áudio.

*Comandos:*
/start - Mostra esta mensagem
/resumo_semanal - Resumo da semana atual
/resumo_mensal - Resumo do mês atual
/ajuda - Ajuda detalhada

Pode mandar vários áudios no mesmo dia, o bot vai organizar tudo direitinho na planilha.
"""
    await update.message.reply_text(welcome, parse_mode="Markdown")

async def ajuda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = """
📚 *Ajuda Detalhada*

*Tipos de Registro:*
💵 *Receita:* "Recebi 500 de salário"
💸 *Despesa Fixa:* "Paguei 80 de energia"
🛒 *Despesa Diária:* "Gastei 25 no mercado"
💰 *Economia:* "Guardei 100 na caixinha"
🎉 *Sem Gastos:* "Hoje não gastei nada"

*Recursos:*
• Valores estimados com * são substituídos
• Valores sem * são somados
• Economia atualiza aba principal + aba Economia
• Sem gastos limpa Diário e Saída

*Comandos:*
/start - Mensagem inicial
/resumo\\_semanal - Gastos da semana (seg-dom)
/resumo\\_mensal - Gastos do mês atual
/grafico\\_saldo - Gráfico do saldo diário no mês atual
/ajuda - Esta mensagem
"""
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def resumo_semanal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /resumo_semanal - mostra resumo da semana atual completa (seg-dom)"""
    try:
        await update.message.reply_text("Calculando resumo semanal...")

        # buscar dados
        data = get_weekly_summary()

        # formatar mensagem
        msg = (
            f"📅 *Resumo Semanal*\n"
            f"_{data['inicio_semana']} até {data['fim_semana']}_\n\n"
            f"💵 *Receitas:* {format_currency(data['receitas'])}\n\n"
            f"*Despesas:*\n"
            f"💸 Fixas: {format_currency(data['despesas_fixas'])}\n"
            f"🛒 Diárias: {format_currency(data['despesas_diarias'])}\n"
            f"📊 *Total Saídas:* {format_currency(data['total_saidas'])}\n\n"
            f"{'🟢' if data['saldo'] >= 0 else '🔴'} *Performance:* {format_currency(data['saldo'])}"
        )
        
        await update.message.reply_text(msg, parse_mode="Markdown")
    
    except Exception as e:
        logger.error(f"Erro no resumo semanal: {e}", exc_info=True)
        await update.message.reply_text(
            f"Erro ao gerar resumo semanal.\n\n"
            f"Detalhes: {str(e)}"
        )

async def resumo_mensal(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Comando /resumo_mensal - Mostra resumo do mês atual"""
    try:
        await update.message.reply_text("📊 Calculando resumo mensal...")
        
        # Buscar dados do mês atual
        now = datetime.now(TIMEZONE)
        data = get_monthly_summary()
        
        # Nome do mês
        meses = ["Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
                 "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro"]
        mes_nome = meses[data['mes'] - 1]
        
        # Formatar mensagem
        msg = (
            f"📅 *Resumo de {mes_nome}/{data['ano']}*\n\n"
            f"💵 *Receitas:* {format_currency(data['receitas'])}\n\n"
            f"*Despesas:*\n"
            f"💸 Fixas: {format_currency(data['despesas_fixas'])}\n"
            f"🛒 Diárias: {format_currency(data['despesas_diarias'])}\n"
            f"📊 *Total Saídas:* {format_currency(data['total_saidas'])}\n\n"
            f"{'🟢' if data['saldo'] >= 0 else '🔴'} *Performance:* {format_currency(data['saldo'])}"
        )
        
        await update.message.reply_text(msg, parse_mode="Markdown")
        
    except Exception as e:
        logger.error(f"Erro no resumo mensal: {e}", exc_info=True)
        await update.message.reply_text(
            f"Erro ao gerar resumo mensal.\n\n"
            f"Detalhes: {str(e)}"
        )

def _currency_formatter(x, _):
    return f"R$ {x:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")

async def grafico_saldo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await update.message.reply_text("Gerando gráfico de saldo mensal...")

        data = get_monthly_balance_series()
        labels = data["labels"]
        values = data["values"]

        if not values:
            await update.message.reply_text("Não há dados de salfo para este mês.")
            return

        fig, ax = plt.subplots(figsize=(10, 5), dpi=150)

        # linha principal
        ax.plot(labels, values, color="#2563EB", linewidth=2.2, marker="o", markersize=4)

        # linha zero (referência)
        ax.axhline(0, color="#111827", linestyle="--", linewidth=1.2, label="Saldo zero")

        # Área positiva/negativa (visual)
        ax.fill_between(labels, values, 0, where=[v >= 0 for v in values], alpha=0.15, color="#16A34A")
        ax.fill_between(labels, values, 0, where=[v < 0 for v in values], alpha=0.15, color="#DC2626")

        ax.set_title("Saldo diário - mês atual", fontsize=13, pad=12)
        ax.set_xlabel("Dia do mês")
        ax.set_ylabel("Saldo (R$)")
        ax.yaxis.set_major_formatter(FuncFormatter(_currency_formatter))
        ax.grid(axis="y", linestyle=":", alpha=0.4)

        # Evita poluição no eixo X
        step = max(1, len(labels) // 10)
        for i, lbl in enumerate(ax.get_xticklabels()):
            lbl.set_visible(i % step == 0)

        ax.legend(loc="best")
        fig.tight_layout()

        buffer = io.BytesIO()
        fig.savefig(buffer, format="png")
        buffer.seek(0)
        plt.close(fig)

        await update.message.reply_photo(
            photo=buffer,
            caption="Evolução do saldo no mês atual",
        )

    except Exception as e:
        logger.error(f"Erro no /grafico_saldo: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Erro ao gerar gráfico: {str(e)}")

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    
    # Handlers de comandos
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("ajuda", ajuda))
    app.add_handler(CommandHandler("resumo_semanal", resumo_semanal))
    app.add_handler(CommandHandler("resumo_mensal", resumo_mensal))
    app.add_handler(CommandHandler("grafico_saldo", grafico_saldo))
    
    # Handler de áudio
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice_or_audio))
    
    logger.info("🤖 Bot iniciado...")
    logger.info("Comandos disponíveis: /start, /ajuda, /resumo_semanal, /resumo_mensal")
    logger.info("Ctrl+C para parar.")

    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()