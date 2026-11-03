# ui/biblia_digital.py
# Interface simples e limpa da Bíblia Digital
# Executar com: streamlit run ui/biblia_digital.py

import streamlit as st
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from html import escape

from core.biblia import (
    listar_livros,
    listar_livros_por_testamento,
    listar_capitulos,
    obter_capitulo_completo,
    obter_livro_completo,
    obter_leitura_continua,
    obter_texto_versiculo,
)
from core.leitura_liturgica import ler_referencia

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
    .titulo-livro {
        font-size: 1.3rem;
        font-weight: 700;
        color: #3d2b5a;
        margin: 1.6rem 0 0.4rem 0;
        padding-bottom: 0.3rem;
        border-bottom: 2px solid #e8e4f0;
    }
    .marca-capitulo {
        font-size: 0.95rem;
        font-weight: 600;
        color: #8a73b5;
        margin: 1rem 0 0.3rem 0;
    }
    .refrao {
        background: #f1ecfa;
        border-left: 4px solid #6b4c9a;
        padding: 0.7rem 1rem;
        margin: 0.4rem 0 1rem 0;
        border-radius: 0 8px 8px 0;
        font-style: italic;
        font-size: 1.1rem;
    }
    .refrao-curto {
        color: #6b4c9a;
        font-style: italic;
        margin: 0.1rem 0 0.9rem 1.2rem;
    }
    .estrofe { margin-bottom: 0.2rem; }
    .subtitulo-secao {
        font-size: 1.15rem;
        font-weight: 600;
        color: #5a4580;
        margin: 1.2rem 0 0.6rem 0;
    }
