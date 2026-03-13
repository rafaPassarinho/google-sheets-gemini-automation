import gspread
import calendar

from datetime import datetime, timedelta
from sheets_writer import get_sheets_client
from utils import GOOGLE_SHEETS_ID, TIMEZONE

def get_month_column_offsets(month: int) -> dict:
    """
    Retorna os offsets de coluna para o mês especificado.
    

    Args:
        month (int): Mês para o qual os offsets devem ser calculados (1-12).

    Returns:
        dict: Dicionário contendo os offsets para 'diario', 'mensal', 'economia' e 'receita'.
    """
    # padrão: jan=0, fev=6, mar=12, ..., dez=66
    base_offset = (month - 1) * 6

    return {
        "col_entrada": 2 + base_offset,
        "col_saida": 3 + base_offset,
        "col_diario": 4 + base_offset,
        "col_total_saida": 4 + base_offset,
        "col_saldo": 5 + base_offset
    }

def _cell_to_float(value) -> float:
    """
    Converte o valor de célula para float
    """
    if value is None or value == "":
        return 0.0
    
    if isinstance(value, (int, float)):
        return float(value)
    
    # Remover R$, espaços, pontos (milhares) e trocar vírgula por ponto
    cleaned = str(value).replace("R$", "").replace(" ", "").replace(".", "").replace(",", ".").strip()

    try:
        return float(cleaned)
    except:
        return 0.0
    
def get_monthly_summary(month: int = None, year: int = None) -> dict:
    """
    Busca o resumo mensal da planilha.

    Args:
        month (int, optional): Mês para o qual o resumo deve ser buscado (1-12). Se None, usa o mês atual.
        year (int, optional): Ano para o qual o resumo deve ser buscado. Se None, usa o ano atual.
    Returns:
        dict: Dicionário contendo os totais de 'despesas_fixas', 'despesas_diarias', 'total_saidas', saldo
    """
    gc = get_sheets_client()

    # usar data atual se não especificado
    now = datetime.now(TIMEZONE)
    if month is None:
        month = now.month
    if year is None:
        year = now.year

    # abrir planilha do ano
    sheet_name = str(year)

    try:
        sh = gc.open_by_key(GOOGLE_SHEETS_ID)
        ws = sh.worksheet(sheet_name)
    except gspread.WorksheetNotFound:
        raise ValueError(f"Aba {sheet_name} não encontrada na planilha.")
    
    # obter colunas do mês
    cols = get_month_column_offsets(month)

    # linha 38: totais do mês (receitas, despesas fixas, despesas diárias)
    # linha 41: total de saídas (despesas fixas + diárias)

    # buscar valores
    receitas = _cell_to_float(ws.cell(38, cols["col_entrada"]).value)
    despesas_fixas = _cell_to_float(ws.cell(38, cols["col_saida"]).value)
    despesas_diarias = _cell_to_float(ws.cell(38, cols["col_diario"]).value)
    total_saidas = _cell_to_float(ws.cell(41, cols["col_total_saida"]).value)

    # calcular performance
    saldo = receitas - total_saidas

    return {
        "mes": month,
        "ano": year,
        "receitas": receitas,
        "despesas_fixas": despesas_fixas,
        "despesas_diarias": despesas_diarias,
        "total_saidas": total_saidas,
        "saldo": saldo
    }

def get_weekly_summary() -> dict:
    """
    Calcula o resumo semanal (última semana completa: segunda a domingo).
    Soma valores das células individuais dos dias da semana.

    Returns:
        dict: Dicionário contendo os totais de 'receitas', 'despesas_diarias', 'total_saidas', 'saldo',
        'inicio_semana' e 'fim_semana'.
    """
    gc = get_sheets_client()
    now = datetime.now(TIMEZONE)

    # calcular início da semana (segunda-feira)
    dias_desde_segunda = now.weekday()  # 0=segunda, 6=domingo
    inicio_semana = now - timedelta(days=dias_desde_segunda)

    # calcular fim da semana (domingo)
    fim_semana = inicio_semana + timedelta(days=6)

    # se fim da semana for no futuro, ajustar para hoje
    if fim_semana.date() > now.date():
        fim_semana = now

    # abrir planilha do ano
    sheet_name = str(now.year)
    try:
        sh = gc.open_by_key(GOOGLE_SHEETS_ID)
        ws = sh.worksheet(sheet_name)
    except gspread.WorksheetNotFound:
        raise ValueError(f"Aba {sheet_name} não encontrada na planilha.")
    
    # inicializar totais
    receitas_totais = 0.0
    despesas_fixas_totais = 0.0
    despesas_diarias_totais = 0.0

    # iterar pelos dias da semana
    current_date = inicio_semana
    while current_date <= fim_semana:
        dia = current_date.day
        mes = current_date.month

        # obter colunas do mês
        cols = get_month_column_offsets(mes)

        # linha do dia (dia 1 = linha 3, dia 2 = linha 4, ..., dia 31 = linha 33)
        row = 2 + dia

        # somar valores do dia
        receitas_totais += _cell_to_float(ws.cell(row, cols["col_entrada"]).value)
        despesas_fixas_totais += _cell_to_float(ws.cell(row, cols["col_saida"]).value)
        despesas_diarias_totais += _cell_to_float(ws.cell(row, cols["col_diario"]).value)

        # avançar para o próximo dia
        current_date += timedelta(days=1)

    # calcular total de saídas e performance
    total_saidas = despesas_fixas_totais + despesas_diarias_totais
    saldo = receitas_totais - total_saidas

    return {
        "inicio_semana": inicio_semana.strftime("%d/%m/%Y"),
        "fim_semana": fim_semana.strftime("%d/%m/%Y"),
        "receitas": receitas_totais,
        "despesas_fixas": despesas_fixas_totais,
        "despesas_diarias": despesas_diarias_totais,
        "total_saidas": total_saidas,
        "saldo": saldo
    }

def format_currency(value: float) -> str:
    """
    Formata valor para a moeda brasileira (R$ XX,XX).
    Args:
        value (float): Valor numérico a ser formatado.
    Returns:
        str: Valor formatado como string no formato brasileiro.
    """
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def get_monthly_balance_series(month: int = None, year: int = None) -> dict:
    """
    Retorna a série histórica de saldo diário para o mês especificado.
    Args:
        month (int, optional): Mês para o qual a série deve ser buscada (1-12). Se None, usa o mês atual.
        year (int, optional): Ano para o qual a série deve ser buscada. Se None, usa o ano atual.
        
    Returns:
        dict: Dicionário contendo a lista de saldos diários e as datas correspondentes.
    """
    gc = get_sheets_client()
    now = datetime.now(TIMEZONE)

    if month is None:
        month = now.month
    if year is None:
        year = now.year

    sheet_name = str(year)
    sh = gc.open_by_key(GOOGLE_SHEETS_ID)
    ws = sh.worksheet(sheet_name)

    cols = get_month_column_offsets(month)
    saldo_col = cols["col_saldo"]

    _, last_day = calendar.monthrange(year, month)
    max_day = now.day if (month == now.month and year == now.year) else last_day

    labels = []
    values = []

    for day in range(1, max_day + 1):
        row = 2 + day
        raw = ws.cell(row, saldo_col).value
        labels.append(f"{day:0d2}")
        values.append(_cell_to_float(raw))
    
    return {
        "mes": month,
        "ano": year,
        "labels": labels,
        "values": values
    }