# core/marcacoes_modelo.py
# Vocabulário e validação das marcações litúrgicas (sem dependências de banco ou de interface).

from __future__ import annotations

from typing import Optional

# Cores litúrgicas para fundo escuro azul-marinho.
#  fill  = cor do marca-texto (aplicada com transparência 'alpha' sobre o fundo)
#  borda = sublinhado da frase marcada
# O branco vira um cinza-claro translúcido (branco puro ofuscaria o texto); o preto vira uma faixa
# escura com sublinhado claro, para continuar visível no fundo escuro.
CORES = {
    "Branco":   {"fill": "#f4f1e6", "borda": "#ffffff", "alpha": 0.30},
    "Vermelho": {"fill": "#ef5350", "borda": "#ff8a80", "alpha": 0.45},
    "Verde":    {"fill": "#4caf50", "borda": "#81c784", "alpha": 0.45},
    "Roxo":     {"fill": "#9575cd", "borda": "#b39ddb", "alpha": 0.50},
    "Rosa":     {"fill": "#f06292", "borda": "#f8bbd0", "alpha": 0.45},
    "Dourado":  {"fill": "#e0b030", "borda": "#ffd54f", "alpha": 0.40},
    "Preto":    {"fill": "#000000", "borda": "#9aa5b8", "alpha": 0.60},
}

TEMPOS = ["Advento", "Natal", "Quaresma", "Tríduo Pascal", "Páscoa", "Tempo Comum"]

DIAS_SEMANA = ["Domingo", "Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado"]

# 'memória' e 'memória obrigatória' são a mesma categoria no calendário romano.
GRAUS = ["Solenidade", "Festa", "Domingo", "Memória obrigatória", "Memória facultativa", "Féria"]

# Tipo da leitura (OPCIONAL). 'Outro' aceita um texto livre.
TIPOS_LEITURA = {
    "primeira":  "Primeira leitura",
    "salmo":     "Salmo",
    "segunda":   "Segunda leitura",
    "aclamacao": "Aclamação ao Evangelho",
    "evangelho": "Evangelho",
    "outro":     "Outro",
}

# Ciclo da leitura: A/B/C (domingos e solenidades) ou I/II (férias do Tempo Comum: ano ímpar/par).
CICLOS = {
    "TODOS": "Todos os anos",
    "A": "Ano A",
    "B": "Ano B",
    "C": "Ano C",
    "I": "Ano ímpar (I)",
    "II": "Ano par (II)",
}


def rotulo_tipo(tipo: Optional[str], tipo_outro: Optional[str] = None) -> str:
    if not tipo:
        return ""
    if tipo == "outro" and tipo_outro:
        return tipo_outro
    return TIPOS_LEITURA.get(tipo, tipo)


def rotulo_ciclo(ciclo: Optional[str]) -> str:
    return CICLOS.get(ciclo or "TODOS", ciclo or "")


def _vazio(valor) -> bool:
    return valor is None or (isinstance(valor, str) and not valor.strip())


def normalizar_celebracao(dados: dict) -> dict:
    """Valida e normaliza os dados de uma celebração. Levanta ValueError com todos os problemas."""
    erros = []
    nome = (dados.get("nome") or "").strip()
    if not nome:
        erros.append("O nome é obrigatório.")

    cor = dados.get("cor")
    if cor not in CORES:
        erros.append(f"Cor litúrgica inválida: {cor!r}.")

    tempo = dados.get("tempo") or None
    if tempo is not None and tempo not in TEMPOS:
        erros.append(f"Tempo litúrgico inválido: {tempo!r}.")

    dia = dados.get("dia_semana") or None
    if dia is not None and dia not in DIAS_SEMANA:
        erros.append(f"Dia da semana inválido: {dia!r}.")

    grau = dados.get("grau") or None
    if grau is not None and grau not in GRAUS:
        erros.append(f"Grau inválido: {grau!r}.")

    semana = dados.get("semana")
    if _vazio(semana) or semana == 0:
        semana = None
    else:
        try:
            semana = int(semana)
            if not 1 <= semana <= 34:
                erros.append("A semana deve estar entre 1 e 34.")
        except (TypeError, ValueError):
            erros.append("Semana inválida.")

    if erros:
        raise ValueError(" ".join(erros))

    return {
        "nome": nome,
        "cor": cor,
        "tempo": tempo,
        "semana": semana,
        "dia_semana": dia,
        "grau": grau,
        "preceito": 1 if dados.get("preceito") else 0,
        "observacao": (dados.get("observacao") or "").strip() or None,
    }


def normalizar_leitura(dados: dict) -> dict:
    """Valida e normaliza os dados de uma leitura. O tipo é opcional; a referência é obrigatória."""
    erros = []
    referencia = (dados.get("referencia") or "").strip()
    if not referencia:
        erros.append("A referência é obrigatória.")

    tipo = dados.get("tipo") or None
    if tipo is not None and tipo not in TIPOS_LEITURA:
        erros.append(f"Tipo de leitura inválido: {tipo!r}.")

    tipo_outro = (dados.get("tipo_outro") or "").strip() or None
    if tipo != "outro":
        tipo_outro = None

    ciclo = dados.get("ciclo") or "TODOS"
    if ciclo not in CICLOS:
        erros.append(f"Ciclo inválido: {ciclo!r}.")

    if erros:
        raise ValueError(" ".join(erros))

    return {
        "tipo": tipo,
        "tipo_outro": tipo_outro,
        "ciclo": ciclo,
        "referencia": referencia,
        "observacao": (dados.get("observacao") or "").strip() or None,
    }