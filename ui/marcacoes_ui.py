# ui/marcacoes_ui.py
# Telas das marcações litúrgicas: cadastro, edição, backup/histórico e exibição do texto marcado.

from __future__ import annotations

import json
from html import escape

import streamlit as st

from core.leitura_liturgica import ler_referencia
from core.marcacoes import Filtros, Marca, cobertura, construir_indice, formatar_versiculos
from core.marcacoes_lote import interpretar_bloco, ordem_legivel, tem_segunda_por_padrao
from core.marcacoes_modelo import (
    CICLOS, CORES, DIAS_SEMANA, GRAUS, TEMPOS, TIPOS_LEITURA, rotulo_ciclo, rotulo_tipo,
)
from storage import marcacoes_db as db
from ui.render_marcado import altura_estimada, documento_html, filtrar_marcados

SEM = "—"
SEM_TIPO = "— sem tipo —"


# ------------------------------------------------------------
# Auxiliares
# ------------------------------------------------------------
def _luminancia(hex_: str) -> float:
    h = hex_.lstrip("#")
    r, g, b = (int(h[k:k + 2], 16) / 255 for k in (0, 2, 4))
    lin = lambda c: c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def chip_cor(cor: str) -> str:
    """Etiqueta com a cor litúrgica (preenchimento opaco; o texto escolhe claro/escuro conforme a cor)."""
    c = CORES.get(cor, {"fill": "#888888", "borda": "#bbbbbb"})
    texto = "#111111" if _luminancia(c["fill"]) > 0.30 else "#ffffff"
    return (
        f"<span style='background:{c['fill']};border:1px solid {c['borda']};border-radius:10px;"
        f"padding:0 .6rem;font-size:.8rem;font-weight:600;color:{texto}'>{escape(cor)}</span>"
    )


def _rotulo_celebracao(c: dict) -> str:
    extra = " · ".join(x for x in (c.get("grau"), c.get("tempo")) if x)
    arq = " [arquivada]" if c.get("arquivada") else ""
    return f"{c['nome']}" + (f"  ({extra})" if extra else "") + arq


def resumo_referencia(referencia: str) -> tuple[bool, str, list[str]]:
    """(interpretada?, descrição curta, avisos) — usado no cadastro e na listagem."""
    if not referencia.strip():
        return False, "", []
    res = ler_referencia(referencia)
    cob = cobertura(referencia)
    if not cob["interpretada"]:
        return False, "Não consegui interpretar esta referência (ela será salva, mas não pinta nada na Bíblia).", list(res["avisos"])
    n = sum(len(sg["versiculos"]) for t in res["trechos"] for sg in t["segmentos"])
    onde = "; ".join(f"{t['livro']} {t['referencia']}" for t in res["trechos"])
    aprox = " · divisão de frases aproximada" if cob["aproximado"] else ""
    return True, f"{onde} — {n} versículo(s){aprox}", list(res["avisos"])


def _mostrar_resumo(referencia: str):
    ok, texto, avisos = resumo_referencia(referencia)
    if not texto:
        return
    (st.success if ok else st.warning)(texto)
    if avisos:
        with st.expander(f"Avisos de precisão ({len(avisos)})"):
            for a in avisos:
                st.write("• " + a)


def _opcoes_tipo():
    return [SEM_TIPO] + [TIPOS_LEITURA[k] for k in TIPOS_LEITURA]


def _codigo_tipo(rotulo: str):
    if rotulo == SEM_TIPO:
        return None
    return next(k for k, v in TIPOS_LEITURA.items() if v == rotulo)


def _opcoes_ciclo():
    return [CICLOS[k] for k in CICLOS]


def _codigo_ciclo(rotulo: str) -> str:
    return next(k for k, v in CICLOS.items() if v == rotulo)


def _ou_none(v):
    return None if v == SEM else v


# ------------------------------------------------------------
# Página de marcações
# ------------------------------------------------------------
def pagina_marcacoes():
    st.subheader("🖍️ Marcações litúrgicas")
    st.caption(
        "Cada celebração reúne suas leituras, escritas na notação da CNBB. Nada é apagado: "
        "“arquivar” esconde da Bíblia mas preserva tudo, e toda edição guarda o estado anterior."
    )
    aba_nova, aba_lista, aba_backup = st.tabs(["➕ Nova celebração", "📋 Celebrações e leituras", "💾 Backup e histórico"])
    with aba_nova:
        _aba_nova()
    with aba_lista:
        _aba_lista()
    with aba_backup:
        _aba_backup()


