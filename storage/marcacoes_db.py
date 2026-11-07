# storage/marcacoes_db.py
# Armazenamento PERMANENTE das marcações (SQLite).
#
# Garantias:
#  - Nada é apagado: gatilhos do banco bloqueiam DELETE; "excluir" = arquivar (reversível).
#  - Toda alteração grava uma cópia do estado anterior em 'historico' (que também é imutável).
#  - A cada gravação é escrito um backup legível em JSON (dados/marcacoes_backup.json).
#
# Local do banco: variável de ambiente BIBLIA_DB, ou dados/marcacoes.db na raiz do projeto.

from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from core.marcacoes_modelo import (
    caminho_pasta, chave_ordem_natural, normalizar_celebracao, normalizar_cor_pasta, normalizar_leitura,
    normalizar_nome_pasta,
)

RAIZ = Path(__file__).resolve().parent.parent

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS celebracoes (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    nome          TEXT    NOT NULL,
    cor           TEXT    NOT NULL,
    tempo         TEXT,
    semana        INTEGER,
    dia_semana    TEXT,
    grau          TEXT,
    preceito      INTEGER NOT NULL DEFAULT 0,
    observacao    TEXT,
    arquivada     INTEGER NOT NULL DEFAULT 0,
    criado_em     TEXT    NOT NULL,
    atualizado_em TEXT    NOT NULL
);
CREATE TABLE IF NOT EXISTS leituras (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    celebracao_id INTEGER NOT NULL REFERENCES celebracoes(id),
    tipo          TEXT,
    tipo_outro    TEXT,
    ciclo         TEXT    NOT NULL DEFAULT 'TODOS',
    referencia    TEXT    NOT NULL,
    observacao    TEXT,
    arquivada     INTEGER NOT NULL DEFAULT 0,
    criado_em     TEXT    NOT NULL,
    atualizado_em TEXT    NOT NULL
);
CREATE TABLE IF NOT EXISTS historico (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    entidade      TEXT    NOT NULL,
    entidade_id   INTEGER NOT NULL,
    acao          TEXT    NOT NULL,
    snapshot      TEXT    NOT NULL,
    registrado_em TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_leituras_cel ON leituras(celebracao_id);

-- Pastas (organização escolhida pelo usuário). Tabelas NOVAS: celebracoes e leituras não são alteradas.
CREATE TABLE IF NOT EXISTS pastas (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    nome          TEXT    NOT NULL,
    pai_id        INTEGER REFERENCES pastas(id),
    cor           TEXT,
    arquivada     INTEGER NOT NULL DEFAULT 0,
    criado_em     TEXT    NOT NULL,
    atualizado_em TEXT    NOT NULL
);
-- Em que pasta está cada celebração (sem linha, ou pasta_id vazio = "sem pasta").
CREATE TABLE IF NOT EXISTS celebracao_pasta (
    celebracao_id INTEGER PRIMARY KEY REFERENCES celebracoes(id),
    pasta_id      INTEGER REFERENCES pastas(id)
);

CREATE TRIGGER IF NOT EXISTS proibe_delete_celebracoes BEFORE DELETE ON celebracoes
BEGIN SELECT RAISE(ABORT, 'Marcações são permanentes: arquive em vez de apagar.'); END;
CREATE TRIGGER IF NOT EXISTS proibe_delete_leituras BEFORE DELETE ON leituras
BEGIN SELECT RAISE(ABORT, 'Marcações são permanentes: arquive em vez de apagar.'); END;
CREATE TRIGGER IF NOT EXISTS proibe_delete_pastas BEFORE DELETE ON pastas
BEGIN SELECT RAISE(ABORT, 'Pastas são permanentes: arquive em vez de apagar.'); END;
CREATE TRIGGER IF NOT EXISTS proibe_delete_celebracao_pasta BEFORE DELETE ON celebracao_pasta
BEGIN SELECT RAISE(ABORT, 'Para tirar da pasta, mova a celebração para "sem pasta".'); END;
CREATE TRIGGER IF NOT EXISTS proibe_delete_historico BEFORE DELETE ON historico
BEGIN SELECT RAISE(ABORT, 'O histórico é imutável.'); END;
CREATE TRIGGER IF NOT EXISTS proibe_update_historico BEFORE UPDATE ON historico
BEGIN SELECT RAISE(ABORT, 'O histórico é imutável.'); END;
"""


def caminho_banco() -> Path:
    return Path(os.environ.get("BIBLIA_DB") or RAIZ / "dados" / "marcacoes.db")


def caminho_backup() -> Path:
    return caminho_banco().with_name("marcacoes_backup.json")


def _agora() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def _conexao():
    caminho = caminho_banco()
    caminho.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(caminho, timeout=15)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    con.executescript(_ESQUEMA)
    if "cor" not in {r["name"] for r in con.execute("PRAGMA table_info(pastas)")}:
        con.execute("ALTER TABLE pastas ADD COLUMN cor TEXT")      # migração aditiva (bancos com pastas antigas)
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def _linha(con, tabela: str, id_: int) -> Optional[dict]:
    r = con.execute(f"SELECT * FROM {tabela} WHERE id = ?", (id_,)).fetchone()
    return dict(r) if r else None


def _registrar(con, entidade: str, id_: int, acao: str, snapshot: dict):
    con.execute(
        "INSERT INTO historico (entidade, entidade_id, acao, snapshot, registrado_em) VALUES (?,?,?,?,?)",
        (entidade, id_, acao, json.dumps(snapshot, ensure_ascii=False), _agora()),
    )


# ------------------------------------------------------------
# Celebrações
# ------------------------------------------------------------
def criar_celebracao(dados: dict) -> int:
    d = normalizar_celebracao(dados)
    agora = _agora()
    with _conexao() as con:
        cur = con.execute(
            """INSERT INTO celebracoes (nome, cor, tempo, semana, dia_semana, grau, preceito, observacao,
                                        criado_em, atualizado_em)
               VALUES (:nome,:cor,:tempo,:semana,:dia_semana,:grau,:preceito,:observacao,:t,:t)""",
            {**d, "t": agora},
        )
        id_ = cur.lastrowid
        _registrar(con, "celebracao", id_, "criada", _linha(con, "celebracoes", id_))
    _salvar_backup()
    return id_


def atualizar_celebracao(id_: int, dados: dict) -> None:
    d = normalizar_celebracao(dados)
    with _conexao() as con:
        antes = _linha(con, "celebracoes", id_)
        if not antes:
            raise ValueError(f"Celebração {id_} não existe.")
        _registrar(con, "celebracao", id_, "editada (estado anterior)", antes)
        con.execute(
            """UPDATE celebracoes SET nome=:nome, cor=:cor, tempo=:tempo, semana=:semana, dia_semana=:dia_semana,
                      grau=:grau, preceito=:preceito, observacao=:observacao, atualizado_em=:t WHERE id=:id""",
            {**d, "t": _agora(), "id": id_},
        )
    _salvar_backup()


def arquivar_celebracao(id_: int, arquivada: bool = True) -> None:
    """Arquiva (ou restaura) a celebração. As leituras ficam preservadas."""
    with _conexao() as con:
        antes = _linha(con, "celebracoes", id_)
        if not antes:
            raise ValueError(f"Celebração {id_} não existe.")
        _registrar(con, "celebracao", id_, "arquivada" if arquivada else "restaurada", antes)
        con.execute("UPDATE celebracoes SET arquivada=?, atualizado_em=? WHERE id=?",
                    (1 if arquivada else 0, _agora(), id_))
    _salvar_backup()


def obter_celebracao(id_: int) -> Optional[dict]:
    with _conexao() as con:
        return _linha(con, "celebracoes", id_)


def listar_celebracoes(incluir_arquivadas: bool = False) -> list[dict]:
    sql = "SELECT * FROM celebracoes" + ("" if incluir_arquivadas else " WHERE arquivada = 0") + " ORDER BY nome COLLATE NOCASE, id"
    with _conexao() as con:
        return [dict(r) for r in con.execute(sql)]


# ------------------------------------------------------------
# Leituras
# ------------------------------------------------------------
def adicionar_leitura(celebracao_id: int, dados: dict) -> int:
    d = normalizar_leitura(dados)
    agora = _agora()
    with _conexao() as con:
        if not _linha(con, "celebracoes", celebracao_id):
            raise ValueError(f"Celebração {celebracao_id} não existe.")
        cur = con.execute(
            """INSERT INTO leituras (celebracao_id, tipo, tipo_outro, ciclo, referencia, observacao, criado_em, atualizado_em)
               VALUES (:cid,:tipo,:tipo_outro,:ciclo,:referencia,:observacao,:t,:t)""",
            {**d, "cid": celebracao_id, "t": agora},
        )
        id_ = cur.lastrowid
        _registrar(con, "leitura", id_, "criada", _linha(con, "leituras", id_))
    _salvar_backup()
    return id_


def adicionar_leituras(celebracao_id: int, lista: list[dict]) -> list[int]:
    """
    Adiciona várias leituras de uma vez, de forma ATÔMICA: se qualquer uma for inválida,
    nenhuma é salva. Grava o backup JSON uma única vez no final.
    """
    dados = [normalizar_leitura(d) for d in lista]       # valida tudo antes de gravar
    agora = _agora()
    ids = []
    with _conexao() as con:
        if not _linha(con, "celebracoes", celebracao_id):
            raise ValueError(f"Celebração {celebracao_id} não existe.")
        for d in dados:
            cur = con.execute(
                """INSERT INTO leituras (celebracao_id, tipo, tipo_outro, ciclo, referencia, observacao, criado_em, atualizado_em)
                   VALUES (:cid,:tipo,:tipo_outro,:ciclo,:referencia,:observacao,:t,:t)""",
                {**d, "cid": celebracao_id, "t": agora},
            )
            _registrar(con, "leitura", cur.lastrowid, "criada", _linha(con, "leituras", cur.lastrowid))
            ids.append(cur.lastrowid)
    if ids:
        _salvar_backup()
    return ids


def atualizar_leitura(id_: int, dados: dict) -> None:
    d = normalizar_leitura(dados)
    with _conexao() as con:
        antes = _linha(con, "leituras", id_)
        if not antes:
            raise ValueError(f"Leitura {id_} não existe.")
        _registrar(con, "leitura", id_, "editada (estado anterior)", antes)
        con.execute(
            """UPDATE leituras SET tipo=:tipo, tipo_outro=:tipo_outro, ciclo=:ciclo, referencia=:referencia,
                      observacao=:observacao, atualizado_em=:t WHERE id=:id""",
            {**d, "t": _agora(), "id": id_},
        )
    _salvar_backup()


def arquivar_leitura(id_: int, arquivada: bool = True) -> None:
    with _conexao() as con:
        antes = _linha(con, "leituras", id_)
        if not antes:
            raise ValueError(f"Leitura {id_} não existe.")
        _registrar(con, "leitura", id_, "arquivada" if arquivada else "restaurada", antes)
        con.execute("UPDATE leituras SET arquivada=?, atualizado_em=? WHERE id=?",
                    (1 if arquivada else 0, _agora(), id_))
    _salvar_backup()


def listar_leituras(celebracao_id: Optional[int] = None, incluir_arquivadas: bool = False) -> list[dict]:
    where, params = [], []
    if celebracao_id is not None:
        where.append("celebracao_id = ?"); params.append(celebracao_id)
    if not incluir_arquivadas:
        where.append("arquivada = 0")
    sql = "SELECT * FROM leituras" + (" WHERE " + " AND ".join(where) if where else "") + " ORDER BY celebracao_id, id"
    with _conexao() as con:
        return [dict(r) for r in con.execute(sql, params)]


# ------------------------------------------------------------
# Pastas
# ------------------------------------------------------------
def _pastas_por_id(con, incluir_arquivadas: bool = True) -> dict:
    sql = "SELECT * FROM pastas" + ("" if incluir_arquivadas else " WHERE arquivada = 0")
    return {r["id"]: dict(r) for r in con.execute(sql)}


def _nome_ocupado(con, pai_id: Optional[int], nome: str, ignorar_id: Optional[int] = None) -> bool:
    """Já existe, no mesmo nível, outra pasta ativa com este nome (sem diferenciar maiúsculas)?"""
    alvo = nome.casefold()
    for r in con.execute("SELECT id, nome FROM pastas WHERE pai_id IS ? AND arquivada = 0", (pai_id,)):
        if r["id"] != ignorar_id and r["nome"].casefold() == alvo:
            return True
    return False


def _descendentes(con, id_: int) -> set:
    achados, fila = set(), [id_]
    while fila:
        atual = fila.pop()
        for r in con.execute("SELECT id FROM pastas WHERE pai_id = ?", (atual,)):
            if r["id"] not in achados:
                achados.add(r["id"])
                fila.append(r["id"])
    return achados


def _pai_valido(con, pai_id: Optional[int]) -> None:
    if pai_id is None:
        return
    pai = _linha(con, "pastas", pai_id)
    if not pai or pai["arquivada"]:
        raise ValueError("A pasta de destino não existe ou está arquivada.")


def criar_pasta(nome: str, pai_id: Optional[int] = None, cor: Optional[str] = None) -> int:
    nome = normalizar_nome_pasta(nome)
    cor = normalizar_cor_pasta(cor)
    agora = _agora()
    with _conexao() as con:
        _pai_valido(con, pai_id)
        if _nome_ocupado(con, pai_id, nome):
            raise ValueError(f"Já existe uma pasta “{nome}” neste nível.")
        cur = con.execute(
            "INSERT INTO pastas (nome, pai_id, cor, criado_em, atualizado_em) VALUES (?,?,?,?,?)",
            (nome, pai_id, cor, agora, agora),
        )
        id_ = cur.lastrowid
        _registrar(con, "pasta", id_, "criada", _linha(con, "pastas", id_))
    _salvar_backup()
    return id_


def renomear_pasta(id_: int, nome: str) -> None:
    nome = normalizar_nome_pasta(nome)
    with _conexao() as con:
        antes = _linha(con, "pastas", id_)
        if not antes:
            raise ValueError(f"Pasta {id_} não existe.")
        if _nome_ocupado(con, antes["pai_id"], nome, ignorar_id=id_):
            raise ValueError(f"Já existe uma pasta “{nome}” neste nível.")
        _registrar(con, "pasta", id_, "renomeada (estado anterior)", antes)
        con.execute("UPDATE pastas SET nome=?, atualizado_em=? WHERE id=?", (nome, _agora(), id_))
    _salvar_backup()


def definir_cor_pasta(id_: int, cor: Optional[str]) -> None:
    """Define (ou remove, com None) a cor de destaque da pasta."""
    cor = normalizar_cor_pasta(cor)
    with _conexao() as con:
        antes = _linha(con, "pastas", id_)
        if not antes:
            raise ValueError(f"Pasta {id_} não existe.")
        if antes["cor"] == cor:
            return
        _registrar(con, "pasta", id_, "cor alterada (estado anterior)", antes)
        con.execute("UPDATE pastas SET cor=?, atualizado_em=? WHERE id=?", (cor, _agora(), id_))
    _salvar_backup()


def mover_pasta(id_: int, novo_pai_id: Optional[int]) -> None:
    """Move a pasta (com tudo o que está dentro) para dentro de outra, ou para a raiz (None)."""
    with _conexao() as con:
        antes = _linha(con, "pastas", id_)
        if not antes:
            raise ValueError(f"Pasta {id_} não existe.")
        if novo_pai_id == antes["pai_id"]:
            return
        if novo_pai_id is not None and (novo_pai_id == id_ or novo_pai_id in _descendentes(con, id_)):
            raise ValueError("Uma pasta não pode ser movida para dentro dela mesma.")
        _pai_valido(con, novo_pai_id)
        if _nome_ocupado(con, novo_pai_id, antes["nome"], ignorar_id=id_):
            raise ValueError(f"O destino já tem uma pasta chamada “{antes['nome']}”.")
        _registrar(con, "pasta", id_, "movida (estado anterior)", antes)
        con.execute("UPDATE pastas SET pai_id=?, atualizado_em=? WHERE id=?", (novo_pai_id, _agora(), id_))
    _salvar_backup()


def arquivar_pasta(id_: int, arquivada: bool = True) -> None:
    """
    Arquiva (ou restaura) a pasta. Só arquiva pasta VAZIA (sem subpastas ativas e sem celebrações),
    para que nenhuma celebração fique escondida sem querer.
    """
    with _conexao() as con:
        antes = _linha(con, "pastas", id_)
        if not antes:
            raise ValueError(f"Pasta {id_} não existe.")
        if arquivada:
            if con.execute("SELECT 1 FROM pastas WHERE pai_id=? AND arquivada=0", (id_,)).fetchone():
                raise ValueError("A pasta tem subpastas. Mova ou arquive as subpastas primeiro.")
            if con.execute("SELECT 1 FROM celebracao_pasta WHERE pasta_id=?", (id_,)).fetchone():
                raise ValueError("A pasta ainda tem celebrações (inclusive arquivadas). Mova-as antes de arquivar.")
        else:
            _pai_valido(con, antes["pai_id"])
            if _nome_ocupado(con, antes["pai_id"], antes["nome"], ignorar_id=id_):
                raise ValueError(f"Já existe outra pasta chamada “{antes['nome']}” neste nível.")
        _registrar(con, "pasta", id_, "arquivada" if arquivada else "restaurada", antes)
        con.execute("UPDATE pastas SET arquivada=?, atualizado_em=? WHERE id=?",
                    (1 if arquivada else 0, _agora(), id_))
    _salvar_backup()


def listar_pastas(incluir_arquivadas: bool = False) -> list[dict]:
    """Em ordem natural: 1ª, 2ª ... 10ª semana; I, II, III ... X."""
    sql = "SELECT * FROM pastas" + ("" if incluir_arquivadas else " WHERE arquivada = 0") + " ORDER BY id"
    with _conexao() as con:
        pastas = [dict(r) for r in con.execute(sql)]
    return sorted(pastas, key=lambda p: (chave_ordem_natural(p["nome"]), p["id"]))


def pastas_das_celebracoes() -> dict[int, Optional[int]]:
    """{celebracao_id: pasta_id}. Celebrações que nunca foram colocadas numa pasta não aparecem aqui."""
    with _conexao() as con:
        return {r["celebracao_id"]: r["pasta_id"] for r in con.execute("SELECT celebracao_id, pasta_id FROM celebracao_pasta")}


def mover_celebracoes(ids: list[int], pasta_id: Optional[int]) -> int:
    """
    Coloca as celebrações na pasta (None = "sem pasta"). Atômico: se algo falhar, nada muda.
    Devolve quantas realmente mudaram de lugar.
    """
    movidas = 0
    with _conexao() as con:
        _pai_valido(con, pasta_id)
        pastas = _pastas_por_id(con)
        destino = caminho_pasta(pastas, pasta_id)
        for cid in ids:
            cel = _linha(con, "celebracoes", cid)
            if not cel:
                raise ValueError(f"Celebração {cid} não existe.")
            atual = con.execute("SELECT pasta_id FROM celebracao_pasta WHERE celebracao_id=?", (cid,)).fetchone()
            anterior = atual["pasta_id"] if atual else None
            if anterior == pasta_id:
                continue
            _registrar(con, "celebracao", cid, "movida de pasta", {
                "nome": cel["nome"], "de": caminho_pasta(pastas, anterior), "para": destino,
            })
            con.execute(
                """INSERT INTO celebracao_pasta (celebracao_id, pasta_id) VALUES (?, ?)
                   ON CONFLICT(celebracao_id) DO UPDATE SET pasta_id = excluded.pasta_id""",
                (cid, pasta_id),
            )
            movidas += 1
    if movidas:
        _salvar_backup()
    return movidas


# ------------------------------------------------------------
# Histórico, versão e backup
# ------------------------------------------------------------
def historico(entidade: Optional[str] = None, entidade_id: Optional[int] = None, limite: int = 200) -> list[dict]:
    where, params = [], []
    if entidade:
        where.append("entidade = ?"); params.append(entidade)
    if entidade_id is not None:
        where.append("entidade_id = ?"); params.append(entidade_id)
    sql = ("SELECT * FROM historico" + (" WHERE " + " AND ".join(where) if where else "")
           + " ORDER BY id DESC LIMIT ?")
    with _conexao() as con:
        linhas = [dict(r) for r in con.execute(sql, params + [limite])]
    for l in linhas:
        l["snapshot"] = json.loads(l["snapshot"])
    return linhas


def versao() -> int:
    """Muda a cada gravação (serve de chave de cache para quem monta o índice de marcações)."""
    with _conexao() as con:
        return con.execute("SELECT COALESCE(MAX(id), 0) FROM historico").fetchone()[0]


def exportar_json() -> dict:
    with _conexao() as con:
        return {
            "formato": "biblia-marcacoes/1",
            "exportado_em": _agora(),
            "celebracoes": [dict(r) for r in con.execute("SELECT * FROM celebracoes ORDER BY id")],
            "leituras": [dict(r) for r in con.execute("SELECT * FROM leituras ORDER BY id")],
            "pastas": [dict(r) for r in con.execute("SELECT * FROM pastas ORDER BY id")],
            "celebracao_pasta": [dict(r) for r in con.execute("SELECT * FROM celebracao_pasta ORDER BY celebracao_id")],
            "historico": [
                {**dict(r), "snapshot": json.loads(r["snapshot"])}
                for r in con.execute("SELECT * FROM historico ORDER BY id")
            ],
        }


def _salvar_backup() -> None:
    """Escreve o backup JSON de forma atômica (arquivo temporário + rename)."""
    destino = caminho_backup()
    destino.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=destino.parent, suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(exportar_json(), f, ensure_ascii=False, indent=1)
        os.replace(tmp, destino)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def restaurar_de_json(backup: dict) -> tuple[int, int]:
    """
    Restaura um backup JSON. Só funciona num banco VAZIO (nunca sobrescreve dados existentes).
    Devolve (nº de celebrações, nº de leituras).
    """
    if backup.get("formato") != "biblia-marcacoes/1":
        raise ValueError("Arquivo de backup desconhecido.")
    with _conexao() as con:
        if con.execute("SELECT COUNT(*) FROM celebracoes").fetchone()[0]:
            raise ValueError("O banco já tem dados; a restauração só é permitida num banco vazio.")
        for c in backup["celebracoes"]:
            con.execute(
                """INSERT INTO celebracoes (id,nome,cor,tempo,semana,dia_semana,grau,preceito,observacao,arquivada,criado_em,atualizado_em)
                   VALUES (:id,:nome,:cor,:tempo,:semana,:dia_semana,:grau,:preceito,:observacao,:arquivada,:criado_em,:atualizado_em)""", c)
        for l in backup["leituras"]:
            con.execute(
                """INSERT INTO leituras (id,celebracao_id,tipo,tipo_outro,ciclo,referencia,observacao,arquivada,criado_em,atualizado_em)
                   VALUES (:id,:celebracao_id,:tipo,:tipo_outro,:ciclo,:referencia,:observacao,:arquivada,:criado_em,:atualizado_em)""", l)
        # Pastas: backups antigos não têm; os pais precisam ser inseridos antes dos filhos.
        pendentes, inseridas = list(backup.get("pastas", [])), set()
        while pendentes:
            prontas = [p for p in pendentes if p["pai_id"] is None or p["pai_id"] in inseridas]
            if not prontas:
                raise ValueError("Backup com pastas inconsistentes.")
            for p in prontas:
                con.execute(
                    """INSERT INTO pastas (id,nome,pai_id,cor,arquivada,criado_em,atualizado_em)
                       VALUES (:id,:nome,:pai_id,:cor,:arquivada,:criado_em,:atualizado_em)""", {**p, "cor": p.get("cor")})
                inseridas.add(p["id"])
            pendentes = [p for p in pendentes if p["id"] not in inseridas]
        for v in backup.get("celebracao_pasta", []):
            con.execute("INSERT INTO celebracao_pasta (celebracao_id, pasta_id) VALUES (:celebracao_id,:pasta_id)", v)
        for h in backup.get("historico", []):
            con.execute(
                "INSERT INTO historico (id,entidade,entidade_id,acao,snapshot,registrado_em) VALUES (?,?,?,?,?,?)",
                (h["id"], h["entidade"], h["entidade_id"], h["acao"], json.dumps(h["snapshot"], ensure_ascii=False), h["registrado_em"]))
    _salvar_backup()
    return len(backup["celebracoes"]), len(backup["leituras"])