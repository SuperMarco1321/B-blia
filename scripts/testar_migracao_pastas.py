# scripts/testar_migracao_pastas.py
# Prova que a funcionalidade de pastas não perde nada do banco atual.
#
# As pastas criadas aqui levam o prefixo “[teste]” e só existem na cópia temporária.
# Trabalha SEMPRE numa CÓPIA temporária: o banco original só é lido (e o script confere, no fim,
# que o arquivo original continua byte a byte igual).
#
# Uso (na raiz do projeto):
#   python scripts/testar_migracao_pastas.py                 # usa dados/marcacoes.db
#   python scripts/testar_migracao_pastas.py caminho/outro.db

from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

TABELAS_ANTIGAS = ("celebracoes", "leituras", "historico")


def sha(caminho: Path) -> str:
    return hashlib.sha256(caminho.read_bytes()).hexdigest()


def despejar(caminho: Path) -> dict:
    """Todas as linhas das tabelas já existentes, lidas direto do arquivo (somente leitura).
    Se o banco já tiver pastas (versão anterior), elas também entram (sem a coluna 'cor', que é nova)."""
    con = sqlite3.connect(f"file:{caminho}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    try:
        saida = {t: [tuple(r) for r in con.execute(f"SELECT * FROM {t} ORDER BY id")] for t in TABELAS_ANTIGAS}
        existentes = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        if "pastas" in existentes:
            saida["pastas"] = [tuple(r) for r in con.execute(
                "SELECT id, nome, pai_id, arquivada, criado_em, atualizado_em FROM pastas ORDER BY id")]
        if "celebracao_pasta" in existentes:
            saida["celebracao_pasta"] = [tuple(r) for r in con.execute(
                "SELECT celebracao_id, pasta_id FROM celebracao_pasta ORDER BY celebracao_id")]
        return saida
    finally:
        con.close()


def main() -> int:
    original = Path(sys.argv[1]) if len(sys.argv) > 1 else RAIZ / "dados" / "marcacoes.db"
    if not original.exists():
        print(f"Banco não encontrado: {original}")
        return 2

    falhas: list[str] = []

    def confere(ok: bool, texto: str):
        print(("  ✅ " if ok else "  ❌ ") + texto)
        if not ok:
            falhas.append(texto)

    hash_antes = sha(original)
    antes = despejar(original)
    print(f"Banco original: {original}")
    print(f"  {len(antes['celebracoes'])} celebrações, {len(antes['leituras'])} leituras, "
          f"{len(antes['historico'])} registros de histórico")

    with tempfile.TemporaryDirectory() as tmp:
        copia = Path(tmp) / "marcacoes.db"
        shutil.copy2(original, copia)
        os.environ["BIBLIA_DB"] = str(copia)          # o app passa a usar a CÓPIA
        from storage import marcacoes_db as db        # importado só depois de apontar para a cópia

        print("\n1) Migração (abrir a cópia com o código novo)")
        db.listar_celebracoes(incluir_arquivadas=True)
        depois = despejar(copia)
        for t in antes:
            confere(depois.get(t) == antes[t], f"tabela '{t}' idêntica após a migração ({len(antes[t])} linhas)")

        print("\n2) Uso das pastas na cópia")
        cels = db.listar_celebracoes(incluir_arquivadas=True)
        n_cels, n_leit = len(cels), len(db.listar_leituras(incluir_arquivadas=True))
        try:
            tc = db.criar_pasta("[teste] Tempo Comum")
            s5 = db.criar_pasta("[teste] 5ª semana", tc)
            sol = db.criar_pasta("[teste] Solenidades")
            confere(True, "criou pastas e subpasta")
            for args, msg in (
                (("[TESTE] tempo comum", None), "recusa nome repetido no mesmo nível (sem diferenciar maiúsculas)"),
                (("", None), "recusa nome vazio"),
            ):
                try:
                    db.criar_pasta(*args)
                    confere(False, msg)
                except ValueError:
                    confere(True, msg)
            try:
                db.mover_pasta(tc, s5)
                confere(False, "impede mover a pasta para dentro de uma subpasta dela")
            except ValueError:
                confere(True, "impede mover a pasta para dentro de uma subpasta dela")

            if cels:
                ids = [c["id"] for c in cels[:3]]
                confere(db.mover_celebracoes(ids, s5) == len(ids), f"moveu {len(ids)} celebração(ões) para a subpasta")
                confere(all(db.pastas_das_celebracoes().get(i) == s5 for i in ids), "celebrações aparecem na subpasta")
                try:
                    db.arquivar_pasta(s5)
                    confere(False, "recusa arquivar pasta que ainda tem celebrações")
                except ValueError:
                    confere(True, "recusa arquivar pasta que ainda tem celebrações")
                db.mover_celebracoes(ids, None)
                confere(all(db.pastas_das_celebracoes().get(i) is None for i in ids), "voltaram para 'sem pasta'")
            db.mover_pasta(s5, sol)
            db.renomear_pasta(sol, "[teste] Solenidades móveis")
            db.arquivar_pasta(s5)
            db.arquivar_pasta(s5, False)
            confere(True, "moveu, renomeou, arquivou e restaurou pastas")

            db.definir_cor_pasta(s5, "Verde")
            db.definir_cor_pasta(sol, "Preto")
            cores = {p["id"]: p["cor"] for p in db.listar_pastas()}
            confere(cores[s5] == "Verde" and cores[sol] == "Preto", "define a cor de destaque da pasta")
            db.definir_cor_pasta(s5, None)
            confere({p["id"]: p["cor"] for p in db.listar_pastas()}[s5] is None, "remove a cor da pasta")
            try:
                db.definir_cor_pasta(s5, "Azul")
                confere(False, "recusa cor que não é litúrgica")
            except ValueError:
                confere(True, "recusa cor que não é litúrgica")
            db.definir_cor_pasta(s5, "Verde")

            raiz = db.criar_pasta("[teste] Semanas")
            for n in ("10ª semana", "2ª semana", "1ª semana", "11ª semana"):
                db.criar_pasta(n, raiz)
            nomes = [p["nome"] for p in db.listar_pastas() if p["pai_id"] == raiz]
            confere(nomes == ["1ª semana", "2ª semana", "10ª semana", "11ª semana"], f"ordem numérica das pastas: {nomes}")
            raiz2 = db.criar_pasta("[teste] Domingos")
            for n in ("Domingo X", "Domingo II", "Domingo IV", "Domingo I"):
                db.criar_pasta(n, raiz2)
            nomes = [p["nome"] for p in db.listar_pastas() if p["pai_id"] == raiz2]
            confere(nomes == ["Domingo I", "Domingo II", "Domingo IV", "Domingo X"], f"ordem romana das pastas: {nomes}")

            # backup → restauração num banco vazio
            backup = db.exportar_json()
            n_pastas = len(db.listar_pastas(True))
            cores_antes = {p["id"]: p["cor"] for p in db.listar_pastas(True)}
            vazio = Path(tmp) / "vazio.db"
            os.environ["BIBLIA_DB"] = str(vazio)
            n_c, n_l = db.restaurar_de_json(backup)
            confere((n_c, n_l) == (n_cels, n_leit) and len(db.listar_pastas(True)) == n_pastas
                    and {p["id"]: p["cor"] for p in db.listar_pastas(True)} == cores_antes,
                    "backup JSON restaura celebrações, leituras, pastas e cores num banco vazio")
            os.environ["BIBLIA_DB"] = str(copia)
        except Exception as e:                       # qualquer erro inesperado conta como falha
            confere(False, f"erro inesperado: {type(e).__name__}: {e}")

        print("\n3) Nada se perdeu")
        con = sqlite3.connect(f"file:{copia}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        cel_dep = [tuple(r) for r in con.execute("SELECT * FROM celebracoes ORDER BY id")]
        leit_dep = [tuple(r) for r in con.execute("SELECT * FROM leituras ORDER BY id")]
        hist_dep = [tuple(r) for r in con.execute("SELECT * FROM historico ORDER BY id")]
        con.close()
        confere(cel_dep == antes["celebracoes"], "celebrações continuam idênticas, linha por linha")
        confere(leit_dep == antes["leituras"], "leituras continuam idênticas, linha por linha")
        confere(hist_dep[: len(antes["historico"])] == antes["historico"],
                "histórico antigo intacto (só ganhou registros novos no fim)")

    print("\n4) Banco original")
    confere(sha(original) == hash_antes, "arquivo original não foi tocado (mesmo hash de antes)")

    print("\n" + ("TUDO CERTO ✅  Pode aplicar no banco de verdade." if not falhas
                  else f"{len(falhas)} FALHA(S) ❌  NÃO aplique no banco de verdade."))
    return 0 if not falhas else 1


if __name__ == "__main__":
    sys.exit(main())
