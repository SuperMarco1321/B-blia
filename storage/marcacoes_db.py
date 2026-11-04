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

from core.marcacoes_modelo import normalizar_celebracao, normalizar_leitura

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

CREATE TRIGGER IF NOT EXISTS proibe_delete_celebracoes BEFORE DELETE ON celebracoes
BEGIN SELECT RAISE(ABORT, 'Marcações são permanentes: arquive em vez de apagar.'); END;
CREATE TRIGGER IF NOT EXISTS proibe_delete_leituras BEFORE DELETE ON leituras
BEGIN SELECT RAISE(ABORT, 'Marcações são permanentes: arquive em vez de apagar.'); END;
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
        for h in backup.get("historico", []):
            con.execute(
                "INSERT INTO historico (id,entidade,entidade_id,acao,snapshot,registrado_em) VALUES (?,?,?,?,?,?)",
                (h["id"], h["entidade"], h["entidade_id"], h["acao"], json.dumps(h["snapshot"], ensure_ascii=False), h["registrado_em"]))
    _salvar_backup()
    return len(backup["celebracoes"]), len(backup["leituras"])
