# ui/render_marcado.py
# Monta o HTML do texto bíblico com as marcações (marca-texto) por FRASE.
# Função pura (sem Streamlit): recebe blocos de texto + índice de marcações e devolve um documento HTML.
#
#  - cada frase marcada recebe a cor litúrgica da celebração;
#  - onde duas ou mais marcações se cruzam, a frase fica em faixas com as cores de todas;
#  - ao passar o mouse, o balão (title) mostra o que cobre a frase e onde está a interseção.

from __future__ import annotations

from html import escape

from core.leitura_liturgica import frases_do_versiculo
from core.marcacoes import IndiceMarcacoes
from core.marcacoes_modelo import CORES

CSS = """
html, body { background: #0b1426; }
body { margin: 0; font-family: 'Segoe UI', system-ui, -apple-system, sans-serif; color: #e6ecf7; color-scheme: dark; }
.bloco { background: #15233f; padding: 1.3rem 1.6rem; border-radius: 12px; border: 1px solid #2a416b; }
.versiculo { font-size: 1.12rem; line-height: 1.9; margin-bottom: 0.55rem; }
.num { font-weight: 600; color: #7db3ff; margin-right: 0.4rem; font-size: 0.9em; }
.livro { font-size: 1.25rem; font-weight: 700; color: #cfe0ff; margin: 1.4rem 0 0.4rem; padding-bottom: .3rem; border-bottom: 2px solid #2a416b; }
.livro:first-child { margin-top: 0; }
.cap { font-size: 0.95rem; font-weight: 600; color: #8fb4f0; margin: 1rem 0 0.3rem; }
.mk { border-radius: 3px; padding: 1px 2px; cursor: help; -webkit-box-decoration-break: clone; box-decoration-break: clone; }
.mk:hover { filter: brightness(1.25); }
"""


def _rgba(hex_: str, alpha: float) -> str:
    h = hex_.lstrip("#")
    return f"rgba({int(h[0:2], 16)},{int(h[2:4], 16)},{int(h[4:6], 16)},{alpha})"


def estilo_frase(marcas) -> str:
    """CSS de uma frase marcada: cor única, ou faixas horizontais quando há interseção."""
    cores = []
    for m in marcas:
        if m.cor not in cores:
            cores.append(m.cor)
    primeira = CORES[cores[0]]["borda"]

    if len(cores) == 1:
        fundo = _rgba(CORES[cores[0]]["fill"], CORES[cores[0]]["alpha"])
    else:
        n = len(cores)
        faixas = []
        for i, c in enumerate(cores):
            a, b = round(i * 100 / n, 2), round((i + 1) * 100 / n, 2)
            cor = _rgba(CORES[c]["fill"], min(0.7, CORES[c]["alpha"] + 0.05))
            faixas.append(f"{cor} {a}%, {cor} {b}%")
        fundo = "linear-gradient(to bottom, " + ", ".join(faixas) + ")"

    # Interseção (mesmo com cores iguais) = sublinhado duplo
    borda = "double 3px" if len(marcas) > 1 else "solid 2px"
    return f"background:{fundo};border-bottom:{borda} {primeira};"


def _balao(texto: str) -> str:
    return escape(texto, quote=True).replace("\n", "&#10;")


def html_versiculo(livro: str, cap: int, ver: int, texto: str, indice: IndiceMarcacoes, inter: dict) -> str:
    frases = frases_do_versiculo(livro, texto) or [texto]
    partes = []
    for i, frase in enumerate(frases):
        corpo = escape(frase, quote=False)
        marcas = indice.marcas_da_frase(livro, cap, ver, i)
        if marcas:
            tip = _balao(indice.tooltip(livro, cap, ver, i, _inter_cache=inter))
            partes.append(f'<span class="mk" style="{estilo_frase(marcas)}" title="{tip}">{corpo}</span>')
        else:
            partes.append(corpo)
    return " ".join(partes)


def documento_html(
    blocos: list[dict],
    indice: IndiceMarcacoes,
    mostrar_livro: bool = True,
    mostrar_capitulo: bool = True,
) -> str:
    """
    blocos: [{"livro": str, "capitulos": [{"capitulo": int, "versiculos": [{"versiculo": int, "texto": str}]}]}]
    Devolve um documento HTML completo (para components.html).
    """
    corpo = []
    for bloco in blocos:
        livro = bloco["livro"]
        if mostrar_livro:
            corpo.append(f'<div class="livro">{escape(livro)}</div>')
        for cap in bloco["capitulos"]:
            n = cap["capitulo"]
            inter = indice.intersecoes(livro, n)
            if mostrar_capitulo:
                corpo.append(f'<div class="cap">Capítulo {n}</div>')
            for v in cap["versiculos"]:
                corpo.append(
                    f'<div class="versiculo"><span class="num">{v["versiculo"]}</span>'
                    f'{html_versiculo(livro, n, v["versiculo"], v["texto"], indice, inter)}</div>'
                )
    return (
        "<!DOCTYPE html><html><head><meta charset='utf-8'><style>" + CSS + "</style></head>"
        "<body><div class='bloco'>" + "".join(corpo) + "</div></body></html>"
    )


def filtrar_marcados(blocos: list[dict], indice: IndiceMarcacoes) -> list[dict]:
    """Mantém só os capítulos que têm alguma marcação (e os livros que sobram)."""
    saida = []
    for b in blocos:
        caps = [c for c in b["capitulos"] if indice.capitulo_marcado(b["livro"], c["capitulo"])]
        if caps:
            saida.append({"livro": b["livro"], "capitulos": caps})
    return saida


def altura_estimada(blocos: list[dict]) -> int:
    """Altura (px) do iframe conforme a quantidade de texto, entre 260 e 820."""
    chars = sum(len(v["texto"]) for b in blocos for c in b["capitulos"] for v in c["versiculos"])
    capitulos = sum(len(b["capitulos"]) for b in blocos)
    return int(min(820, max(260, 110 + chars / 70 * 31 + capitulos * 30)))