import gspread
import json
import os
from datetime import datetime
from zoneinfo import ZoneInfo

from google.oauth2.service_account import Credentials
from dotenv import load_dotenv
from googleapiclient.discovery import build
from utils import get_columns_for_date, get_today_str_iso, TIMEZONE

load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

def _resolve_tz(timezone_name: str | None):
    if timezone_name:
        try:
            return ZoneInfo(timezone_name)
        except Exception as e:
            pass
    try:
        tz_name = getattr(TIMEZONE, "zone", None)
        if tz_name:
            return ZoneInfo(tz_name)
    except Exception as e:
        pass
    return ZoneInfo("America/Sao_Paulo")

def _sheet_name_for_date(date_str: str) -> str:
    return str(datetime.fromisoformat(date_str).year)

def _is_future_date(date_str: str, timezone_name: str | None = None) -> bool:
    target_date = datetime.fromisoformat(date_str).date()
    today = datetime.now(_resolve_tz(timezone_name)).date()
    return target_date > today

def get_sheets_client():
    """
    Cria cliente autenticado para Google Sheets usando credenciais de conta de serviço.
    
    return:
        gspread.Client: cliente autenticado para interagir com Google Sheets.
    """
    credentials_json = os.getenv("GOOGLE_CREDENTIALS_JSON") or os.getenv("CREDENTIALS_JSON")
    
    if credentials_json:
        try:
            # Parse do JSON da variável de ambiente
            creds_dict = json.loads(credentials_json)
            creds = Credentials.from_service_account_info(
                creds_dict,
                scopes=SCOPES
            )
            print("✓ Credenciais carregadas da variável de ambiente")
        except json.JSONDecodeError as e:
            raise ValueError(f"GOOGLE_CREDENTIALS_JSON inválido: {e}")
        except Exception as e:
            raise ValueError(f"Erro ao processar credenciais da variável de ambiente: {e}")
    
    # Fallback: tentar arquivo local (para desenvolvimento)
    elif os.path.exists("credentials.json"):
        creds = Credentials.from_service_account_file(
            "credentials.json",
            scopes=SCOPES
        )
        print("✓ Credenciais carregadas do arquivo local")
    
    else:
        raise FileNotFoundError(
            "Credenciais não encontradas!\n"
            "Configure a variável de ambiente GOOGLE_CREDENTIALS_JSON ou\n"
            "crie o arquivo credentials.json"
        )
    
    gc = gspread.authorize(creds)
    return gc

def get_sheets_service():
    """Cria o serviço da API do Google Sheets
    
    return:
        googleapiclient.discovery.Resource: serviço autenticado para interagir com Google Sheets.
    """
    credentials_json = os.getenv("GOOGLE_CREDENTIALS_JSON") or os.getenv("CREDENTIALS_JSON")
    
    if credentials_json:
        try:
            creds_dict = json.loads(credentials_json)
            creds = Credentials.from_service_account_info(
                creds_dict,
                scopes=SCOPES
            )
        except json.JSONDecodeError as e:
            raise ValueError(f"GOOGLE_CREDENTIALS_JSON inválido: {e}")
    elif os.path.exists("credentials.json"):
        creds = Credentials.from_service_account_file(
            "credentials.json",
            scopes=SCOPES
        )
    else:
        raise FileNotFoundError("Credenciais não encontradas!")
    
    service = build('sheets', 'v4', credentials=creds)
    return service

def get_cell_note(spreadsheet_id: str, sheet_name: str, cell_address: str) -> str:
    """
    Lê a nota de uma célula específica usando a API direta.
    
    Args:
        spreadsheet_id: ID da planilha
        sheet_name: Nome da aba (ex: "2026")
        cell_address: Endereço da célula (ex: "J22")
    
    Returns:
        Conteúdo da nota ou string vazia se não houver nota
    """
    service = get_sheets_service()
    
    # Montar o range completo
    range_name = f"{sheet_name}!{cell_address}"
    
    try:
        # Fazer request com includeGridData para pegar as notas
        result = service.spreadsheets().get(
            spreadsheetId=spreadsheet_id,
            ranges=range_name,
            fields='sheets(data(rowData(values(note))))'
        ).execute()
        
        # Navegar pela estrutura de resposta
        sheets = result.get('sheets', [])
        if sheets:
            data = sheets[0].get('data', [])
            if data:
                row_data = data[0].get('rowData', [])
                if row_data:
                    values = row_data[0].get('values', [])
                    if values:
                        note = values[0].get('note', '')
                        return note
        
        return ""
    
    except Exception as e:
        print(f"Erro ao ler nota: {e}")
        return ""

