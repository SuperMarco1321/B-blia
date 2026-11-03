# core/biblia.py
# Camada de acesso à Bíblia Ave Maria.
# Responsável por carregar, buscar e devolver textos de forma limpa.

import json
from pathlib import Path
from typing import Optional
from utils.divisao_versiculo import obter_partes, dividir_por_pontos

CAMINHO_BIBLIA = Path(__file__).parent.parent / "bibliaAveMaria.json"

# Cache em memória
_biblia_raw: dict | None = None
_indice: dict | None = None          # nome_livro → dados do livro
_lista_livros: list[str] | None = None


def _carregar() -> dict:
    """Carrega o JSON uma única vez."""
    global _biblia_raw, _indice, _lista_livros

    if _biblia_raw is not None:
        return _biblia_raw

    with open(CAMINHO_BIBLIA, "r", encoding="utf-8") as f:
        _biblia_raw = json.load(f)

    # Monta índice rápido por nome do livro
    _indice = {}
    _lista_livros = []

    for testamento in ["antigoTestamento", "novoTestamento"]:
        for livro in _biblia_raw[testamento]:
            nome = livro["nome"]
            _indice[nome] = livro
            _lista_livros.append(nome)

    return _biblia_raw


def listar_livros() -> list[str]:
    """Retorna a lista de todos os livros na ordem canônica."""
    _carregar()
    return _lista_livros.copy()


def listar_capitulos(livro: str) -> list[int]:
    """Retorna a lista de números de capítulos de um livro."""
    _carregar()
    dados = _indice.get(livro)
    if not dados:
        return []
    return [cap["capitulo"] for cap in dados["capitulos"]]


def obter_texto_versiculo(
    livro: str,
    capitulo: int,
    versiculo: int,
    letras: Optional[str] = None
) -> Optional[str]:
    """
    Retorna o texto de um versículo específico.
    Se 'letras' for informado (ex: "b", "ab"), devolve só aquelas partes
    (separadas por ponto final).
    """
    _carregar()
    dados_livro = _indice.get(livro)
    if not dados_livro:
        return None

    for cap in dados_livro["capitulos"]:
        if cap["capitulo"] == capitulo:
            for v in cap["versiculos"]:
                if v["versiculo"] == versiculo:
                    texto = v["texto"]
                    if letras:
                        return obter_partes(texto, letras)
                    return texto
    return None


def obter_capitulo_completo(livro: str, capitulo: int) -> list[dict]:
    """
    Retorna todos os versículos de um capítulo.
    Formato: [{"versiculo": 1, "texto": "..."}, ...]
    """
    _carregar()
    dados_livro = _indice.get(livro)
    if not dados_livro:
        return []

    for cap in dados_livro["capitulos"]:
        if cap["capitulo"] == capitulo:
            return [
                {"versiculo": v["versiculo"], "texto": v["texto"]}
                for v in cap["versiculos"]
            ]
    return []


def obter_partes_versiculo(livro: str, capitulo: int, versiculo: int) -> dict:
    """
    Retorna o versículo já dividido em partes a, b, c...
    Útil para debug e para a marcação precisa.
    """
    texto = obter_texto_versiculo(livro, capitulo, versiculo)
    if not texto:
        return {}
    return dividir_por_pontos(texto)


def buscar_simples(
    livro: str,
    capitulo: Optional[int] = None,
    versiculo: Optional[int] = None
) -> dict:
    """
    Busca simples usada pela Bíblia Digital.

    - Só livro          → devolve informações do livro + lista de capítulos
    - Livro + capítulo  → devolve o capítulo completo
    - Livro + cap + ver → devolve o versículo específico
    """
    _carregar()

    if livro not in _indice:
        return {"erro": f"Livro '{livro}' não encontrado"}

    resultado = {
        "livro": livro,
        "capitulo": capitulo,
        "versiculo": versiculo,
    }

    if capitulo is None:
        resultado["capitulos"] = listar_capitulos(livro)
        return resultado

    if versiculo is None:
        resultado["versiculos"] = obter_capitulo_completo(livro, capitulo)
        return resultado

    texto = obter_texto_versiculo(livro, capitulo, versiculo)
    resultado["texto"] = texto
    resultado["partes"] = dividir_por_pontos(texto) if texto else {}
    return resultado
