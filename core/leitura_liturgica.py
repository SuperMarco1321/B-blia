# core/leitura_liturgica.py
# Ferramenta de leitura litúrgica:
# recebe uma referência na notação CNBB (ex: "Sl 144(145),8-9.10-11.12-13ab.13cd-14 (R. 17a)")
# e devolve o TEXTO correspondente, já montado, com avisos quando algo é aproximado.
#
# Uso rápido:
#   PYTHONPATH=. python core/leitura_liturgica.py "Jo 1,1-5.9-12b"

import re
from collections import defaultdict
from typing import Optional

from core.biblia import obter_texto_versiculo
from core.parser_referencia import parse_referencia
from utils.divisao_versiculo import dividir_por_pontos, extrair_letra_da_referencia

# Títulos de salmo que o Ave Maria inclui dentro do v. 1, mas que o lecionário não lê.
_TITULO_SALMO = re.compile(r"^(Salmo|Cântico|Hino|Oração|Louvor)\b", re.IGNORECASE)


def _limpar(texto: str, livro: str) -> str:
    """
    Limpeza do texto-fonte:
    - remove hífens suaves invisíveis (U+00AD) que quebram palavras ('co­nhecesse');
    - remove o '*' (marca de pausa de salmo) fora dos Salmos, onde ele só atrapalha a leitura;
    - normaliza espaços.
    """
    texto = texto.replace("\u00ad", "")
    if livro != "Salmos":
        texto = texto.replace("*", "")
    return re.sub(r"\s+", " ", texto).strip()


# ------------------------------------------------------------
# Texto de um versículo (com letras)
# ------------------------------------------------------------
def _partes_do_versiculo(livro: str, capitulo: int, versiculo: int, texto: str, avisos: list) -> list[str]:
    """Divide o versículo em frases, removendo o título do salmo (se houver)."""
    partes = list(dividir_por_pontos(texto).values())

    if livro == "Salmos" and versiculo == 1 and len(partes) > 1:
        primeira = partes[0]
        if _TITULO_SALMO.match(primeira) and len(primeira.split()) <= 10:
            partes = partes[1:]
            aviso = f"Salmos {capitulo},1: título do salmo omitido ('{primeira.rstrip('.')}')."
            if aviso not in avisos:
                avisos.append(aviso)
    return partes


def _mapear_letras(letras: str, max_letra: int, n_partes: int) -> tuple[list[int], bool]:
    """
    Converte letras (ex: "ab", "cd") em índices de frases.

    - Se a referência usa letras até 'max_letra' e o texto tem pelo menos essa
      quantidade de frases → mapeamento direto (a=1ª frase, b=2ª ...).
    - Se o texto tem MENOS frases que letras (ex.: Sl 144,13 com 13ab + 13cd, mas
      só 2 frases no JSON) → as letras são distribuídas igualmente entre as frases
      (a,b → 1ª frase; c,d → 2ª). Nesse caso devolve aproximado=True.
    """
    indices_letra = sorted({ord(l) - 97 for l in letras.lower() if "a" <= l <= "z"})
    if not indices_letra or n_partes == 0:
        return [], False

    if max_letra <= n_partes:
        return sorted({i for i in indices_letra if i < n_partes}), False

    # Distribui 'max_letra' letras entre 'n_partes' frases (as primeiras ficam com o resto)
    base, resto = divmod(max_letra, n_partes)
    letra_para_parte = []
    for parte in range(n_partes):
        letra_para_parte += [parte] * (base + (1 if parte < resto else 0))
    return sorted({letra_para_parte[i] for i in indices_letra if i < len(letra_para_parte)}), True


def _texto_versiculo(
    livro: str, capitulo: int, versiculo: int, letras: Optional[str],
    max_letra: int, avisos: list,
) -> tuple[Optional[str], bool]:
    """Devolve (texto, aproximado). texto=None se o versículo não existe."""
    texto = obter_texto_versiculo(livro, capitulo, versiculo)
    if texto is None:
        avisos.append(f"{livro} {capitulo},{versiculo}: versículo não encontrado no JSON.")
        return None, False

    texto = _limpar(texto, livro)
    partes = _partes_do_versiculo(livro, capitulo, versiculo, texto, avisos)

    if not letras:
        # Versículo inteiro (apenas sem o título do salmo, se for o caso)
        return (" ".join(partes) if partes else texto), False

    indices, aproximado = _mapear_letras(letras, max_letra, len(partes))
    if not indices:
        avisos.append(
            f"{livro} {capitulo},{versiculo}{letras}: letra fora do texto; versículo inteiro usado."
        )
        return " ".join(partes), False

    if aproximado:
        aviso = (
            f"{livro} {capitulo},{versiculo}: o texto tem {len(partes)} frase(s), mas a referência "
            f"usa letras até '{chr(96 + max_letra)}'; divisão aproximada (letras distribuídas entre as frases)."
        )
        if aviso not in avisos:
            avisos.append(aviso)

    return " ".join(partes[i] for i in indices), aproximado