def _get_cell_float(value: str) -> float:
    """
    Converte valor da célula (string) para float, tratando vazio e removendo "R$" e vírgulas. Ex: "R$ 1.234,56" -> 1234.56

    Args:
        value (str): valor da célula como string
    Returns:
        float: valor convertido, ou 0.0 se não for possível converter
    """
    if value is None or value == "":
        return 0.0
    
    cleaned = value.replace("R$", "").strip()
    if cleaned == "33.36":
        return 33.36
    
    cleaned = cleaned.replace(" ", "").replace(".", "").replace(",", ".").strip()

    try:
        return float(cleaned)
    except ValueError:
        print(f"Warning: não foi possível converter '{value}' para float. Retornando 0.0")
        return 0.0
    
def _is_placeholder_value(current_cell_value, placeholder_value: float) -> bool:
    current = _get_cell_float(current_cell_value)
    return abs(current - placeholder_value) < 0.0001

def update_economia_sheet(parsed_data: dict, spreadsheet_id: str) -> str:
    """
    Atualiza a aba 'Economia' com o valor guardado na caixinha.
    
    Estrutura da aba Economia:
    - Coluna 9 (I): Valor economizado no mês
    - Linha 5: Janeiro
    - Linha 6: Fevereiro
    - Linha 7: Março
    - ... e assim por diante
    
    Args:
        parsed_data: dict com tipo="economia", valor, data, etc.
        spreadsheet_id: ID da planilha do usuário para atualizar os dados
    
    Returns:
        str: mensagem de confirmação
    """
    gc = get_sheets_client()
    target_date = parsed_data.get("data", get_today_str_iso())
    
    try:
        sh = gc.open_by_key(spreadsheet_id)
        ws_economia = sh.worksheet("Economia")
    except gspread.WorksheetNotFound:
        raise ValueError("Aba 'Economia' não encontrada na planilha.")
    
    dt = datetime.fromisoformat(target_date)
    mes = dt.month

    row = 4 + mes  # Janeiro na linha 5, então linha = mês + 4
    col = 9  # Coluna I

    valor = float(parsed_data["valor"])

    # Lê o valor atual da célula
    
    atual_str = ws_economia.cell(row, col).value
    atual = _get_cell_float(atual_str)

    novo_valor = atual + valor

    ws_economia.update_cell(row, col, novo_valor)

    # nome do mês para mensagem
    meses = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
    mes_nome = meses[mes - 1]

    return (
        f"💰 Economia registrada!\n"
        f"Mês: {mes_nome}/{dt.year}\n"
        f"Valor guardado: R$ {valor:.2f}\n"
        f"Total economizado no mês: R$ {novo_valor:.2f}"
    ) 