</style>
""", unsafe_allow_html=True)


def html_leitura_continua(blocos: list[dict], mostrar_livro: bool = True) -> tuple[str, int, int]:
    """
    Junta vários livros/capítulos numa ÚNICA string HTML contínua
    (um só bloco, com marcas discretas de livro e capítulo no meio do texto).
    Retorna (html, total_capitulos, total_versiculos).
    """
    partes = []
    total_caps = total_vers = 0
    for bloco in blocos:
        if mostrar_livro:
            partes.append(f"<div class='titulo-livro'>{escape(bloco['livro'])}</div>")
        for cap in bloco["capitulos"]:
            total_caps += 1
            partes.append(f"<div class='marca-capitulo'>Capítulo {cap['capitulo']}</div>")
            for v in cap["versiculos"]:
                total_vers += 1
                partes.append(
                    f"<div class='versiculo'>"
                    f"<span class='numero-versiculo'>{v['versiculo']}</span>"
                    f"{escape(v['texto'], quote=False)}</div>"
                )
    return "".join(partes), total_caps, total_vers


EXEMPLOS_LITURGICOS = [
    "Sl 22(23),1-3a.3b-4.5.6 (R. 1)",
    "Sl 144(145),8-9.10-11.12-13ab.13cd-14 (R. 17a)",
    "1Cor 12,31–13,13",
    "Hab 1,2-3; 2,2-4",
    "Jo 1,1-5.9-12b",
    "Gn 22,1-2.9a.10-13.15-18",
    "Is 52,13–53,12",
    "Lc 1,39-45",
]


def _usar_exemplo():
    if st.session_state.get("exemplo_lit") != "—":
        st.session_state["ref_lit"] = st.session_state["exemplo_lit"]


def pagina_leitura_liturgica():
    st.subheader("🕯️ Leitura litúrgica")
    st.caption("Digite a referência na notação da CNBB e receba o texto da leitura.")

    st.session_state.setdefault("ref_lit", EXEMPLOS_LITURGICOS[0])
    st.selectbox("Exemplos", ["—"] + EXEMPLOS_LITURGICOS, key="exemplo_lit", on_change=_usar_exemplo)
    referencia = st.text_input("Referência", key="ref_lit", help="Ex.: Sl 144(145),8-9.10-11.12-13ab.13cd-14 (R. 17a)")
    mostrar_numeros = st.checkbox("Mostrar números dos versículos", value=False)

    if not referencia.strip():
        st.info("Digite uma referência para começar.")
        return

    res = ler_referencia(referencia)

    if not res["trechos"]:
        for aviso in res["avisos"]:
            st.warning(aviso)
        return

    st.markdown(f"<div class='titulo-capitulo'>{escape(res['referencia_original'])}</div>", unsafe_allow_html=True)

    refrao = res["refrao"]
    refrao_texto = escape(refrao["texto"], quote=False) if refrao and refrao["texto"] else None
    eh_salmo = res["livro"] == "Salmos"

    if refrao_texto:
        st.markdown(
            f"<div class='refrao'><b>R.</b> {refrao_texto}</div>",
            unsafe_allow_html=True,
        )

    for trecho in res["trechos"]:
        if len(res["trechos"]) > 1:
            st.markdown(
                f"<div class='subtitulo-secao'>{escape(trecho['livro'])} {escape(trecho['referencia'])}</div>",
                unsafe_allow_html=True,
            )

        if eh_salmo:
            # cada segmento (separado por '.') é uma estrofe; refrão depois de cada uma
            html = ""
            for seg in trecho["segmentos"]:
                html += f"<div class='estrofe versiculo'>{_html_segmento(seg, mostrar_numeros)}</div>"
                if refrao_texto:
                    html += f"<div class='refrao-curto'>R. {refrao_texto}</div>"
        else:
            html = "<div class='versiculo'>" + " ".join(
                _html_segmento(seg, mostrar_numeros) for seg in trecho["segmentos"]
            ) + "</div>"

        st.markdown(f"<div class='bloco-capitulo'>{html}</div>", unsafe_allow_html=True)

    if res["avisos"]:
        with st.expander(f"⚠️ Avisos de precisão ({len(res['avisos'])})"):
            for aviso in res["avisos"]:
                st.write("• " + aviso)
            st.caption(
                "As letras (a, b, c...) da CNBB seguem as meias-linhas do original; aqui o texto é "
                "dividido por ponto final. Onde isso não bate, a divisão é aproximada."
            )


def _html_segmento(seg: dict, mostrar_numeros: bool) -> str:
    if not mostrar_numeros:
        return escape(seg["texto"], quote=False)
    partes = []
    for v in seg["versiculos"]:
        rotulo = f"{v['versiculo']}{v['letras'] or ''}"
        partes.append(f"<span class='numero-versiculo'>{rotulo}</span>{escape(v['texto'], quote=False)}")
    return " ".join(partes)


def main():
    st.title("📖 Bíblia Ave Maria")
    st.caption("Edição Católica")

    livros = listar_livros()

    with st.sidebar:
        modo = st.radio("Modo", ["📖 Bíblia", "🕯️ Leitura litúrgica"])
        st.divider()

    if modo.startswith("🕯️"):
        pagina_leitura_liturgica()
        return

    with st.sidebar:
        st.header("Navegação")
        st.caption("Use 0 para ver tudo do nível")

        # --- Livro ---
        opcoes_livro = ["0 — Todos os livros"] + livros
        livro_sel = st.selectbox("Livro", options=opcoes_livro, index=1)

        testamento_sel = None
        so_indice = False
        if livro_sel.startswith("0"):
            livro = None
            capitulo = None
            versiculo = 0
            testamento_sel = st.radio(
                "Testamento",
                options=["Bíblia inteira", "Antigo Testamento", "Novo Testamento"],
            )
            so_indice = st.checkbox("Mostrar só o índice", value=False)
        else:
            livro = livro_sel

            # --- Capítulo ---
            capitulos = listar_capitulos(livro)
            opcoes_cap = ["0 — Todos os capítulos"] + [str(c) for c in capitulos]
            cap_sel = st.selectbox("Capítulo", options=opcoes_cap, index=1)

            if cap_sel.startswith("0"):
                capitulo = None
                versiculo = 0
                so_indice = st.checkbox("Mostrar só o índice", value=False)
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

    # 1. Todos os livros → leitura contínua (ou índice, se marcado)
    if livro is None:
        por_testamento = listar_livros_por_testamento()

        if testamento_sel == "Bíblia inteira":
            nomes = livros
            titulo = "Todos os livros"
        else:
            nomes = por_testamento[testamento_sel]
            titulo = testamento_sel

        st.markdown(f"<div class='titulo-capitulo'>{titulo}</div>", unsafe_allow_html=True)

        if so_indice:
            for rotulo, lista in por_testamento.items():
                if rotulo != testamento_sel and testamento_sel != "Bíblia inteira":
                    continue
                st.markdown(f"<div class='subtitulo-secao'>{rotulo}</div>", unsafe_allow_html=True)
                cols = st.columns(2)
                for i, nome in enumerate(lista):
                    cols[i % 2].markdown(f"<div class='item-lista'>{nome}</div>", unsafe_allow_html=True)
            st.caption(f"{len(nomes)} livros")
            return

        if testamento_sel == "Bíblia inteira":
            st.caption("Leitura contínua de toda a Bíblia — pode demorar alguns segundos para carregar.")

        html, n_caps, n_vers = html_leitura_continua(obter_leitura_continua(nomes))
        st.markdown(f"<div class='bloco-capitulo'>{html}</div>", unsafe_allow_html=True)
        st.caption(f"{len(nomes)} livros • {n_caps} capítulos • {n_vers} versículos")
        return

    # 2. Todos os capítulos do livro → leitura contínua (ou índice, se marcado)
    if capitulo is None:
        capitulos = listar_capitulos(livro)
        st.markdown(f"<div class='titulo-capitulo'>{livro}</div>", unsafe_allow_html=True)

        if not capitulos:
            st.warning("Nenhum capítulo encontrado.")
            return

        if so_indice:
            cols = st.columns(6)
            for i, num in enumerate(capitulos):
                cols[i % 6].markdown(
                    f"<div class='item-lista' style='text-align:center'>{num}</div>",
                    unsafe_allow_html=True
                )
            st.caption(f"{len(capitulos)} capítulos")
            return

        html, n_caps, n_vers = html_leitura_continua(
            [{"livro": livro, "capitulos": obter_livro_completo(livro)}],
            mostrar_livro=False,
        )
        st.markdown(f"<div class='bloco-capitulo'>{html}</div>", unsafe_allow_html=True)
        st.caption(f"{n_caps} capítulos • {n_vers} versículos")
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