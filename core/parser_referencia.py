# core/parser_referencia.py
# Interpreta referências bíblicas no formato usado pela CNBB e notação comum.
# Versão rigorosa — com suporte a letras e consulta ao JSON da Bíblia.

from utils.livros import normalizar_nome
from utils.divisao_versiculo import extrair_letra_da_referencia
import re
import json
from pathlib import Path
from typing import Optional

# Caminho do JSON da Bíblia
CAMINHO_BIBLIA = Path(__file__).parent.parent / "bibliaAveMaria.json"

# Cache do índice de versículos (carregado sob demanda)
_indice_versiculos: dict | None = None


def _carregar_indice_versiculos() -> dict:
    """
    Carrega o JSON da Bíblia e cria um índice rápido:
    {
        "I Coríntios": {
            12: 31,   # capítulo 12 tem 31 versículos
            13: 13,
            ...
        },
        ...
    }
    """
    global _indice_versiculos
    if _indice_versiculos is not None:
        return _indice_versiculos

    with open(CAMINHO_BIBLIA, "r", encoding="utf-8") as f:
        data = json.load(f)

    indice = {}

    for testamento in ["antigoTestamento", "novoTestamento"]:
        for livro in data[testamento]:
            nome = livro["nome"]
            indice[nome] = {}
            for cap in livro["capitulos"]:
                num_cap = cap["capitulo"]
                qtd_versiculos = len(cap["versiculos"])
                indice[nome][num_cap] = qtd_versiculos

    _indice_versiculos = indice
    return indice


def quantos_versiculos(livro: str, capitulo: int) -> int | None:
    """
    Retorna quantos versículos o capítulo tem.
    Retorna None se o livro ou capítulo não existir.
    """
    indice = _carregar_indice_versiculos()
    return indice.get(livro, {}).get(capitulo)


# Refrão: "(R. 17a)", "(R. cf. 6)", "(R/ 6)" e, sem parênteses, "... R. 1" no fim da referência.
_RE_REFRAO_PARENTESES = re.compile(r"\(\s*R\s*[./]\s*(.*?)\)", flags=re.IGNORECASE)
_RE_REFRAO_FINAL = re.compile(
    r"\s+R\.\s*((?:cf\.?\s*)?\d+[a-z]*(?:[,.\-–]\d+[a-z]*)*)\s*$",
    flags=re.IGNORECASE,
)


def _extrair_refrao(original: str) -> tuple[Optional[str], str]:
    """Devolve (refrão ou None, texto sem o refrão)."""
    for padrao in (_RE_REFRAO_PARENTESES, _RE_REFRAO_FINAL):
        m = padrao.search(original)
        if m:
            refrao = m.group(1).strip() or None
            texto = (original[:m.start()] + " " + original[m.end():]).strip()
            return refrao, texto
    return None, original


def parse_referencia(texto: str) -> dict:
    """
    Recebe uma string de referência (ex: "Sl 22(23),1-3.5.7-9 (R. 1)")
    e devolve um dicionário estruturado com todos os versículos expandidos.
    """
    if not texto or not texto.strip():
        return {
            "referencia_original": texto,
            "livro": None,
            "refrão": None,
            "versiculos": []
        }

    original = texto.strip()

    # 1. Extrai o refrão (e o remove do texto)
    refrao, texto_limpo = _extrair_refrao(original)

    # 2. Separa por ponto e vírgula
    blocos = [b.strip() for b in texto_limpo.split(";") if b.strip()]

    livro_atual = None
    todos_versiculos = []

    for idx_bloco, bloco in enumerate(blocos):
        match_livro = re.match(
            r"^([1-3]?[A-Za-zÀ-ú\s\.]+?)\s+(\d+.*)$",
            bloco
        )

        if match_livro:
            nome_bruto = match_livro.group(1).strip()
            resto = match_livro.group(2).strip()
            livro_normalizado = normalizar_nome(nome_bruto)

            if livro_normalizado:
                livro_atual = livro_normalizado
            else:
                resto = bloco
        else:
            resto = bloco

        if not livro_atual:
            continue

        itens = _parse_capitulos_versiculos(livro_atual, resto)
        for item in itens:
            item["bloco"] = idx_bloco   # trecho separado por ';'
        todos_versiculos.extend(itens)

    return {
        "referencia_original": original,
        "livro": livro_atual,
        "refrão": refrao,
        "versiculos": todos_versiculos
    }


