import logging
from functools import lru_cache
from sentence_transformers import CrossEncoder


logger = logging.getLogger(__name__)

MATCH_THRESHOLD = 0.6

@lru_cache(maxsize=1)
def _load_model():
    """
    Carrega o modelo uma única vez e o mantém em cache para uso futuro.
    """
    logger.info("Carregando cross-encoder multilingue...")
    model = CrossEncoder(
        "cross-encoder/ms-marco-MiniLM-L-6-v2",
        max_length=128
    )
    logger.info("Modelo carregado.")
    return model

def find_matching_estimates(
        nova_descricao: str,
        candidatos: list[dict],
        threshold: float = MATCH_THRESHOLD
) -> list[dict]:
    """
    Recebe a descrição do novo gasto e uma lista de candidatos pré-filtrados.

    Args:
        nova_descricao (str): A descrição do novo gasto.
        candidatos (list[dict]): Lista de dicionários contendo 'descricao', 'row', 'col' e 'cell_ref'.
        threshold (float): Limite de similaridade para considerar uma correspondência.
    Returns:
        list[dict]: Lista de candidatos que passaram no teste de similaridade, ordenados por score.
    """
    if not candidatos:
        return []

    model = _load_model()

    pares = [(nova_descricao, c["descricao"]) for c in candidatos]
    scores = model.predict(pares)

    matches = []
    for candidato, score in zip(candidatos, scores):
        logger.debug(f"Score '{nova_descricao} x {candidato['descricao']}': {score:.3f}")
        if score >= threshold:
            matches.append({**candidato, "score": float(score)})

    matches.sort(key=lambda x: x["score"], reverse=True)
    return matches
    