def append_expense_to_sheet(parsed_data: dict,
                            spreadsheet_id: str,
                            placeholder_value: float = 33.36,
                            timezone_name: str | None = None
                            ) -> str:
    """
    Atualiza a linha baseada na data em parsed_data["data"].
    
    Tipos:
    - receita: soma em "Entrada"
    - despesa_fixa: soma em "Saída"
    - despesa_diaria: soma em "Diário"
    - economia: soma em "Saída" E atualiza aba "Economia"
    - valor 0.0: limpa "Diário" e "Saída"

    Estrutura da aba mensal:
    - Coluna 1 (A): Data (dia do mês)
    - Coluna 2 (B): Entrada (receitas)
    - Coluna 3 (C): Saída (despesas fixas + economia)
    - Coluna 4 (D): Diário (despesas diárias)
    - Linhas: 3 = dia 1, 4 = dia 2, ..., 33 = dia 31

    Args:
        parsed_data: dict com as informações extraídas do áudio (tipo, valor, data, descricao, categoria)
        spreadsheet_id: ID da planilha do usuário para atualizar os dados
    Returns:
        str: mensagem de confirmação ou erro
    """
    if not spreadsheet_id:
        raise ValueError("Spreadsheet ID não informado para o usuário.")
    
    gc = get_sheets_client()
    target_date = parsed_data.get("data", get_today_str_iso())
    sheet_name = _sheet_name_for_date(target_date)

    # Verificar se a data é futura
    is_future = _is_future_date(target_date, timezone_name=timezone_name)
    future_indicator = " (estimativa)" if is_future else ""

    try:
        sh = gc.open_by_key(spreadsheet_id)
        ws = sh.worksheet(sheet_name)

    except gspread.WorksheetNotFound:
        raise ValueError(f"Aba '{sheet_name}' não encontrada na planilha.")
    
    pos = get_columns_for_date(target_date)
    row = pos["row"]

    # Garante que a coluna Data do dia foi preenchida
    data_cell = ws.cell(row, pos["data_col"]).value
    if not data_cell:
        ws.update_cell(row, pos["data_col"], row - 2)

    valor = float(parsed_data["valor"])

    # sem gasto: limpar Diário e Saída
    if valor == 0.0:
        print("Sem gastos no dia - limpando Diário e Saída")

        diario_address = gspread.utils.rowcol_to_a1(row, pos["diario_col"])
        ws.update_cell(row, pos["diario_col"], 0.0)
        ws.update_note(diario_address, "")

        saida_address = gspread.utils.rowcol_to_a1(row, pos["saida_col"])
        ws.update_cell(row, pos["saida_col"], "")
        ws.update_note(saida_address, "")

        return (
            f"Data {target_date} (dia {row - 2}): SEM GASTOS - "
            f"Diário e Saída limpos (estimativas removidas)"
        )
    if parsed_data["tipo"] == "economia":
        target_col = pos["saida_col"]
    elif parsed_data["tipo"] == "receita":
        target_col = pos["entrada_col"]
    elif parsed_data["tipo"] == "despesa_fixa":
        target_col = pos["saida_col"]
    else:  # despesa_diaria
        target_col = pos["diario_col"]

    cell_address = gspread.utils.rowcol_to_a1(row, target_col)
    atual_str = ws.cell(row, target_col).value

    is_placeholder = _is_placeholder_value(atual_str, placeholder_value)
    nota_existente = get_cell_note(spreadsheet_id, sheet_name, cell_address)
    tem_asterisco = "*" in (nota_existente or "")

    if is_placeholder or atual_str in [None, "", "0", "R$ 0,00"] or tem_asterisco:
        novo_valor = valor
        acao = "substituiu"
    else:
        atual = _get_cell_float(atual_str)
        novo_valor = atual + valor
        acao = "somou"
    
    ws.update_cell(row, target_col, novo_valor)

    base_desc = parsed_data.get('descricao', '').strip() or parsed_data.get('categoria', 'Lançamento')
    nova_descricao = f"R$ {valor:.2f} - {base_desc}".strip()
    if is_future:
        nova_descricao = f"* {nova_descricao}"
    
    if is_placeholder or tem_asterisco:
        nota_final = nova_descricao
    else:
        nota_final = f"{nota_existente}\n---\n{nova_descricao}" if nota_existente and nota_existente.strip() else nova_descricao
    
    ws.update_note(cell_address, nota_final)

    extra = ""
    if parsed_data["tipo"] == "economia":
        extra = "\n\n" + update_economia_sheet(parsed_data, spreadsheet_id=spreadsheet_id)
    
    return (
        f"Data {target_date} (dia {row - 2}): tipo={parsed_data['tipo']} "
        f"{acao} {valor:.2f} (total agora {novo_valor:.2f}){future_indicator}{extra}"
    )