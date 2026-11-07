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
    CICLOS, CORES, DIAS_SEMANA, GRAUS, SEM_PASTA, TEMPOS, TIPOS_LEITURA, caminho_pasta, chave_ordem_celebracao, chave_ordem_natural,
    rotulo_ciclo, rotulo_tipo,
)
from storage import marcacoes_db as db
from ui.render_marcado import altura_estimada, documento_html, filtrar_marcados

SEM = "—"
SEM_TIPO = "— sem tipo —"
_ROTULO_ENTIDADE = {"celebracao": "Celebração", "leitura": "Leitura", "pasta": "Pasta"}


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
    aba_nova, aba_lista, aba_pastas, aba_backup = st.tabs(
        ["➕ Nova celebração", "📋 Celebrações e leituras", "🗂️ Pastas", "💾 Backup e histórico"]
    )
    with aba_nova:
        _aba_nova()
    with aba_lista:
        _aba_lista()
    with aba_pastas:
        _aba_pastas()
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


# ---------- Pastas ----------
def _msg_pastas(tipo: str, texto: str):
    st.session_state["pastas_msg"] = (tipo, texto)


def _acao_pastas(acao, texto_ok: str) -> bool:
    """Executa uma ação do banco e deixa a mensagem (sucesso ou erro) para a próxima tela."""
    try:
        acao()
    except ValueError as e:
        _msg_pastas("erro", str(e))
        return False
    _msg_pastas("ok", texto_ok)
    return True


def _ir_pasta(pasta_id):
    st.session_state["pasta_atual"] = pasta_id
    st.session_state["pasta_cel_aberta"] = None


def _abrir_celebracao(cid):
    st.session_state["pasta_cel_aberta"] = cid


def _cb_criar_pasta(pai_id):
    nome = st.session_state.get(f"pasta_nova_{pai_id or 0}", "")
    _acao_pastas(lambda: db.criar_pasta(nome, pai_id), f"Pasta “{nome.strip()}” criada.")


def _cb_renomear_pasta(pid):
    nome = st.session_state.get(f"pasta_ren_{pid}", "")
    _acao_pastas(lambda: db.renomear_pasta(pid, nome), "Pasta renomeada.")


def _cb_mover_pasta(pid):
    destino = st.session_state.get(f"pasta_mvpai_{pid}", 0) or None
    _acao_pastas(lambda: db.mover_pasta(pid, destino), "Pasta movida.")


def _cb_arquivar_pasta(pid, pai_id):
    if _acao_pastas(lambda: db.arquivar_pasta(pid), "Pasta arquivada (estava vazia)."):
        _ir_pasta(pai_id)


def _cb_cor_pasta(pid):
    cor = st.session_state.get(f"pasta_cor_{pid}", SEM)
    _acao_pastas(lambda: db.definir_cor_pasta(pid, None if cor == SEM else cor), "Cor da pasta atualizada.")


def _contagem_pasta(n_sub: int, n_cel: int) -> str:
    """Uma contagem só: subpastas, se tiver; senão, celebrações. Pasta vazia não leva texto."""
    if n_sub:
        return f"{n_sub} subpasta" + ("" if n_sub == 1 else "s")
    if n_cel:
        return f"{n_cel} celebraç" + ("ão" if n_cel == 1 else "ões")
    return ""


def _css_pastas_coloridas(pastas: list[dict]) -> str:
    """Contorno colorido nos botões das pastas que têm cor (sem texto, sem ocupar espaço)."""
    regras = []
    for p in pastas:
        c = CORES.get(p.get("cor") or "")
        if not c:
            continue
        cor = c["borda"] if _luminancia(c["fill"]) < 0.05 else c["fill"]   # o preto usa a borda clara
        regras.append(
            f".st-key-pasta_ir_{p['id']} button{{border:2px solid {cor} !important;"
            f"box-shadow:0 0 8px {cor}99 !important;}}"
        )
    return f"<style>{''.join(regras)}</style>" if regras else ""


def _cb_restaurar_pasta(pid):
    _acao_pastas(lambda: db.arquivar_pasta(pid, False), "Pasta restaurada.")