def _parse_capitulos_versiculos(livro: str, texto: str) -> list[dict]:
    """
    Interpreta a parte de capítulos e versículos com rigor.
    Agora consulta o JSON para expandir intervalos entre capítulos.
    """
    resultado = []

    texto = re.sub(r"\s+", "", texto)
    texto = re.sub(r"(\d+)\(\d+\)", r"\1", texto)  # Sl 22(23) → 22

    # =========================================================
    # Caso especial: intervalo entre capítulos diferentes
    # Ex: 12,31–13,13  ou  12,31-13,13
    # =========================================================
    match_entre = re.match(
        r"(\d+),(\d+[a-z]*)[–\-](\d+),(\d+[a-z]*)",
        texto,
        flags=re.IGNORECASE
    )
    if match_entre:
        cap1 = int(match_entre.group(1))
        ver_inicio, letras_inicio = extrair_letra_da_referencia(match_entre.group(2))
        cap2 = int(match_entre.group(3))
        ver_fim, letras_fim = extrair_letra_da_referencia(match_entre.group(4))

        if ver_inicio is None or ver_fim is None:
            return resultado

        # --- Capítulo inicial: do versículo de início até o último versículo ---
        ultimo_ver_cap1 = quantos_versiculos(livro, cap1)
        if ultimo_ver_cap1 is None:
            resultado.append({
                "livro": livro,
                "capitulo": cap1,
                "versiculo": ver_inicio,
                "letras": letras_inicio,
                "nota": "capítulo não encontrado no JSON"
            })
        else:
            for v in range(ver_inicio, ultimo_ver_cap1 + 1):
                letras = letras_inicio if v == ver_inicio else None
                resultado.append({
                    "livro": livro,
                    "capitulo": cap1,
                    "versiculo": v,
                    "letras": letras
                })

        # --- Capítulos intermediários (se houver) ---
        for cap in range(cap1 + 1, cap2):
            ultimo = quantos_versiculos(livro, cap)
            if ultimo is None:
                continue
            for v in range(1, ultimo + 1):
                resultado.append({
                    "livro": livro,
                    "capitulo": cap,
                    "versiculo": v,
                    "letras": None
                })

        # --- Capítulo final: do versículo 1 até o versículo de fim ---
        for v in range(1, ver_fim + 1):
            letras = letras_fim if v == ver_fim else None
            resultado.append({
                "livro": livro,
                "capitulo": cap2,
                "versiculo": v,
                "letras": letras
            })

        return resultado

    # =========================================================
    # Caso normal: um capítulo + lista de versículos
    # =========================================================
    match = re.match(r"(\d+)[,.](.+)", texto)
    if not match:
        if texto.isdigit():
            return [{
                "livro": livro,
                "capitulo": int(texto),
                "versiculo": None,
                "letras": None
            }]
        return []

    capitulo = int(match.group(1))
    parte_versiculos = match.group(2)

    partes = [p for p in parte_versiculos.split(".") if p]

    for idx_seg, parte in enumerate(partes):
        n_antes = len(resultado)
        if "-" in parte or "–" in parte:
            pedacos = re.split(r"[–\-]", parte, maxsplit=1)
            if len(pedacos) != 2:
                continue

            v_inicio, letras_inicio = extrair_letra_da_referencia(pedacos[0])
            v_fim, letras_fim = extrair_letra_da_referencia(pedacos[1])

            if v_inicio is not None and v_fim is not None:
                for v in range(v_inicio, v_fim + 1):
                    if v == v_inicio and v == v_fim:
                        letras = letras_inicio or letras_fim
                    elif v == v_inicio:
                        letras = letras_inicio
                    elif v == v_fim:
                        letras = letras_fim
                    else:
                        letras = None

                    resultado.append({
                        "livro": livro,
                        "capitulo": capitulo,
                        "versiculo": v,
                        "letras": letras
                    })
        else:
            v, letras = extrair_letra_da_referencia(parte)
            if v is not None:
                resultado.append({
                    "livro": livro,
                    "capitulo": capitulo,
                    "versiculo": v,
                    "letras": letras
                })

        for item in resultado[n_antes:]:
            item["segmento"] = idx_seg   # parte separada por '.'

    return resultado


# ============================================================
# Testes
# ============================================================
if __name__ == "__main__":
    exemplos = [
        "1Cor 12,31–13,13",
        "1Cor 12,31-13,13",
        "Sl 144(145),8-9.10-11.12-13ab.13cd-14 (R. 17a)",
        "Jo 1,1-5.9-12b",
        "Hab 1,2-3; 2,2-4",
        "Lc 4,31-37",
    ]

    for ex in exemplos:
        print(f"\n{'='*60}")
        print(f"Entrada: {ex}")
        resultado = parse_referencia(ex)
        print(f"Livro   : {resultado['livro']}")
        print(f"Refrão  : {resultado['refrão']}")
        print(f"Total de versículos marcados: {len(resultado['versiculos'])}")
        print("Versículos:")
        for v in resultado["versiculos"]:
            letras_str = f" (letras: {v['letras']})" if v.get("letras") else ""
            print(f"   {v['capitulo']},{v['versiculo']}{letras_str}")