# ------------------------------------------------------------
# Rótulos legíveis (ex: "8-9", "13ab", "12,31–13,13")
# ------------------------------------------------------------
def _fmt(versiculo: int, letras: Optional[str]) -> str:
    return f"{versiculo}{letras or ''}"


def _rotulo_segmento(itens: list[dict]) -> str:
    primeiro, ultimo = itens[0], itens[-1]
    if primeiro["capitulo"] != ultimo["capitulo"]:
        return (
            f"{primeiro['capitulo']},{_fmt(primeiro['versiculo'], primeiro['letras'])}–"
            f"{ultimo['capitulo']},{_fmt(ultimo['versiculo'], ultimo['letras'])}"
        )
    if primeiro["versiculo"] == ultimo["versiculo"]:
        letras = primeiro.get("letras") or ultimo.get("letras")
        return _fmt(primeiro["versiculo"], letras)
    return f"{_fmt(primeiro['versiculo'], primeiro['letras'])}–{_fmt(ultimo['versiculo'], ultimo['letras'])}"


# ------------------------------------------------------------
# Refrão
# ------------------------------------------------------------
def _resolver_refrao(refrao: Optional[str], livro: str, capitulo: int, max_letras: dict, avisos: list) -> Optional[dict]:
    """
    Refrão pode vir como '17a' (mesmo salmo) ou como referência completa ('Sl 22,1').
    Devolve {"referencia": "...", "texto": "..." | None}.
    """
    if not refrao:
        return None

    m = re.fullmatch(r"(\d+)([a-z]*)", refrao.replace(" ", "").lower())
    if m:
        v = int(m.group(1))
        letras = m.group(2) or None
        chave = (livro, capitulo, v)
        max_l = max(max_letras.get(chave, 0), max((ord(c) - 96 for c in (letras or "")), default=0))
        texto, _ = _texto_versiculo(livro, capitulo, v, letras, max_l, avisos)
        return {"referencia": refrao, "texto": texto}

    # Referência completa
    parsed = parse_referencia(refrao)
    if parsed["versiculos"]:
        textos = []
        for item in parsed["versiculos"]:
            max_l = max((ord(c) - 96 for c in (item["letras"] or "")), default=0)
            t, _ = _texto_versiculo(item["livro"], item["capitulo"], item["versiculo"], item["letras"], max_l, avisos)
            if t:
                textos.append(t)
        if textos:
            return {"referencia": refrao, "texto": " ".join(textos)}

    avisos.append(f"Refrão '{refrao}' não pôde ser resolvido; mantido como indicado.")
    return {"referencia": refrao, "texto": None}