# ---------- Nova celebração ----------
def _aba_nova():
    with st.form("form_nova_celebracao", clear_on_submit=True):
        nome = st.text_input("Nome", placeholder="Ex.: 2º Domingo do Advento")
        c1, c2 = st.columns(2)
        cor = c1.selectbox("Cor litúrgica", list(CORES))
        grau = c2.selectbox("Grau", [SEM] + GRAUS)
        c3, c4, c5 = st.columns(3)
        tempo = c3.selectbox("Tempo litúrgico", [SEM] + TEMPOS)
        semana = c4.number_input("Semana (0 = não se aplica)", min_value=0, max_value=34, value=0, step=1)
        dia = c5.selectbox("Dia da semana", [SEM] + DIAS_SEMANA)
        preceito = st.checkbox("Dia de preceito")
        obs = st.text_area("Observação (opcional)", height=70)
        enviar = st.form_submit_button("Criar celebração", type="primary")

    if enviar:
        try:
            novo_id = db.criar_celebracao({
                "nome": nome, "cor": cor, "tempo": _ou_none(tempo), "semana": semana,
                "dia_semana": _ou_none(dia), "grau": _ou_none(grau), "preceito": preceito, "observacao": obs,
            })
        except ValueError as e:
            st.error(str(e))
        else:
            st.session_state["cel_sel"] = novo_id
            st.success(f"Celebração “{nome.strip()}” criada. Agora adicione as leituras na aba **Celebrações e leituras**.")


# ---------- Celebrações e leituras ----------
def _aba_lista():
    arquivadas = st.checkbox("Mostrar arquivadas", value=False, key="ver_arq")
    celebracoes = db.listar_celebracoes(incluir_arquivadas=arquivadas)
    if not celebracoes:
        st.info("Nenhuma celebração cadastrada ainda.")
        return

    busca = st.text_input("Buscar pelo nome", key="busca_cel").strip().lower()
    if busca:
        celebracoes = [c for c in celebracoes if busca in c["nome"].lower()]
        if not celebracoes:
            st.info("Nada encontrado.")
            return

    ids = [c["id"] for c in celebracoes]
    por_id = {c["id"]: c for c in celebracoes}
    if st.session_state.get("cel_sel") not in ids:
        st.session_state["cel_sel"] = ids[0]
    cid = st.selectbox("Celebração", ids, key="cel_sel", format_func=lambda i: _rotulo_celebracao(por_id[i]))
    cel = por_id[cid]

    _cabecalho_celebracao(cel)
    _editar_celebracao(cel)
    st.markdown("##### Leituras")
    _lista_leituras(cel)
    _nova_leitura(cel)


def _cabecalho_celebracao(cel: dict):
    partes = [chip_cor(cel["cor"])]
    for x in (cel.get("grau"), cel.get("tempo"), f"{cel['semana']}ª semana" if cel.get("semana") else None, cel.get("dia_semana")):
        if x:
            partes.append(escape(x))
    if cel.get("preceito"):
        partes.append("⛪ dia de preceito")
    st.markdown(" · ".join(partes), unsafe_allow_html=True)
    if cel.get("observacao"):
        st.caption(cel["observacao"])

    if cel["arquivada"]:
        st.warning("Esta celebração está arquivada (não aparece na Bíblia).")
        if st.button("♻️ Restaurar celebração", key=f"rest_c{cel['id']}"):
            db.arquivar_celebracao(cel["id"], False)
            st.rerun()
    else:
        if st.button("🗄️ Arquivar celebração", key=f"arq_c{cel['id']}", help="Esconde da Bíblia; nada é apagado e dá para restaurar."):
            db.arquivar_celebracao(cel["id"], True)
            st.rerun()


