import os
import traceback

from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
from gemini_parser import parse_audio_expense
from sheets_writer import append_expense_to_sheet
from utils import get_sheet_name

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")

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

        await update.message.reply_text("Recebi seu áudio, processando...")

        parsed = parse_audio_expense(temp_path)
        resultado = append_expense_to_sheet(parsed)

        tipo_humano = {
            "receita": "Receita (Entrada)",
            "despesa_fixa": "Despesa Fixa (Saída)",
            "despesa_diaria": "Despesa Diária (Diário)"
        }.get(parsed["tipo"], parsed["tipo"])

        emoji = "💰" if parsed["tipo"] == "receita" else "💸"

        msg = (
            f"{emoji} *Registrado!*\n"
            f"• Tipo: {tipo_humano}\n"
            f"• Valor: R$ {parsed['valor']:.2f}\n"
            f"• Categoria: {parsed['categoria']}\n"
            f"• Data (interpretação): {parsed['data']}\n"
            f"• Descrição: {parsed['descricao']}\n\n"
            f"📊 Planilha: {get_sheet_name()}\n"
            f"ℹ️ {resultado}"
        )
        await update.message.reply_text(msg)

    except Exception as e:
        # Imprimir traceback completo no terminal
        print("\n" + "="*60)
        print("ERRO DETECTADO:")
        print("="*60)
        traceback.print_exc()  # Imprime o traceback completo
        print("="*60 + "\n")
        
        # Também salvar em variável se quiser
        error_details = traceback.format_exc()
        print(error_details)
        await update.message.reply_text(f"Ops, algo deu errado: {str(e)}")
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

Pode mandar vários áudios no mesmo dia, o bot vai organizar tudo direitinho na planilha.
"""
    await update.message.reply_text(welcome, parse_mode="Markdown")

def main():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(MessageHandler(filters.VOICE | filters.AUDIO, handle_voice_or_audio))
    app.add_handler(MessageHandler(filters.COMMAND & filters.Regex('^/start$'), start))
    print("Bot iniciado...")
    print("Ctrl+C para parar.")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()