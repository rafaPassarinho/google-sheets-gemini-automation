import re
import logging
import gspread

from datetime import datetime

from sheets_writer import get_sheets_client, get_cell_note

logger = logging.getLogger(__name__)

# regex para extrair descrição de uma nota de estimativa
# exemplo de notas: "* R$ 250,00 - aluguel", "* mercado semana"
_CURRENCY_RE = re.compile(r"^(?:R\$\s*[\d.,]+\s*[-–]\s*)?(.+)$", re.IGNORECASE)

def _extrair_descricao_nota(nota: str) -> str:
    """
    Extrai a parte descritiva de uma nota de estimativa, removendo apenas o asterisco.

    Args:
        nota (str): A nota de estimativa, geralmente começando com "*".
    Returns:
        str: A descrição extraída da nota, sem o asterisco e sem o valor monetário. None se a nota não possuir asterisco.
    """
    if not (nota.startswith("*") or nota.endswith("*")):
        return None

    nota_limpa = nota.strip("*").strip()

    # Tenta remover o valor da moeda (ex: "R$ 50,00 - ") do início da nota
    match = _CURRENCY_RE.match(nota_limpa)
    if match:
        return match.group(1).strip()

    return nota_limpa

def buscar_estimativas_candidatas(
        spreadsheet_id: str,
        col_index: int,
        row_start: int, # dia seguinte ao dia atual + 3
        row_end: int    # última linha do mês
) -> list[dict]:
    """
    Varre um intervalo específico de uma coluna e retorna todas as células que possuem nota começando com '*'.

    Args:
        spreadsheet_id (str): ID da planilha do Google Sheets.
        col_index (int): Índice da coluna a ser varrida.
        row_start (int): Número da primeira linha do mês.
        row_end (int): Número da última linha do mês.

    Returns:
        list[dict]: Lista de dicionários compatível com matcher.find_matching_estimates().
    """
    try:
        client = get_sheets_client()
        sheet = client.open_by_key(spreadsheet_id)
        aba_nome = str(datetime.now().year)
        ws = sheet.worksheet(aba_nome)

        cell_list = ws.range(row_start, col_index, row_end, col_index)

        candidatos = []
        for cell in cell_list:
            try:
                nota = get_cell_note(spreadsheet_id, aba_nome, cell.address) or ""
            except Exception:
                nota = ""

            descricao = _extrair_descricao_nota(nota)
            if descricao:
                candidatos.append({
                    "descricao": descricao,
                    "row": cell.row,
                    "col": cell.col,
                    "cell_ref": cell.address
                })

        logger.info(
            "Coluna %s - Linhas %s-%s: %s estimativa(s) encontrada(s).",
            col_index, row_start, row_end, len(candidatos)
        )
        return candidatos

    except Exception as e:
        logger.error("Erro ao buscar estimativas candidatas: %s", e, exc_info=True)
        return []
    
def apagar_estimativa(
        spreadsheet_id: str,
        row: int,
        col: int
) -> bool:
    """
    Apaga o valor e a nota de uma célula de estimativa.
    Args:
        spreadsheet_id (str): ID da planilha do Google Sheets.
        row (int): Número da linha da célula a ser apagada.
        col (int): Número da coluna da célula a ser apagada.
    Returns:
        bool: True se a operação foi bem-sucedida, False caso contrário.
    """
    try:
        client = get_sheets_client()
        sheet = client.open_by_key(spreadsheet_id)
        aba_nome = str(datetime.now().year)
        ws = sheet.worksheet(aba_nome)

        cell_address = gspread.utils.rowcol_to_a1(row, col)

        ws.update_cell(row, col, "")
        ws.update_note(cell_address, "")

        logger.info("Estimativa apagada na célula %s.", cell_address)
        return True

    except Exception as e:
        logger.error("Erro ao apagar estimativa (%s, %s): %s", row, col, e, exc_info=True)
        return False
    