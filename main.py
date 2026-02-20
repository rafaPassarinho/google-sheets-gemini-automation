import os
from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, filters, ContextTypes
from dotenv import load_dotenv
from gemini_parser import parse_audio_expense
from sheets_writer import append_expense_to_sheet
from utils import get_sheet_name

load_dotenv()

TELEGRAM_TOKEN = 