def _cb_mover_celebracoes(ids_chave: str, pasta_id):
    s = st.session_state
    ids = list(s.get(ids_chave, []))
    if not ids:
        return
    try:
        n = db.mover_celebracoes(ids, pasta_id)
    except ValueError as e:
        _msg_pastas("erro", str(e))
        return
    _msg_pastas("ok", f"{n} celebração(ões) movida(s).")
    s[ids_chave] = []


def _cb_mover_uma(cid: int, chave: str):
    destino = st.session_state.get(chave, 0) or None
    try:
        n = db.mover_celebracoes([cid], destino)
    except ValueError as e:
        _msg_pastas("erro", str(e))
        return
    _msg_pastas("ok", "Celebração movida." if n else "A celebração já estava nessa pasta.")


def _descendentes_ui(por_id: dict, id_: int) -> set:
    achados, fila = set(), [id_]
    while fila:
        atual = fila.pop()
        for p in por_id.values():
            if p["pai_id"] == atual and p["id"] not in achados:
                achados.add(p["id"])
                fila.append(p["id"])
    return achados


def _aba_pastas():
    s = st.session_state
    msg = s.pop("pastas_msg", None)
    if msg:
        (st.success if msg[0] == "ok" else st.error)(msg[1])

    todas_pastas = db.listar_pastas(incluir_arquivadas=True)
    pastas = [p for p in todas_pastas if not p["arquivada"]]
    por_id = {p["id"]: p for p in pastas}
    caminhos = {p["id"]: caminho_pasta(por_id, p["id"]) for p in pastas}

    st.caption(
        "Organize as celebrações em pastas com os nomes que você quiser (e subpastas dentro delas). "
        "Dentro de cada celebração, as leituras aparecem separadas por ciclo automaticamente. "
        "Nada é apagado: pasta só pode ser arquivada quando está vazia."
    )
    ver_arq = st.checkbox("Mostrar celebrações arquivadas", value=False, key="pastas_ver_arq")

    todas_cel = sorted(db.listar_celebracoes(incluir_arquivadas=True), key=chave_ordem_celebracao)   # dia da semana
    cel_por_id = {c["id"]: c for c in todas_cel}
    visiveis = [c for c in todas_cel if ver_arq or not c["arquivada"]]
    mapa = db.pastas_das_celebracoes()

    def pasta_de(cid):
        pid = mapa.get(cid)
        return pid if pid in por_id else None

    # --- celebração aberta: visão com subpastas por ciclo ---
    aberta = s.get("pasta_cel_aberta")
    if aberta in cel_por_id:
        _detalhe_celebracao_pastas(cel_por_id[aberta], por_id, caminhos, pasta_de(aberta))
        return

    atual = s.get("pasta_atual")
    if atual not in por_id:
        atual = s["pasta_atual"] = None

    # --- onde estou ---
    trilha, x = [], atual
    while x is not None:
        trilha.append(por_id[x]["nome"])
        x = por_id[x]["pai_id"]
    caminho_txt = " › ".join(["Início"] + trilha[::-1])
    filhas = [p for p in pastas if p["pai_id"] == atual]
    st.markdown(
        f"<div style='font-size:1.05rem;margin:.4rem 0'>📍 <b>{escape(caminho_txt)}</b></div>"
        + _css_pastas_coloridas(filhas),
        unsafe_allow_html=True,
    )
    if atual is not None:
        c1, c2, _ = st.columns([1, 1, 3])
        c1.button("🏠 Início", key="pasta_home", on_click=_ir_pasta, args=(None,))
        c2.button("⬆️ Subir", key="pasta_up", on_click=_ir_pasta, args=(por_id[atual]["pai_id"],))

    # --- subpastas (a seção só aparece se houver) ---
    if filhas:
        cols = st.columns(2)
        for i, p in enumerate(filhas):
            n_sub = sum(1 for q in pastas if q["pai_id"] == p["id"])
            n_cel = sum(1 for c in visiveis if pasta_de(c["id"]) == p["id"])
            contagem = _contagem_pasta(n_sub, n_cel)
            rotulo = f"📁 {p['nome']} - {contagem}" if contagem else f"📁 {p['nome']}"
            cols[i % 2].button(rotulo, key=f"pasta_ir_{p['id']}", on_click=_ir_pasta, args=(p["id"],))

    # --- celebrações desta pasta ---
    aqui = [c for c in visiveis if pasta_de(c["id"]) == atual]
    n_leituras: dict[int, int] = {}
    for l in db.listar_leituras():
        n_leituras[l["celebracao_id"]] = n_leituras.get(l["celebracao_id"], 0) + 1
    if aqui:
        st.markdown("##### 🕊️ Celebrações " + ("nesta pasta" if atual is not None else "sem pasta"))
    for c in aqui:
        esq, dir_ = st.columns([5, 1])
        info = " · ".join(t for t in (c.get("grau"), c.get("tempo"), f"{n_leituras.get(c['id'], 0)} leitura(s)") if t)
        arq = " 🗄️ arquivada" if c["arquivada"] else ""
        esq.markdown(
            f"{chip_cor(c['cor'])} <b>{escape(c['nome'])}</b> "
            f"<span style='opacity:.7'>{escape(info)}{arq}</span>", unsafe_allow_html=True,
        )
        dir_.button("Abrir", key=f"pasta_abrir_{c['id']}", on_click=_abrir_celebracao, args=(c["id"],))

    # --- mover várias celebrações para cá ---
    destino_txt = "esta pasta" if atual is not None else "“sem pasta”"
    with st.expander(f"📥 Mover celebrações para {destino_txt}"):
        candidatas = [c["id"] for c in visiveis if pasta_de(c["id"]) != atual]
        if not candidatas:
            st.caption("Todas as celebrações já estão aqui.")
        else:
            chave = f"pasta_mvcel_{atual or 0}"
            s[chave] = [i for i in s.get(chave, []) if i in candidatas]     # evita valores que já não são opção
            st.multiselect(
                "Escolha as celebrações", candidatas, key=chave,
                format_func=lambda i: f"{cel_por_id[i]['nome']}  —  📁 {caminho_pasta(por_id, pasta_de(i))}",
            )
            st.button(f"Mover para {destino_txt}", type="primary", key=f"pasta_mvcel_btn_{atual or 0}",
                      disabled=not s[chave], on_click=_cb_mover_celebracoes, args=(chave, atual))

    # --- nova pasta ---
    st.divider()
    onde = f"dentro de “{por_id[atual]['nome']}”" if atual is not None else "no início"
    with st.form(f"form_pasta_nova_{atual or 0}", clear_on_submit=True):
        st.text_input(f"Nova pasta {onde}", key=f"pasta_nova_{atual or 0}", placeholder="Ex.: Solenidades de data móvel")
        st.form_submit_button("➕ Criar pasta", type="primary", on_click=_cb_criar_pasta, args=(atual,))

    # --- gerenciar a pasta atual ---
    if atual is not None:
        pasta = por_id[atual]
        with st.expander("⚙️ Gerenciar esta pasta"):
            st.text_input("Nome", value=pasta["nome"], key=f"pasta_ren_{atual}")
            st.button("Renomear", key=f"pasta_ren_btn_{atual}", on_click=_cb_renomear_pasta, args=(atual,))

            opcoes_cor = [SEM] + list(CORES)
            chave_cor = f"pasta_cor_{atual}"
            if s.get(chave_cor, SEM) not in opcoes_cor:
                s.pop(chave_cor, None)
            st.selectbox(
                "Cor de destaque (contorno na lista de pastas)", opcoes_cor, key=chave_cor,
                index=opcoes_cor.index(pasta.get("cor") or SEM),
                format_func=lambda c: "(sem cor)" if c == SEM else c,
                on_change=_cb_cor_pasta, args=(atual,),
            )

            proibidas = {atual} | _descendentes_ui(por_id, atual)
            opcoes = [0] + sorted((i for i in por_id if i not in proibidas), key=lambda i: chave_ordem_natural(caminhos[i]))
            chave_pai = f"pasta_mvpai_{atual}"
            if s.get(chave_pai, 0) not in opcoes:
                s.pop(chave_pai, None)
            st.selectbox(
                "Mover esta pasta (com tudo o que tem dentro) para", opcoes, key=chave_pai,
                index=opcoes.index(pasta["pai_id"] or 0),
                format_func=lambda i: "(início)" if i == 0 else caminhos[i],
            )
            st.button("Mover pasta", key=f"pasta_mv_btn_{atual}", on_click=_cb_mover_pasta, args=(atual,))

            vazia = not filhas and not any(v == atual for v in mapa.values())
            st.button(
                "🗄️ Arquivar pasta", key=f"pasta_arq_{atual}", disabled=not vazia,
                help="Só é possível arquivar uma pasta vazia (sem subpastas nem celebrações).",
                on_click=_cb_arquivar_pasta, args=(atual, pasta["pai_id"]),
            )
            if not vazia:
                st.caption("Para arquivar, primeiro mova as celebrações e as subpastas para outro lugar.")

    # --- pastas arquivadas (restaurar) ---
    arquivadas = [p for p in todas_pastas if p["arquivada"]]
    if atual is None and arquivadas:
        todas_por_id = {p["id"]: p for p in todas_pastas}
        with st.expander(f"🗄️ Pastas arquivadas ({len(arquivadas)})"):
            for p in arquivadas:
                a, b = st.columns([4, 1])
                a.text(caminho_pasta(todas_por_id, p["id"]))
                b.button("♻️ Restaurar", key=f"pasta_rest_{p['id']}", on_click=_cb_restaurar_pasta, args=(p["id"],))


