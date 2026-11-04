# core/marcacoes.py
# Motor das marcações: transforma leituras cadastradas (notação CNBB) em cobertura por FRASE,
# monta o índice usado na Bíblia e calcula as interseções entre marcações.

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Iterable, Optional

from core.leitura_liturgica import ler_referencia
from core.marcacoes_modelo import rotulo_ciclo, rotulo_tipo
from storage import marcacoes_db as db


# ------------------------------------------------------------
# Cobertura de uma referência
# ------------------------------------------------------------
@lru_cache(maxsize=8192)
def cobertura(referencia: str) -> dict:
    """
    Interpreta uma referência CNBB e devolve a cobertura por frase:
    {"itens": ((livro, cap, ver, (frases...)), ...), "avisos": (...), "interpretada": bool, "aproximado": bool}
    Referências que o parser não entende voltam com interpretada=False (são salvas, mas não pintam nada).
    """
    res = ler_referencia(referencia)
    itens, aproximado = [], False
    for trecho in res["trechos"]:
        for seg in trecho["segmentos"]:
            for v in seg["versiculos"]:
                itens.append((v["livro"], v["capitulo"], v["versiculo"], tuple(v["frases"])))
                aproximado = aproximado or v["aproximado"]
    return {
        "itens": tuple(itens),
        "avisos": tuple(res["avisos"]),
        "interpretada": bool(itens),
        "aproximado": aproximado,
        "livro": res["livro"],
    }


# ------------------------------------------------------------
# Índice
# ------------------------------------------------------------
@dataclass(frozen=True)
class Marca:
    leitura_id: int
    celebracao_id: int
    celebracao: str
    cor: str
    tempo: Optional[str]
    grau: Optional[str]
    tipo: str            # rótulo legível ('' se não houver)
    tipo_codigo: str     # primeira/salmo/segunda/aclamacao/evangelho/outro ('' = sem tipo)
    ciclo: str           # código: TODOS/A/B/C/I/II
    referencia: str
    aproximado: bool = False

    @property
    def descricao(self) -> str:
        partes = [self.celebracao]
        detalhe = " · ".join(x for x in (self.tipo, None if self.ciclo == "TODOS" else rotulo_ciclo(self.ciclo)) if x)
        if detalhe:
            partes.append(detalhe)
        return f"{' — '.join(partes)} ({self.referencia})"


@dataclass
class Filtros:
    cores: Optional[set] = None
    tempos: Optional[set] = None
    ciclos: Optional[set] = None       # filtrar por 'A' inclui também as leituras de 'TODOS'
    tipos: Optional[set] = None        # códigos de tipo; '' = sem tipo


class IndiceMarcacoes:
    """Mapa (livro, cap) → verso → frase → [Marca]."""

    def __init__(self):
        self._mapa: dict = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
        self.marcas: dict[int, Marca] = {}

    def adicionar(self, marca: Marca, itens: Iterable[tuple]):
        self.marcas[marca.leitura_id] = marca
        for livro, cap, ver, frases in itens:
            for f in frases:
                lista = self._mapa[(livro, cap)][ver][f]
                if marca not in lista:
                    lista.append(marca)

    # --- consultas ---
    def marcas_da_frase(self, livro: str, cap: int, ver: int, frase: int) -> list[Marca]:
        return self._mapa.get((livro, cap), {}).get(ver, {}).get(frase, [])

    def capitulo_marcado(self, livro: str, cap: int) -> bool:
        return (livro, cap) in self._mapa

    def livros_marcados(self) -> set[str]:
        return {livro for livro, _ in self._mapa}

    def marcas_no_capitulo(self, livro: str, cap: int) -> list[Marca]:
        vistas = {}
        for ver in self._mapa.get((livro, cap), {}).values():
            for lista in ver.values():
                for m in lista:
                    vistas[m.leitura_id] = m
        return sorted(vistas.values(), key=lambda m: (m.celebracao.lower(), m.leitura_id))

    def intersecoes(self, livro: str, cap: int) -> dict[tuple[int, int], list[int]]:
        """(id_a, id_b) com id_a < id_b → versículos do capítulo em que as duas marcações se cruzam."""
        pares: dict[tuple[int, int], set] = defaultdict(set)
        for ver, frases in self._mapa.get((livro, cap), {}).items():
            for lista in frases.values():
                ids = sorted({m.leitura_id for m in lista})
                for i, a in enumerate(ids):
                    for b in ids[i + 1:]:
                        pares[(a, b)].add(ver)
        return {k: sorted(v) for k, v in pares.items()}

    def tooltip(self, livro: str, cap: int, ver: int, frase: int, _inter_cache: Optional[dict] = None) -> str:
        """Texto do balão ao passar o mouse: o que cobre a frase e onde há interseção."""
        marcas = self.marcas_da_frase(livro, cap, ver, frase)
        if not marcas:
            return ""
        linhas = [f"● {m.descricao}" for m in marcas]
        if len(marcas) > 1:
            inter = _inter_cache if _inter_cache is not None else self.intersecoes(livro, cap)
            ids = sorted(m.leitura_id for m in marcas)
            linhas.append("⚠ Interseção:")
            for i, a in enumerate(ids):
                for b in ids[i + 1:]:
                    vers = inter.get((a, b), [ver])
                    linhas.append(
                        f"  {self.marcas[a].celebracao} × {self.marcas[b].celebracao} em {formatar_versiculos(vers)}"
                    )
        return "\n".join(linhas)


def formatar_versiculos(vers: list[int]) -> str:
    """[3,4,5,8] → 'vv. 3-5, 8' ; [3] → 'v. 3'."""
    vers = sorted(set(vers))
    if len(vers) == 1:
        return f"v. {vers[0]}"
    faixas, inicio, anterior = [], vers[0], vers[0]
    for v in vers[1:]:
        if v == anterior + 1:
            anterior = v
            continue
        faixas.append((inicio, anterior)); inicio = anterior = v
    faixas.append((inicio, anterior))
    return "vv. " + ", ".join(str(a) if a == b else f"{a}-{b}" for a, b in faixas)


def _passa(marca: Marca, f: Optional[Filtros]) -> bool:
    if f is None:
        return True
    if f.cores and marca.cor not in f.cores:
        return False
    if f.tempos and (marca.tempo or "") not in f.tempos:
        return False
    if f.ciclos and marca.ciclo not in f.ciclos and marca.ciclo != "TODOS":
        return False
    if f.tipos and marca.tipo_codigo not in f.tipos:
        return False
    return True


def construir_indice(filtros: Optional[Filtros] = None) -> IndiceMarcacoes:
    """Monta o índice com todas as leituras ATIVAS (celebração e leitura não arquivadas)."""
    indice = IndiceMarcacoes()
    celebracoes = {c["id"]: c for c in db.listar_celebracoes()}
    for l in db.listar_leituras():
        c = celebracoes.get(l["celebracao_id"])
        if not c:
            continue
        cob = cobertura(l["referencia"])
        if not cob["interpretada"]:
            continue
        marca = Marca(
            leitura_id=l["id"], celebracao_id=c["id"], celebracao=c["nome"], cor=c["cor"],
            tempo=c["tempo"], grau=c["grau"], tipo=rotulo_tipo(l["tipo"], l["tipo_outro"]), tipo_codigo=l["tipo"] or "",
            ciclo=l["ciclo"], referencia=l["referencia"], aproximado=cob["aproximado"],
        )
        if _passa(marca, filtros):
            indice.adicionar(marca, cob["itens"])
    return indice
