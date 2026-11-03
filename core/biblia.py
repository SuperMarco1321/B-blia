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
_por_testamento: dict | None = None   # "Antigo Testamento"/"Novo Testamento" → [nomes]


def _carregar() -> dict:
    """Carrega o JSON uma única vez."""
    global _biblia_raw, _indice, _lista_livros, _por_testamento

    if _biblia_raw is not None:
        return _biblia_raw

    with open(CAMINHO_BIBLIA, "r", encoding="utf-8") as f:
        _biblia_raw = json.load(f)

    # Monta índice rápido por nome do livro
    _indice = {}
    _lista_livros = []
    _por_testamento = {}

    rotulos = {
        "antigoTestamento": "Antigo Testamento",
        "novoTestamento": "Novo Testamento",
    }
    for chave, rotulo in rotulos.items():
        _por_testamento[rotulo] = []
        for livro in _biblia_raw[chave]:
            nome = livro["nome"]
            _indice[nome] = livro
            _lista_livros.append(nome)
            _por_testamento[rotulo].append(nome)

    return _biblia_raw


def listar_livros() -> list[str]:
    """Retorna a lista de todos os livros na ordem canônica."""
    _carregar()
    return _lista_livros.copy()


def listar_livros_por_testamento() -> dict[str, list[str]]:
    """Retorna {"Antigo Testamento": [...], "Novo Testamento": [...]} direto do JSON."""
    _carregar()
    return {k: v.copy() for k, v in _por_testamento.items()}


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


def obter_livro_completo(livro: str) -> list[dict]:
    """
    Junta TODOS os capítulos de um livro, na ordem.
    Formato: [{"capitulo": 1, "versiculos": [{"versiculo": 1, "texto": "..."}]}, ...]
    """
    _carregar()
    dados_livro = _indice.get(livro)
    if not dados_livro:
        return []
    return [
        {
            "capitulo": cap["capitulo"],
            "versiculos": [
                {"versiculo": v["versiculo"], "texto": v["texto"]}
                for v in cap["versiculos"]
            ],
        }
        for cap in dados_livro["capitulos"]
    ]


def obter_leitura_continua(livros: Optional[list[str]] = None) -> list[dict]:
    """
    Junta a leitura de vários livros (ou de todos, se 'livros' for None)
    numa única sequência, na ordem canônica.
    Formato: [{"livro": "Gênesis", "capitulos": [ ...obter_livro_completo... ]}, ...]
    """
    _carregar()
    nomes = livros if livros is not None else _lista_livros
    return [
        {"livro": nome, "capitulos": obter_livro_completo(nome)}
        for nome in nomes
        if nome in _indice
    ]


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