# ------------------------------------------------------------
# API principal
# ------------------------------------------------------------
def ler_referencia(referencia: str) -> dict:
    """
    Recebe uma referência CNBB e devolve:
    {
      "referencia_original": str,
      "livro": str | None,
      "refrao": {"referencia": "17a", "texto": "..."} | None,
      "trechos": [                      # um por bloco separado por ';'
        {
          "livro": "Habacuc",
          "referencia": "1,2–3",
          "segmentos": [                # um por parte separada por '.'
            {"rotulo": "8–9",
             "versiculos": [{"capitulo", "versiculo", "letras", "texto", "aproximado"}],
             "texto": "..."}
          ],
          "texto": "..."
        }
      ],
      "texto": str,                     # leitura completa (trechos separados por linha em branco)
      "avisos": [str]
    }
    """
    avisos: list[str] = []
    parsed = parse_referencia(referencia)

    resultado = {
        "referencia_original": parsed["referencia_original"],
        "livro": parsed["livro"],
        "refrao": None,
        "trechos": [],
        "texto": "",
        "avisos": avisos,
    }

    itens = parsed["versiculos"]
    if not itens:
        avisos.append("Não foi possível interpretar a referência (livro não reconhecido ou formato inválido).")
        return resultado

    # Maior letra usada em cada versículo na referência inteira (para o mapeamento de letras)
    max_letras: dict[tuple, int] = defaultdict(int)
    for it in itens:
        if it.get("letras") and it.get("versiculo") is not None:
            chave = (it["livro"], it["capitulo"], it["versiculo"])
            max_letras[chave] = max(max_letras[chave], max(ord(c) - 96 for c in it["letras"]))

    # Agrupa: bloco (;) → segmento (.)
    estrutura: dict[int, dict[int, list[dict]]] = defaultdict(lambda: defaultdict(list))
    for it in itens:
        estrutura[it.get("bloco", 0)][it.get("segmento", 0)].append(it)

    for idx_bloco in sorted(estrutura):
        segmentos_out = []
        livro_bloco = None
        todos_bloco = []

        for idx_seg in sorted(estrutura[idx_bloco]):
            lista = estrutura[idx_bloco][idx_seg]
            livro_bloco = livro_bloco or lista[0]["livro"]
            versiculos_out = []

            for it in lista:
                if it.get("versiculo") is None:
                    avisos.append(f"{it['livro']} {it['capitulo']}: referência sem versículo (capítulo inteiro não expandido).")
                    continue
                if it.get("nota"):
                    avisos.append(f"{it['livro']} {it['capitulo']},{it['versiculo']}: {it['nota']}.")
                chave = (it["livro"], it["capitulo"], it["versiculo"])
                texto, aprox = _texto_versiculo(
                    it["livro"], it["capitulo"], it["versiculo"], it.get("letras"),
                    max_letras.get(chave, 0), avisos,
                )
                if texto:
                    versiculos_out.append({
                        "capitulo": it["capitulo"],
                        "versiculo": it["versiculo"],
                        "letras": it.get("letras"),
                        "texto": texto,
                        "aproximado": aprox,
                    })

            if versiculos_out:
                segmentos_out.append({
                    "rotulo": _rotulo_segmento(lista),
                    "versiculos": versiculos_out,
                    "texto": " ".join(v["texto"] for v in versiculos_out),
                })
                todos_bloco.extend(lista)

        if segmentos_out:
            resultado["trechos"].append({
                "livro": livro_bloco,
                "referencia": _rotulo_trecho(todos_bloco, [sg["rotulo"] for sg in segmentos_out]),
                "segmentos": segmentos_out,
                "texto": " ".join(s["texto"] for s in segmentos_out),
            })

    # Refrão (usa o capítulo do primeiro versículo)
    if parsed["refrão"]:
        primeiro = itens[0]
        resultado["refrao"] = _resolver_refrao(
            parsed["refrão"], primeiro["livro"], primeiro["capitulo"], max_letras, avisos
        )

    resultado["texto"] = "\n\n".join(t["texto"] for t in resultado["trechos"])
    return resultado


def _rotulo_trecho(itens: list[dict], rotulos_segmentos: list[str]) -> str:
    """Rótulo do trecho na notação original: 'cap,seg1.seg2.seg3' (ou 'cap,v–cap,v' se atravessa capítulos)."""
    p, u = itens[0], itens[-1]
    if p["capitulo"] != u["capitulo"]:
        return (f"{p['capitulo']},{_fmt(p['versiculo'], p['letras'])}–"
                f"{u['capitulo']},{_fmt(u['versiculo'], u['letras'])}")
    return f"{p['capitulo']},{'.'.join(rotulos_segmentos)}"


def formatar_texto_puro(res: dict) -> str:
    """Versão em texto simples (para terminal / testes)."""
    linhas = [f"=== {res['referencia_original']} ==="]
    if res["refrao"]:
        txt = res["refrao"]["texto"] or "(texto não encontrado)"
        linhas.append(f"R. ({res['refrao']['referencia']}) {txt}")
    for t in res["trechos"]:
        linhas.append(f"\n[{t['livro']} {t['referencia']}]")
        for s in t["segmentos"]:
            linhas.append(f"  ({s['rotulo']}) {s['texto']}")
    if res["avisos"]:
        linhas.append("\nAvisos:")
        linhas += [f"  - {a}" for a in res["avisos"]]
    return "\n".join(linhas)


# ------------------------------------------------------------
# Teste rápido
# ------------------------------------------------------------
if __name__ == "__main__":
    import sys

    exemplos = sys.argv[1:] or [
        "Sl 22(23),1-3a.3b-4.5.6 (R. 1)",
        "Sl 144(145),8-9.10-11.12-13ab.13cd-14 (R. 17a)",
        "1Cor 12,31–13,13",
        "Hab 1,2-3; 2,2-4",
        "Jo 1,1-5.9-12b",
    ]
    for ex in exemplos:
        print(formatar_texto_puro(ler_referencia(ex)))
        print()
