# utils/divisao_versiculo.py
# Divide o texto de um versículo em partes (a, b, c...) usando pontos finais.
# Objetivo: aproximar a notação litúrgica (10b, 13ab, etc.)

import re
from typing import Dict, List


def dividir_por_pontos(texto: str) -> Dict[str, str]:
    """
    Recebe o texto completo de um versículo e devolve um dicionário
    com as partes separadas por ponto final, indexadas por letra.

    Exemplo:
        Entrada: "Hoje foi o fim. Amém. Maria Santíssima seja Louvada."
        Saída: {
            "a": "Hoje foi o fim.",
            "b": "Amém.",
            "c": "Maria Santíssima seja Louvada."
        }
    """
    if not texto or not texto.strip():
        return {}

    # Normaliza espaços
    texto = re.sub(r"\s+", " ", texto.strip())

    # Divide por ponto final seguido de espaço ou fim de string
    # Mantém o ponto junto com a sentença
    partes_brutas = re.split(r"(?<=\.)\s+", texto)

    # Remove partes vazias
    partes = [p.strip() for p in partes_brutas if p.strip()]

    resultado = {}
    letras = "abcdefghijklmnopqrstuvwxyz"

    for i, parte in enumerate(partes):
        if i >= len(letras):
            # Caso extremo: mais de 26 sentenças
            chave = f"extra{i - 25}"
        else:
            chave = letras[i]

        # Garante que a parte termine com ponto (se não terminar)
        if not parte.endswith((".", "!", "?", "…")):
            parte = parte + "."

        resultado[chave] = parte

    return resultado


def obter_partes(texto: str, letras_desejadas: str) -> str:
    """
    Recebe o texto do versículo e uma string de letras (ex: "b", "ab", "cd")
    e devolve apenas as partes correspondentes, juntadas.

    Exemplos:
        obter_partes(texto, "b")     → só a parte b
        obter_partes(texto, "ab")    → partes a + b
        obter_partes(texto, "cd")    → partes c + d
    """
    if not letras_desejadas:
        return texto  # sem letra = versículo inteiro

    partes = dividir_por_pontos(texto)
    if not partes:
        return texto

    letras_desejadas = letras_desejadas.lower()
    selecionadas = []

    for letra in letras_desejadas:
        if letra in partes:
            selecionadas.append(partes[letra])

    if not selecionadas:
        # Se a letra pedida não existe, devolve o versículo inteiro
        # (melhor do que devolver vazio)
        return texto

    return " ".join(selecionadas)


def extrair_letra_da_referencia(parte_versiculo: str) -> tuple[int | None, str | None]:
    """
    Recebe algo como "10b", "13ab", "16", "3bc"
    e devolve (número_do_versiculo, letras)

    Exemplos:
        "10b"   → (10, "b")
        "13ab"  → (13, "ab")
        "16"    → (16, None)
        "3bc"   → (3, "bc")
    """
    if not parte_versiculo:
        return None, None

    match = re.match(r"(\d+)([a-z]*)", parte_versiculo.strip().lower())
    if not match:
        return None, None

    numero = int(match.group(1))
    letras = match.group(2) if match.group(2) else None

    return numero, letras


# ============================================================
# Teste rápido
# ============================================================
if __name__ == "__main__":
    exemplos = [
        "Hoje foi o fim. Amém. Maria Santíssima seja Louvada.",
        "No princípio, Deus criou o céu e a terra. A terra estava sem forma e vazia.",
        "Felizes os pobres em espírito, porque deles é o Reino dos Céus.",
        "Disse Deus: Faça-se a luz! E a luz foi feita.",
    ]

    for texto in exemplos:
        print("=" * 60)
        print("Texto original:")
        print(f"  {texto}")
        print("\nDivisão:")
        partes = dividir_por_pontos(texto)
        for letra, parte in partes.items():
            print(f"  {letra} = {parte}")

        print("\nTeste obter_partes('b'):")
        print(f"  → {obter_partes(texto, 'b')}")
        print()