def _editar_celebracao(cel: dict):
    with st.expander("✏️ Editar dados da celebração"):
        with st.form(f"form_edit_c{cel['id']}"):
            nome = st.text_input("Nome", value=cel["nome"])
            c1, c2 = st.columns(2)
            cores = list(CORES)
            cor = c1.selectbox("Cor litúrgica", cores, index=cores.index(cel["cor"]))
            graus = [SEM] + GRAUS
            grau = c2.selectbox("Grau", graus, index=graus.index(cel["grau"]) if cel["grau"] in graus else 0)
            c3, c4, c5 = st.columns(3)
            tempos = [SEM] + TEMPOS
            tempo = c3.selectbox("Tempo litúrgico", tempos, index=tempos.index(cel["tempo"]) if cel["tempo"] in tempos else 0)
            semana = c4.number_input("Semana (0 = não se aplica)", min_value=0, max_value=34, value=cel["semana"] or 0, step=1)
            dias = [SEM] + DIAS_SEMANA
            dia = c5.selectbox("Dia da semana", dias, index=dias.index(cel["dia_semana"]) if cel["dia_semana"] in dias else 0)
            preceito = st.checkbox("Dia de preceito", value=bool(cel["preceito"]))
            obs = st.text_area("Observação", value=cel["observacao"] or "", height=70)
            salvar = st.form_submit_button("Salvar alterações", type="primary")
        if salvar:
            try:
                db.atualizar_celebracao(cel["id"], {
                    "nome": nome, "cor": cor, "tempo": _ou_none(tempo), "semana": semana,
                    "dia_semana": _ou_none(dia), "grau": _ou_none(grau), "preceito": preceito, "observacao": obs,
                })
            except ValueError as e:
                st.error(str(e))
            else:
                st.success("Salvo (o estado anterior ficou no histórico).")
                st.rerun()


def _lista_leituras(cel: dict):
    leituras = db.listar_leituras(cel["id"], incluir_arquivadas=True)
    if not leituras:
        st.caption("Nenhuma leitura ainda.")
        return
    for l in leituras:
        tipo = rotulo_tipo(l["tipo"], l["tipo_outro"]) or "sem tipo"
        arq = " 🗄️ arquivada" if l["arquivada"] else ""
        ok, resumo, _ = resumo_referencia(l["referencia"])
        sinal = "✅" if ok else "⚠️"
        with st.expander(f"{sinal} {tipo} · {rotulo_ciclo(l['ciclo'])} · {l['referencia']}{arq}"):
            if resumo:
                (st.success if ok else st.warning)(resumo)
            with st.form(f"form_edit_l{l['id']}"):
                tipos = _opcoes_tipo()
                atual = TIPOS_LEITURA.get(l["tipo"], SEM_TIPO) if l["tipo"] else SEM_TIPO
                c1, c2 = st.columns(2)
                tipo_sel = c1.selectbox("Tipo (opcional)", tipos, index=tipos.index(atual))
                ciclos = _opcoes_ciclo()
                ciclo_sel = c2.selectbox("Ciclo", ciclos, index=ciclos.index(CICLOS[l["ciclo"]]))
                outro = st.text_input("Se o tipo for “Outro”, qual?", value=l["tipo_outro"] or "")
                ref = st.text_input("Referência (notação CNBB)", value=l["referencia"])
                obs = st.text_area("Observação", value=l["observacao"] or "", height=60)
                salvar = st.form_submit_button("Salvar leitura")
            if salvar:
                try:
                    db.atualizar_leitura(l["id"], {
                        "tipo": _codigo_tipo(tipo_sel), "tipo_outro": outro,
                        "ciclo": _codigo_ciclo(ciclo_sel), "referencia": ref, "observacao": obs,
                    })
                except ValueError as e:
                    st.error(str(e))
                else:
                    st.rerun()
            if l["observacao"]:
                st.caption(l["observacao"])
            if l["arquivada"]:
                if st.button("♻️ Restaurar leitura", key=f"rest_l{l['id']}"):
                    db.arquivar_leitura(l["id"], False)
                    st.rerun()
            else:
                if st.button("🗄️ Arquivar leitura", key=f"arq_l{l['id']}"):
                    db.arquivar_leitura(l["id"], True)
                    st.rerun()


def _salvar_nova_leitura(cid: int):
    s = st.session_state
    try:
        db.adicionar_leitura(cid, {
            "tipo": _codigo_tipo(s["nl_tipo"]), "tipo_outro": s.get("nl_outro", ""),
            "ciclo": _codigo_ciclo(s["nl_ciclo"]), "referencia": s.get("nl_ref", ""), "observacao": s.get("nl_obs", ""),
        })
    except ValueError as e:
        s["nl_msg"] = ("erro", str(e))
        return
    s["nl_msg"] = ("ok", f"Leitura “{s['nl_ref'].strip()}” adicionada.")
    s["nl_ref"] = ""          # limpa só a referência; tipo e ciclo ficam para a próxima leitura
    s["nl_obs"] = ""
    s["nl_outro"] = ""


