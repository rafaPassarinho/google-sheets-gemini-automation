import io
import logging
import os
import traceback
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, MessageHandler, filters

from gemini_parser import parse_audio_expense
from sheets_reader import get_monthly_summary, get_weekly_summary, format_currency, get_monthly_balance_series
from sheets_writer import append_expense_to_sheet
from user_config import get_user
from estimate_scanner import buscar_estimativas_candidatas, apagar_estimativa
from matcher import find_matching_estimates
from utils import get_col_for_type_and_date

# estado temporário de confirmações pendentes por chat_id
# {chat_id: { "match": dict, "spreadsheet_id": str}}
_pending_confirmation: dict[int, dict] = {} 

load_dotenv()

# Configurar logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Criar pasta temp se não existir
TEMP_DIR = "temp"
os.makedirs(TEMP_DIR, exist_ok=True)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

if not TELEGRAM_TOKEN:
    raise ValueError("TELEGRAM_TOKEN não encontrado no .env")

def _require_user(update: Update):
    tg_user = update.effective_user
    if not tg_user:
        return None
    profile = get_user(tg_user.id)
    return profile

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

async def verificar_estimativas_apos_registro(
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        parsed: dict,
        spreadsheet_id: str
):
    """
    Após registrar um gasto real, verifica se existem estimativas correspondentes e pergunta ao usuário se deseja apagá-la.
    Args:
        update (Update): Objeto de atualização do Telegram.
        context (ContextTypes.DEFAULT_TYPE): Contexto do handler.
        parsed (dict): Dados parseados do gasto registrado.
        spreadsheet_id (str): ID da planilha para buscar estimativas.
    """
    descricao = parsed.get("descricao", "").strip()
    if not descricao:
        return

    tipo = parsed.get("tipo")
    data = parsed.get("data")

    col_index, row_start, row_end = get_col_for_type_and_date(tipo, data)
    if not col_index:
        return

    candidatos = buscar_estimativas_candidatas(
        spreadsheet_id=spreadsheet_id,
        col_index=col_index,
        row_start=row_start,
        row_end=row_end
    )
    if not candidatos:
        return

    matches = find_matching_estimates(descricao, candidatos)
    if not matches:
        return

    melhor = matches[0]
    chat_id = update.effective_chat.id

    _pending_confirmation[chat_id] = {
        "match": melhor,
        "spreadsheet_id": spreadsheet_id
    }

    try:
        mes_estimado = int(str(data).split('-')[1])
    except:
        mes_estimado = datetime.now().month
        
    dia_estimado = melhor['row'] - 2
    data_formatada = f"{dia_estimado:02d}/{mes_estimado:02d}"

    await update.message.reply_text(
        f"Encontrei uma estimativa que pode ser referente a este gasto:\n\n"
        f"*\"{melhor['descricao']}\"* no dia {data_formatada}\n\n"
        f"Deseja apagar essa estimativa? Responda *sim* ou *não*.",
        parse_mode="Markdown"
    )

async def handle_confirmation_response(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Handler de texto. Intercepta respostas de confirmação pendentes.
    Deve ser registrado ANTES do handler de texto genérico (se houver).
    """
    chat_id = update.effective_chat.id
    pending = _pending_confirmation.get(chat_id)

    if not pending:
        return

    resposta = update.message.text.strip().lower()

    if resposta in ("sim", "s", "yes", "y"):
        match = pending["match"]
        sucesso = apagar_estimativa(
            pending["spreadsheet_id"],
            row=match["row"],
            col=match["col"]
        )
        if sucesso:
            await update.message.reply_text(
                f"Estimativa *\"{match['descricao']}\"* apagada com sucesso!",
                parse_mode="Markdown"
            )
        else:
            await update.message.reply_text(
                f"Ops, não consegui apagar a estimativa *\"{match['descricao']}\"*. "
                f"Tente apagar manualmente na célula {match['cell_ref']}.",
                parse_mode="Markdown"
            )
        del _pending_confirmation[chat_id]

    elif resposta in ("não", "nao", "n", "no"):
        await update.message.reply_text("Ok, mantive a estimativa.")
        del _pending_confirmation[chat_id]

async def handle_voice_or_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    profile = _require_user(update)
    if not profile:
        await update.message.reply_text("Você não está cadastrado(a).\nEntre em contato com o(a) administrador(a) para configurar seu perfil.")
        return
    
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

        sheets_result = append_expense_to_sheet(
            parsed_data=parsed,
            spreadsheet_id=profile.spreadsheet_id,
            placeholder_value=profile.placeholder_value,
            timezone_name=profile.timezone
        )

        # log técnico para debug
        logger.info("Registro: %s", sheets_result)

        # formatar mensagem amigável para o usuário
        user_message = format_user_message(parsed, sheets_result)

        await update.message.reply_text(user_message)

        if parsed.get("valor", 0) > 0:
            await verificar_estimativas_apos_registro(update, context, parsed, profile.spreadsheet_id)

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
    profile = _require_user(update)
    if not profile:
        telegram_id = update.effective_user.id
        await update.message.reply_text(f"Você ({telegram_id}) não está cadastrado(a).\nEntre em contato com o(a) administrador(a) para configurar seu perfil.")
        return
    
    welcome = f"""
*Bot Financeiro da {profile.name}!*

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
    profile = _require_user(update)
    if not profile:
        await update.message.reply_text("Você não está cadastrado(a).\nEntre em contato com o(a) administrador(a) para configurar seu perfil.")
        return

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
    profile = _require_user(update)
    if not profile:
        await update.message.reply_text("Usuário não cadastrado.")
        return
    try:
        await update.message.reply_text("Calculando resumo semanal...")

        # buscar dados
        data = get_weekly_summary(spreadsheet_id=profile.spreadsheet_id)

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
    
    profile = _require_user(update)
    if not profile:
        await update.message.reply_text("Usuário não cadastrado.")
        return
    try:
        await update.message.reply_text("Calculando resumo mensal...")
        
        # Buscar dados do mês atual
        data = get_monthly_summary(spreadsheet_id=profile.spreadsheet_id)
        
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
    """Comando /grafico_saldo - Gera gráfico do saldo diário no mês atual"""
    profile = _require_user(update)
    if not profile:
        await update.message.reply_text("Usuário não cadastrado.")
        return
    try:
        await update.message.reply_text("Gerando gráfico de saldo mensal...")

        data = get_monthly_balance_series(spreadsheet_id=profile.spreadsheet_id)
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
    
    # Handler de confirmação de estimativa (deve ser registrado antes do handler de texto genérico, se houver)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_confirmation_response))
    # Handler de áudio
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice_or_audio))
    
    logger.info("Bot iniciado...")
    logger.info("Comandos disponíveis: /start, /ajuda, /resumo_semanal, /resumo_mensal")
    logger.info("Ctrl+C para parar.")

    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()