def _detalhe_celebracao_pastas(cel: dict, por_id: dict, caminhos: dict, pasta_id):
    """Uma celebração por dentro: leituras agrupadas em 'subpastas' por ciclo (automático)."""
    st.button("⬅️ Voltar", key="pasta_voltar", on_click=_abrir_celebracao, args=(None,))
    extras = [t for t in (cel.get("grau"), cel.get("tempo"), f"{cel['semana']}ª semana" if cel.get("semana") else None,
                          cel.get("dia_semana")) if t]
    st.markdown(
        f"<h4 style='margin:.6rem 0 .2rem'>{escape(cel['nome'])}</h4>"
        f"{chip_cor(cel['cor'])} {escape(' · '.join(extras))}", unsafe_allow_html=True,
    )
    st.caption("📁 " + caminho_pasta(por_id, pasta_id))

    with st.expander("📁 Mover para outra pasta"):
        opcoes = [0] + sorted(por_id, key=lambda i: chave_ordem_natural(caminhos[i]))
        chave = f"pasta_mv1_{cel['id']}"
        if st.session_state.get(chave, 0) not in opcoes:
            st.session_state.pop(chave, None)
        st.selectbox(
            "Destino", opcoes, key=chave, index=opcoes.index(pasta_id or 0),
            format_func=lambda i: SEM_PASTA if i == 0 else caminhos[i],
        )
        st.button("Mover", key=f"pasta_mv1_btn_{cel['id']}", on_click=_cb_mover_uma, args=(cel["id"], chave))

    leituras = db.listar_leituras(cel["id"])
    st.markdown("##### Leituras por ciclo")
    if not leituras:
        st.caption("Esta celebração ainda não tem leituras.")
    ordem_tipo = {k: i for i, k in enumerate(TIPOS_LEITURA)}
    por_ciclo: dict[str, list] = {}
    for l in leituras:
        por_ciclo.setdefault(l["ciclo"], []).append(l)
    for ciclo in CICLOS:
        grupo = por_ciclo.get(ciclo)
        if not grupo:
            continue
        grupo.sort(key=lambda l: (ordem_tipo.get(l["tipo"], 99), l["id"]))
        with st.expander(f"📁 {rotulo_ciclo(ciclo)}  ·  {len(grupo)} leitura(s)", expanded=True):
            for l in grupo:
                tipo = rotulo_tipo(l["tipo"], l["tipo_outro"]) or "sem tipo"
                sinal = "✅" if cobertura(l["referencia"])["interpretada"] else "⚠️"
                st.markdown(f"{sinal} <b>{escape(tipo)}</b> — {escape(l['referencia'])}", unsafe_allow_html=True)
                if l["observacao"]:
                    st.caption(l["observacao"])
    st.caption("Para editar ou arquivar leituras, use a aba “Celebrações e leituras”.")


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
            "O quê": f"{_ROTULO_ENTIDADE.get(e['entidade'], e['entidade'])} #{e['entidade_id']}",
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