def _estado_bloco(cid: int):
    """Interpreta o bloco a partir do que está na tela (usado pelo botão de salvar)."""
    s = st.session_state
    ciclo = _codigo_ciclo(s.get(f"lote_ciclo_{cid}", CICLOS["TODOS"]))
    ev_todos = ciclo in ("I", "II") and s.get(f"lote_evtodos_{cid}", True)
    return interpretar_bloco(
        s.get(f"lote_texto_{cid}", ""), s.get(f"lote_seg_{cid}", False), ciclo, ev_todos,
        db.listar_leituras(cid, incluir_arquivadas=True),
    )


def _salvar_bloco(cid: int):
    s = st.session_state
    res = _estado_bloco(cid)
    if not res.a_adicionar:
        s[f"lote_msg_{cid}"] = ("erro", "Nada para adicionar.")
        return
    try:
        ids = db.adicionar_leituras(cid, res.para_banco())
    except ValueError as e:
        s[f"lote_msg_{cid}"] = ("erro", str(e))
        return
    ignoradas = sum(1 for l in res.linhas if l.duplicada)
    extra = f" ({ignoradas} já existia(m) e foi(ram) ignorada(s))" if ignoradas else ""
    s[f"lote_msg_{cid}"] = ("ok", f"{len(ids)} leitura(s) adicionada(s){extra}.")
    s[f"lote_texto_{cid}"] = ""       # limpa o texto; ciclo e 2ª leitura ficam para o próximo bloco


def _bloco_leituras(cel: dict):
    """Cadastro rápido: uma referência por linha, o tipo vem da posição da linha."""
    cid = cel["id"]
    st.markdown("##### ⚡ Adicionar leituras em bloco")

    c1, c2 = st.columns(2)
    ciclo_rot = c1.selectbox("Ciclo (vale para o bloco todo)", _opcoes_ciclo(), key=f"lote_ciclo_{cid}")
    com_segunda = c2.checkbox(
        "Tem segunda leitura", value=tem_segunda_por_padrao(cel), key=f"lote_seg_{cid}",
        help="Já vem marcado para domingos e solenidades.",
    )
    ciclo = _codigo_ciclo(ciclo_rot)
    ev_todos = False
    if ciclo in ("I", "II"):
        ev_todos = st.checkbox(
            "Evangelho e aclamação valem para todos os anos (recomendado)", value=True, key=f"lote_evtodos_{cid}",
            help="Nos dias de semana só a 1ª leitura e o salmo mudam entre ano par e ímpar.",
        )

    st.caption(f"Uma referência por linha, nesta ordem: **{ordem_legivel(com_segunda)}**. "
               "Linha em branco pula a posição.")
    texto = st.text_area("Leituras", key=f"lote_texto_{cid}", height=150, label_visibility="collapsed",
                         placeholder="Is 9,1-6\nSl 95(96),1-2a.2b-3.11-12.13 (R. Lc 2,11)\nTt 2,11-14\nLc 2,10-11\nLc 2,1-14")

    res = interpretar_bloco(texto, com_segunda, ciclo, ev_todos, db.listar_leituras(cid, incluir_arquivadas=True))
    for erro in res.erros:
        st.error(erro)
    for aviso in res.avisos:
        st.caption("ℹ️ " + aviso)

    if res.linhas:
        linhas = []
        for l in res.linhas:
            if l.pulada:
                situacao = "— pulada"
            elif l.duplicada:
                situacao = "♻️ já cadastrada (será ignorada)"
            else:
                ok, resumo, _ = resumo_referencia(l.referencia)
                situacao = f"✅ {resumo}" if ok else "⚠️ não interpretada (será salva mesmo assim)"
            linhas.append({
                "Linha": l.posicao, "Tipo": TIPOS_LEITURA[l.tipo], "Ciclo": rotulo_ciclo(l.ciclo),
                "Referência": l.referencia or "—", "Situação": situacao,
            })
        st.dataframe(linhas, hide_index=True, width="stretch")

    n = len(res.a_adicionar)
    st.button(
        f"Adicionar {n} leitura(s)" if n else "Adicionar leituras",
        type="primary", key=f"lote_btn_{cid}", disabled=n == 0,
        on_click=_salvar_bloco, args=(cid,),
    )
    msg = st.session_state.pop(f"lote_msg_{cid}", None)
    if msg:
        (st.success if msg[0] == "ok" else st.error)(msg[1])


