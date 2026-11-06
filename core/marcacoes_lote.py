# core/marcacoes_lote.py
# Cadastro de leituras EM BLOCO: o usuário digita uma referência por linha, na ordem do lecionário,
# e o tipo de cada leitura é deduzido pela posição da linha.
#
#   Com 2ª leitura (domingos e solenidades): 1ª leitura / Salmo / 2ª leitura / Aclamação / Evangelho
#   Sem 2ª leitura (dias de semana, festas, memórias): 1ª leitura / Salmo / Aclamação / Evangelho
#
# Lógica pura (sem Streamlit nem banco): recebe o texto e as leituras já cadastradas.

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from core.marcacoes_modelo import TIPOS_LEITURA, rotulo_ciclo

SLOTS_COM_SEGUNDA = ["primeira", "salmo", "segunda", "aclamacao", "evangelho"]
SLOTS_SEM_SEGUNDA = ["primeira", "salmo", "aclamacao", "evangelho"]

# Evangelho e aclamação dos dias de semana não mudam entre ano par e ímpar.
_TIPOS_SEM_PAR_IMPAR = ("evangelho", "aclamacao")


def tem_segunda_por_padrao(celebracao: dict) -> bool:
    """Domingos e solenidades têm segunda leitura; dias de semana, festas e memórias, não."""
    return celebracao.get("dia_semana") == "Domingo" or celebracao.get("grau") in ("Domingo", "Solenidade")


def slots(com_segunda: bool) -> list[str]:
    return list(SLOTS_COM_SEGUNDA if com_segunda else SLOTS_SEM_SEGUNDA)


def ordem_legivel(com_segunda: bool) -> str:
    return " → ".join(TIPOS_LEITURA[t] for t in slots(com_segunda))


def _chave(referencia: str) -> str:
    """Normaliza a referência para detectar repetidas (ignora espaços e maiúsculas)."""
    return re.sub(r"\s+", "", referencia).lower()


@dataclass
class LinhaLote:
    posicao: int               # 1, 2, 3...
    tipo: str                  # código do tipo (primeira, salmo...)
    ciclo: str                 # código do ciclo aplicado a esta linha
    referencia: str            # '' = linha em branco (posição pulada)
    duplicada: bool = False    # já existe na celebração com o mesmo tipo e ciclo

    @property
    def pulada(self) -> bool:
        return not self.referencia

    @property
    def vai_ser_salva(self) -> bool:
        return not self.pulada and not self.duplicada


@dataclass
class ResultadoLote:
    linhas: list[LinhaLote] = field(default_factory=list)
    erros: list[str] = field(default_factory=list)
    avisos: list[str] = field(default_factory=list)

    @property
    def a_adicionar(self) -> list[LinhaLote]:
        return [] if self.erros else [l for l in self.linhas if l.vai_ser_salva]

    def para_banco(self) -> list[dict]:
        """Dados prontos para db.adicionar_leituras()."""
        return [
            {"tipo": l.tipo, "tipo_outro": None, "ciclo": l.ciclo, "referencia": l.referencia, "observacao": None}
            for l in self.a_adicionar
        ]


def interpretar_bloco(
    texto: str,
    com_segunda: bool,
    ciclo: str,
    evangelho_todos_anos: bool = False,
    existentes: Optional[list[dict]] = None,
) -> ResultadoLote:
    """
    Converte o texto (uma referência por linha) em linhas tipadas.

    - Linha em branco = pula aquela posição (ex.: celebração sem salmo).
    - Linhas a mais que as posições = erro (nada é salvo).
    - Linhas a menos = aviso (as posições finais ficam sem leitura).
    - evangelho_todos_anos: com ciclo I/II, Evangelho e aclamação entram como "Todos os anos".
    - Leituras já cadastradas (mesmo tipo, ciclo e referência) são marcadas como duplicadas.
    """
    res = ResultadoLote()
    posicoes = slots(com_segunda)

    linhas = [l.strip() for l in texto.replace("\r", "").split("\n")]
    while linhas and not linhas[-1]:        # linhas em branco no final não contam
        linhas.pop()

    if not linhas:
        return res

    if len(linhas) > len(posicoes):
        res.erros.append(
            f"Você digitou {len(linhas)} linhas, mas esta celebração espera no máximo {len(posicoes)}: "
            f"{ordem_legivel(com_segunda)}. Se houver segunda leitura, marque “Tem segunda leitura”."
        )

    vistas = {(e["tipo"], e["ciclo"], _chave(e["referencia"])) for e in (existentes or []) if not e.get("arquivada")}

    for i, referencia in enumerate(linhas[: len(posicoes)]):
        tipo = posicoes[i]
        ciclo_linha = ciclo
        if evangelho_todos_anos and ciclo in ("I", "II") and tipo in _TIPOS_SEM_PAR_IMPAR:
            ciclo_linha = "TODOS"
        linha = LinhaLote(posicao=i + 1, tipo=tipo, ciclo=ciclo_linha, referencia=referencia)
        if not linha.pulada and (tipo, ciclo_linha, _chave(referencia)) in vistas:
            linha.duplicada = True
        res.linhas.append(linha)

    if len(linhas) < len(posicoes):
        faltam = ", ".join(TIPOS_LEITURA[t] for t in posicoes[len(linhas):])
        res.avisos.append(f"Só {len(linhas)} linha(s): ficam sem leitura {faltam}.")
    pulados = [TIPOS_LEITURA[l.tipo] for l in res.linhas if l.pulada]
    if pulados:
        res.avisos.append("Linha em branco: " + ", ".join(pulados) + " será pulada.")
    return res


def descricao_ciclo(ciclo: str) -> str:
    return rotulo_ciclo(ciclo)
