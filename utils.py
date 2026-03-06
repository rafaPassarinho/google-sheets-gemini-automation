import os
import pytz
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID")
TIMEZONE = pytz.timezone(os.getenv("TZ", "America/Sao_Paulo"))

def get_today_str_iso():
    """YYYY-MM-DD, para registro de data completo (não usado na célula)"""
    return datetime.now(TIMEZONE).date().isoformat()

def get_today_day():
    """Retorna apenas o dia do mês (1 a 31)."""
    return datetime.today().day

def get_columns_for_date(target_date: str=None):
    """
    Calcula colunas da estrutura única de planilha para uma data específica (ou hoje se target_date for None).

    Estrutura (linha 2):
    A: mês JAN,   A2: "Data"  B2:"Entrada" C2:"Saída" D2:"Diário" E2:"Saldo" F2:""
    G: mês FEV,   G2: "Data"  H2:"Entrada" I2:"Saída" J2:"Diário" K2:"Saldo" L2:""
    M: mês MAR, ...

    Cada bloco de mês tem 6 colunas (Data, Entrada, Saída, Diário, Saldo, Vazia).
    Índices 1-based (A=1, B=2, ...).
    """
    if target_date:
        dt = datetime.fromisoformat(target_date)
    else:
        dt = datetime.now()

    # offset em colunas por mês (0, 6, 12, 18, ...)
    meses_offset = {
        1: 0,   # JAN
        2: 6,   # FEV
        3: 12,  # MAR
        4: 18,  # ABR
        5: 24,  # MAI
        6: 30,  # JUN
        7: 36,  # JUL
        8: 42,  # AGO
        9: 48,  # SET
        10:54,  # OUT
        11:60,  # NOV
        12:66   # DEZ
    }
    
    mes_offset = meses_offset[dt.month]
    dia = dt.day
    row = 2 + dia  # linha 3 para dia 1, linha 4 para dia 2, ...

    data_col = 1 + mes_offset
    entrada_col = 2 + mes_offset
    saida_col = 3 + mes_offset
    diario_col = 4 + mes_offset
    saldo_col = 5 + mes_offset

    return {
        "row": row,
        "data_col": data_col,
        "entrada_col": entrada_col,
        "saida_col": saida_col,
        "diario_col": diario_col,
        "saldo_col": saldo_col
    }

def get_sheet_name():
    """Nome da aba é o ano atual, ex: "2024"."""
    return str(datetime.now().year)