def _nova_leitura(cel: dict):
    if cel["arquivada"]:
        st.markdown("##### ➕ Adicionar leituras")
        st.caption("Restaure a celebração para adicionar leituras.")
        return
    _bloco_leituras(cel)
    st.divider()
    st.markdown("##### ➕ Adicionar leitura avulsa")
    st.caption("Para uma leitura fora do padrão: tipo “Outro”, observação, etc.")
    c1, c2 = st.columns(2)
    tipo_sel = c1.selectbox("Tipo (opcional)", _opcoes_tipo(), key="nl_tipo")
    c2.selectbox("Ciclo", _opcoes_ciclo(), key="nl_ciclo")
    if tipo_sel == TIPOS_LEITURA["outro"]:
        st.text_input("Qual?", key="nl_outro", placeholder="Ex.: Oração dos fiéis")
    if (tipo_sel in (TIPOS_LEITURA["evangelho"], TIPOS_LEITURA["aclamacao"])
            and _codigo_ciclo(st.session_state.get("nl_ciclo", CICLOS["TODOS"])) in ("I", "II")):
        st.info(
            "Dica: o Evangelho e a aclamação dos dias de semana não mudam entre ano par e ímpar "
            "(só a 1ª leitura e o salmo mudam). Normalmente se usa “Todos os anos”."
        )
    st.text_input(
        "Referência (notação CNBB)", key="nl_ref",
        placeholder="Ex.: Sl 23(24),1-2.3-4ab.5-6 (R. cf. 6)",
    )
    st.text_input("Observação (opcional)", key="nl_obs")
    _mostrar_resumo(st.session_state.get("nl_ref", ""))
    st.button("Adicionar leitura", type="primary", on_click=_salvar_nova_leitura, args=(cel["id"],))

    msg = st.session_state.pop("nl_msg", None)
    if msg:
        (st.success if msg[0] == "ok" else st.error)(msg[1])


# ---------- Backup e histórico ----------
def _aba_backup():
    st.markdown("**Onde estão os dados**")
    st.code(f"Banco:  {db.caminho_banco()}\nBackup: {db.caminho_backup()}", language=None)
    st.caption(
        "O banco impede apagar registros. O backup JSON é regravado a cada alteração; guarde-o junto do "
        "projeto (por exemplo, no GitHub). Se o app for publicado numa hospedagem em que o disco é "
        "temporário, use o botão abaixo para baixar uma cópia."
    )
    st.download_button(
        "⬇️ Baixar backup (JSON)",
        data=json.dumps(db.exportar_json(), ensure_ascii=False, indent=1),
        file_name="marcacoes_backup.json",
        mime="application/json",
    )

    st.markdown("**Restaurar de um backup** (só funciona se o banco estiver vazio)")
    arquivo = st.file_uploader("Arquivo marcacoes_backup.json", type="json", key="up_backup")
    if arquivo is not None and st.button("Restaurar"):
        try:
            n_c, n_l = db.restaurar_de_json(json.load(arquivo))
        except (ValueError, KeyError, json.JSONDecodeError) as e:
            st.error(f"Não foi possível restaurar: {e}")
        else:
            st.success(f"Restaurado: {n_c} celebrações e {n_l} leituras.")

    st.markdown("**Histórico de alterações**")
    eventos = db.historico(limite=100)
    if not eventos:
        st.caption("Nada registrado ainda.")
        return
    linhas = []
    for e in eventos:
        snap = e["snapshot"]
        linhas.append({
            "Quando (UTC)": e["registrado_em"].replace("T", " "),
            "O quê": f"{'Celebração' if e['entidade'] == 'celebracao' else 'Leitura'} #{e['entidade_id']}",
            "Ação": e["acao"],
            "Conteúdo": snap.get("nome") or snap.get("referencia") or "",
        })
    st.dataframe(linhas, width="stretch", hide_index=True)


