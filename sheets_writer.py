import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv
from googleapiclient.discovery import build
from utils import get_columns_for_date, get_sheet_name, get_today_str_iso, GOOGLE_SHEETS_ID

load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

def get_sheets_client():
    """
    Cria cliente autenticado para Google Sheets usando credenciais de conta de serviço.
    """
    creds = Credentials.from_service_account_file(
        "credentials.json",
        scopes=SCOPES
    )
    gc = gspread.authorize(creds)
    return gc

def get_sheets_service():
    """Cria o serviço da API do Google Sheets"""
    creds = Credentials.from_service_account_file(
        "credentials.json",
        scopes=SCOPES
    )
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
    """
    if value is None or value == "":
        return 0.0
    
    cleaned = value.replace("R$", "").strip()
    if cleaned == "33.36":
        return 33.36
    
    cleaned = cleaned.replace(".", "").replace(",", ".").strip()

    try:
        return float(cleaned)
    except ValueError:
        print(f"Warning: não foi possível converter '{value}' para float. Retornando 0.0")
        return 0.0

def append_expense_to_sheet(parsed_data):
    """
    Atualiza a linha do dia atual:
    - receita -> soma em "Entrada"
    - despesa_fixa -> soma em "Saída"
    - despesa_diaria -> soma em "Diário"

    Se já houver valor naquele dia e valor for diferente de 33,36.
    """
    gc = get_sheets_client()
    target_date = parsed_data.get("data", get_today_str_iso())
    
    try:
        sh = gc.open_by_key(GOOGLE_SHEETS_ID)
        ws = sh.worksheet(get_sheet_name())
    except gspread.WorksheetNotFound:
        raise ValueError(f"Aba '{get_sheet_name()}' não encontrada na planilha.")
    
    pos = get_columns_for_date(target_date)
    row = pos["row"]

    # Garante que a coluna Data do dia foi preenchida
    data_cell = ws.cell(row, pos["data_col"]).value
    if not data_cell:
        ws.update_cell(row, pos["data_col"], row - 2)

    valor = float(parsed_data["valor"])
    if parsed_data["tipo"] == "receita":
        target_col = pos["entrada_col"]
    elif parsed_data["tipo"] == "despesa_fixa":
        target_col = pos["saida_col"]
    else:  # despesa_diaria
        target_col = pos["diario_col"] 

    # Lê o valor atual da célula
    atual_str = ws.cell(row, target_col).value
    is_placeholder = (atual_str and atual_str.strip() == "R$ 33,36")

    # Atualiza o valor
    if is_placeholder:
        novo_valor = valor
    else:
        atual = _get_cell_float(atual_str)
        novo_valor = atual + valor
    
    ws.update_cell(row, target_col, novo_valor)

    # Gerenciar notas: substituir se placeholder, append caso contrário
    cell_address = gspread.utils.rowcol_to_a1(row, target_col)
    nova_descricao = parsed_data.get('descricao', 'N/A')
    
    if is_placeholder:
        # Substitui a nota completamente
        nota_final = nova_descricao
        print(f"📝 Substituindo nota (placeholder detectado)")
    else:
        # Faz append à nota existente
        nota_existente = get_cell_note(GOOGLE_SHEETS_ID, get_sheet_name(), cell_address)
        
        if nota_existente and nota_existente.strip():
            # Adiciona separador e nova descrição
            nota_final = f"{nota_existente}\n---\n{nova_descricao}"
            print(f"📝 Adicionando à nota existente")
        else:
            # Não havia nota, cria nova
            nota_final = nova_descricao
            print(f"📝 Criando nova nota")
    
    ws.update_note(cell_address, nota_final)

    return (
        f"Dia {row - 2}: tipo={parsed_data['tipo']} "
        f"{'substituiu' if is_placeholder else '↑'} {valor:.2f} "
        f"(total agora {novo_valor:.2f})"
    )