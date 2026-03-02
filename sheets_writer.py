import gspread
from google.oauth2.service_account import Credentials
from dotenv import load_dotenv
from googleapiclient.discovery import build
from utils import get_columns_for_date, get_sheet_name, get_today_str_iso, GOOGLE_SHEETS_ID
from datetime import datetime

load_dotenv()

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]

def get_sheets_client():
    """
    Cria cliente autenticado para Google Sheets usando credenciais de conta de serviço.
    
    return:
        gspread.Client: cliente autenticado para interagir com Google Sheets.
    """
    creds = Credentials.from_service_account_file(
        "credentials.json",
        scopes=SCOPES
    )
    gc = gspread.authorize(creds)
    return gc

def get_sheets_service():
    """Cria o serviço da API do Google Sheets
    
    return:
        googleapiclient.discovery.Resource: serviço autenticado para interagir com Google Sheets.
    """
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

def update_economia_sheet(parsed_data: dict) -> str:
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
    
    Returns:
        str: mensagem de confirmação
    """
    gc = get_sheets_client()
    target_date = parsed_data.get("data", get_today_str_iso())
    
    try:
        sh = gc.open_by_key(GOOGLE_SHEETS_ID)
        ws_economia = sh.worksheet("Economia")
    except gspread.WorksheetNotFound:
        raise ValueError("Aba 'Economia' não encontrada na planilha.")
    
    dt = datetime.fromisoformat(target_date)
    mes = dt.month

    row = 4 + mes  # Janeiro na linha 5, então linha = mês + 4
    col = 9  # Coluna I

    valor = float(parsed_data["valor"])

    # Lê o valor atual da célula
    cell_address = gspread.utils.rowcol_to_a1(row, col)
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

def append_expense_to_sheet(parsed_data: dict) -> str:
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
    Returns:
        str: mensagem de confirmação ou erro
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
        target_col = pos["saida_col"]  # economia é registrada como saída

        cell_address = gspread.utils.rowcol_to_a1(row, target_col)
        atual_str = ws.cell(row, target_col).value
        is_placeholder = (atual_str and atual_str.strip() == "R$ 33,36")

        nota_existente = get_cell_note(GOOGLE_SHEETS_ID, get_sheet_name(), cell_address)
        tem_asterisco = nota_existente and '*' in nota_existente

        if is_placeholder or atual_str in [None, "", "0", "R$ 0,00"] or tem_asterisco:
            novo_valor = valor
            acao = "substituiu"
        else:
            atual = _get_cell_float(atual_str)
            novo_valor = atual + valor
            acao = "somou"
        
        ws.update_cell(row, target_col, novo_valor)

        nova_descricao = parsed_data.get('descricao', 'Economia')
        if is_placeholder or tem_asterisco:
            nota_final = nova_descricao
        else:
            if nota_existente and nota_existente.strip():
                nota_final = f"{nota_existente}\n---\n{nova_descricao}"
            else:
                nota_final = nova_descricao

        ws.update_note(cell_address, nota_final)

        economia_result = update_economia_sheet(parsed_data)

        return (
            f"Data {target_date} (dia {row - 2}): ECONOMIA {acao} {valor:.2f} "
            f"(Saída: R$ {novo_valor:.2f})\n\n{economia_result}"
        )

    if parsed_data["tipo"] == "receita":
        target_col = pos["entrada_col"]
    elif parsed_data["tipo"] == "despesa_fixa":
        target_col = pos["saida_col"]
    else:  # despesa_diaria
        target_col = pos["diario_col"] 

    # Lê o valor atual da célula
    cell_address = gspread.utils.rowcol_to_a1(row, target_col)
    atual_str = ws.cell(row, target_col).value
    is_placeholder = (atual_str and atual_str.strip() == "R$ 33,36")

    nota_existente = get_cell_note(GOOGLE_SHEETS_ID, get_sheet_name(), cell_address)
    tem_asterisco = nota_existente and '*' in nota_existente

    # decidir se substitui ou soma: se for placeholder, possui valor 0 ou tem asterisco na nota, substitui. Caso contrário, soma.
    if is_placeholder or atual_str in [None, "", "0", "R$ 0,00"] or tem_asterisco:
        #substitui o valor
        novo_valor = valor
        if is_placeholder:
            acao = "substituiu placeholder"
        elif tem_asterisco:
            acao = "substituiu (estimativa)"
        else:
            acao = "registrou novo valor"
        print(f"{acao}: {atual_str} -> {novo_valor:.2f}")
    else:
        # soma ao valor existente
        atual = _get_cell_float(atual_str)
        novo_valor = atual + valor
        acao = "somou"
        print(f"{acao}: {atual:.2f} + {valor:.2f} -> {novo_valor:.2f}")

    ws.update_cell(row, target_col, novo_valor)

    # Gerenciar notas: substituir se placeholder, append caso contrário
    nova_descricao = parsed_data.get('descricao', 'N/A')
    
    if is_placeholder or tem_asterisco:
        # Substitui a nota completamente
        nota_final = nova_descricao
        print(f"📝 Substituindo nota")
    else:
        # Faz append à nota existente        
        if nota_existente and nota_existente.strip():
            # Adiciona separador e nova descrição
            nota_final = f"{nota_existente}\n---\n{nova_descricao}"
            print(f"Adicionando à nota existente")
        else:
            # Não havia nota, cria nova
            nota_final = nova_descricao
            print(f"Criando nova nota")
    
    ws.update_note(cell_address, nota_final)

    return (
        f"Data {target_date} (dia {row - 2}): tipo={parsed_data['tipo']} "
        f"{acao} {valor:.2f} (total agora {novo_valor:.2f})"
    )       