# ------------------------------------------------------------
# Marcações na Bíblia
# ------------------------------------------------------------
@st.cache_resource(max_entries=32, show_spinner=False)
def _indice_cache(versao: int, cores, tempos, ciclos, tipos):
    """O índice não é 'picklável', por isso cache_resource; a chave inclui a versão do banco."""
    return construir_indice(Filtros(
        cores=set(cores) or None, tempos=set(tempos) or None,
        ciclos=set(ciclos) or None, tipos=set(tipos) or None,
    ))


def controles_marcacao_sidebar():
    """
    Desenha, na barra lateral, a opção 'Mostrar marcações' e os filtros.
    Devolve (indice | None, so_marcado).
    """
    mostrar = st.checkbox("🖍️ Mostrar marcações", value=False, key="mostrar_marcas")
    if not mostrar:
        return None, False
    with st.expander("Filtros das marcações"):
        cores = st.multiselect("Cor litúrgica", list(CORES), key="f_cores")
        tempos = st.multiselect("Tempo litúrgico", TEMPOS, key="f_tempos")
        ciclos = st.multiselect("Ano / ciclo", [k for k in CICLOS if k != "TODOS"],
                                format_func=lambda k: CICLOS[k], key="f_ciclos",
                                help="Inclui também as leituras marcadas como “Todos os anos”.")
        tipos = st.multiselect("Tipo de leitura", [""] + list(TIPOS_LEITURA),
                               format_func=lambda k: TIPOS_LEITURA.get(k, "(sem tipo)"), key="f_tipos")
    so_marcado = st.checkbox("Só o que tem marcação", value=True, key="so_marcado",
                             help="Em “todos os livros / capítulos”, mostra apenas os trechos marcados.")
    indice = _indice_cache(db.versao(), tuple(cores), tuple(tempos), tuple(ciclos), tuple(tipos))
    return indice, so_marcado


def _embutir_html(documento: str, altura: int):
    """
    Mostra um documento HTML completo num iframe. Usa st.iframe (Streamlit recente) e, em versões
    antigas, st.components.v1.html (descontinuado nas novas).
    SEGURANÇA: o HTML é embutido sem isolamento; por isso todo texto dinâmico (versículos, nomes
    digitados, balões) é escapado em ui/render_marcado.py e os estilos vêm só de constantes.
    """
    if hasattr(st, "iframe"):
        st.iframe(documento, height=altura)
    else:  # pragma: no cover
        import streamlit.components.v1 as components
        components.html(documento, height=altura, scrolling=True)


def mostrar_texto_marcado(blocos: list[dict], indice, *, mostrar_livro=True, mostrar_capitulo=True, so_marcado=False):
    """Exibe o texto com marcações (iframe) e, abaixo, a lista do que está marcado no trecho."""
    if so_marcado:
        blocos = filtrar_marcados(blocos, indice)
        if not blocos:
            st.info("Nenhuma marcação neste trecho (ou os filtros esconderam todas).")
            return

    _embutir_html(
        documento_html(blocos, indice, mostrar_livro=mostrar_livro, mostrar_capitulo=mostrar_capitulo),
        altura_estimada(blocos),
    )

    marcas: dict[int, Marca] = {}
    cruzamentos = []
    for b in blocos:
        for c in b["capitulos"]:
            for m in indice.marcas_no_capitulo(b["livro"], c["capitulo"]):
                marcas[m.leitura_id] = m
            for (a, bb), vers in indice.intersecoes(b["livro"], c["capitulo"]).items():
                cruzamentos.append((indice.marcas[a], indice.marcas[bb], f"{b['livro']} {c['capitulo']}", vers))

    if not marcas:
        st.caption("Nenhuma marcação neste texto.")
        return
    with st.expander(f"🖍️ Marcações neste trecho ({len(marcas)})"):
        for m in sorted(marcas.values(), key=lambda x: (x.celebracao.lower(), x.leitura_id)):
            aprox = " _(frases aproximadas)_" if m.aproximado else ""
            st.markdown(f"{chip_cor(m.cor)} {escape(m.descricao)}{aprox}", unsafe_allow_html=True)
        if cruzamentos:
            st.markdown("**Interseções**")
            for a, b, onde, vers in cruzamentos[:60]:
                st.write(f"• {a.celebracao} × {b.celebracao} — {onde}, {formatar_versiculos(vers)}")
            if len(cruzamentos) > 60:
                st.caption(f"… e mais {len(cruzamentos) - 60}.")