# ui/biblia_digital.py
# Interface simples e limpa da Bíblia Digital
# Executar com: streamlit run ui/biblia_digital.py

import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.biblia import listar_livros, listar_capitulos, obter_capitulo_completo, obter_texto_versiculo

st.set_page_config(
    page_title="Bíblia Ave Maria",
    page_icon="📖",
    layout="centered",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .versiculo {
        font-size: 1.15rem;
        line-height: 1.7;
        margin-bottom: 0.6rem;
    }
    .numero-versiculo {
        font-weight: 600;
        color: #6b4c9a;
        margin-right: 0.4rem;
    }
    .titulo-capitulo {
        text-align: center;
        font-size: 1.4rem;
        font-weight: 600;
        margin: 1.2rem 0 1.5rem 0;
        color: #3d2b5a;
    }
    .bloco-capitulo {
        background-color: #faf9fc;
        padding: 1.5rem 1.8rem;
        border-radius: 10px;
        border: 1px solid #e8e4f0;
        margin-bottom: 1.5rem;
    }
    .item-lista {
        padding: 0.45rem 0.7rem;
        margin-bottom: 0.25rem;
        background: #f7f5fb;
        border-radius: 6px;
        border: 1px solid #ebe6f5;
        font-size: 1.05rem;
    }
    .subtitulo-secao {
        font-size: 1.15rem;
        font-weight: 600;
        color: #5a4580;
        margin: 1.2rem 0 0.6rem 0;
    }
</style>
""", unsafe_allow_html=True)


def main():
    st.title("📖 Bíblia Ave Maria")
    st.caption("Edição Católica • Navegação simples")

    livros = listar_livros()

    with st.sidebar:
        st.header("Navegação")
        st.caption("Use 0 para ver tudo do nível")

        # --- Livro ---
        opcoes_livro = ["0 — Todos os livros"] + livros
        livro_sel = st.selectbox("Livro", options=opcoes_livro, index=1)

        if livro_sel.startswith("0"):
            livro = None
            capitulo = None
            versiculo = 0
        else:
            livro = livro_sel

            # --- Capítulo ---
            capitulos = listar_capitulos(livro)
            opcoes_cap = ["0 — Todos os capítulos"] + [str(c) for c in capitulos]
            cap_sel = st.selectbox("Capítulo", options=opcoes_cap, index=1)

            if cap_sel.startswith("0"):
                capitulo = None
                versiculo = 0
            else:
                capitulo = int(cap_sel)

                # --- Versículo ---
                st.caption("Versículo")
                versiculo = st.number_input(
                    "Versículo",
                    min_value=0,
                    value=0,
                    step=1,
                    help="0 = todos os versículos do capítulo"
                )

    # ========== CONTEÚDO PRINCIPAL ==========

    # 1. Todos os livros
    if livro is None:
        st.markdown("<div class='titulo-capitulo'>Todos os livros</div>", unsafe_allow_html=True)

        antigo = livros[:46]
        novo = livros[46:]

        st.markdown("<div class='subtitulo-secao'>Antigo Testamento</div>", unsafe_allow_html=True)
        cols = st.columns(2)
        for i, nome in enumerate(antigo):
            cols[i % 2].markdown(f"<div class='item-lista'>{nome}</div>", unsafe_allow_html=True)

        st.markdown("<div class='subtitulo-secao'>Novo Testamento</div>", unsafe_allow_html=True)
        cols = st.columns(2)
        for i, nome in enumerate(novo):
            cols[i % 2].markdown(f"<div class='item-lista'>{nome}</div>", unsafe_allow_html=True)

        st.caption(f"{len(livros)} livros")
        return

    # 2. Todos os capítulos do livro
    if capitulo is None:
        capitulos = listar_capitulos(livro)
        st.markdown(f"<div class='titulo-capitulo'>{livro}</div>", unsafe_allow_html=True)

        if not capitulos:
            st.warning("Nenhum capítulo encontrado.")
            return

        cols = st.columns(6)
        for i, num in enumerate(capitulos):
            cols[i % 6].markdown(
                f"<div class='item-lista' style='text-align:center'>{num}</div>",
                unsafe_allow_html=True
            )

        st.caption(f"{len(capitulos)} capítulos")
        return

    # 3. Um versículo específico
    if versiculo and versiculo > 0:
        texto = obter_texto_versiculo(livro, capitulo, versiculo)
        if texto:
            st.markdown(
                f"<div class='titulo-capitulo'>{livro} {capitulo},{versiculo}</div>",
                unsafe_allow_html=True
            )
            st.markdown(
                f"<div class='bloco-capitulo'><div class='versiculo'>"
                f"<span class='numero-versiculo'>{versiculo}</span>{texto}"
                f"</div></div>",
                unsafe_allow_html=True
            )
        else:
            st.warning(f"Versículo {versiculo} não encontrado em {livro} {capitulo}.")
        return

    # 4. Capítulo completo (versículo = 0)
    versiculos = obter_capitulo_completo(livro, capitulo)
    if not versiculos:
        st.warning("Capítulo não encontrado.")
        return

    st.markdown(f"<div class='titulo-capitulo'>{livro} {capitulo}</div>", unsafe_allow_html=True)

    html_versiculos = ""
    for v in versiculos:
        html_versiculos += (
            f"<div class='versiculo'>"
            f"<span class='numero-versiculo'>{v['versiculo']}</span>"
            f"{v['texto']}"
            f"</div>"
        )

    st.markdown(f"<div class='bloco-capitulo'>{html_versiculos}</div>", unsafe_allow_html=True)
    st.caption(f"{len(versiculos)} versículos")


if __name__ == "__main__":
    main()
