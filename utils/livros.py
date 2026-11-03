# utils/livros.py
# Mapeamento de nomes e abreviações → nome exato no JSON da Ave Maria

# Chave = forma normalizada (minúscula, sem acento quando possível)
# Valor = nome EXATO que aparece no bibliaAveMaria.json

LIVROS = {
    # === ANTIGO TESTAMENTO ===
    # Pentateuco
    "genesis": "Gênesis",
    "gênesis": "Gênesis",
    "gn": "Gênesis",
    "gen": "Gênesis",

    "exodo": "Êxodo",
    "êxodo": "Êxodo",
    "ex": "Êxodo",
    "êx": "Êxodo",

    "levitico": "Levítico",
    "levítico": "Levítico",
    "lv": "Levítico",
    "lev": "Levítico",

    "numeros": "Números",
    "números": "Números",
    "nm": "Números",
    "num": "Números",

    "deuteronomio": "Deuteronômio",
    "deuteronômio": "Deuteronômio",
    "dt": "Deuteronômio",
    "deut": "Deuteronômio",

    # Históricos
    "josue": "Josué",
    "josué": "Josué",
    "js": "Josué",
    "jos": "Josué",

    "juizes": "Juízes",
    "juízes": "Juízes",
    "jz": "Juízes",

    "rute": "Rute",
    "rt": "Rute",
    "ru": "Rute",

    "i samuel": "I Samuel",
    "1 samuel": "I Samuel",
    "1samuel": "I Samuel",
    "1sm": "I Samuel",
    "1 sm": "I Samuel",
    "ism": "I Samuel",
    "i sm": "I Samuel",

    "ii samuel": "II Samuel",
    "2 samuel": "II Samuel",
    "2samuel": "II Samuel",
    "2sm": "II Samuel",
    "2 sm": "II Samuel",
    "iism": "II Samuel",
    "ii sm": "II Samuel",

    "i reis": "I Reis",
    "1 reis": "I Reis",
    "1reis": "I Reis",
    "1rs": "I Reis",
    "1 rs": "I Reis",
    "irs": "I Reis",
    "i rs": "I Reis",

    "ii reis": "II Reis",
    "2 reis": "II Reis",
    "2reis": "II Reis",
    "2rs": "II Reis",
    "2 rs": "II Reis",
    "iirs": "II Reis",
    "ii rs": "II Reis",

    "i cronicas": "I Crônicas",
    "i crônicas": "I Crônicas",
    "1 cronicas": "I Crônicas",
    "1 crônicas": "I Crônicas",
    "1cr": "I Crônicas",
    "1 cr": "I Crônicas",
    "icr": "I Crônicas",

    "ii cronicas": "II Crônicas",
    "ii crônicas": "II Crônicas",
    "2 cronicas": "II Crônicas",
    "2 crônicas": "II Crônicas",
    "2cr": "II Crônicas",
    "2 cr": "II Crônicas",
    "iicr": "II Crônicas",

    "esdras": "Esdras",
    "esd": "Esdras",
    "ed": "Esdras",

    "neemias": "Neemias",
    "ne": "Neemias",
    "nee": "Neemias",

    "tobias": "Tobias",
    "tb": "Tobias",
    "tob": "Tobias",

    "judite": "Judite",
    "jt": "Judite",
    "jdt": "Judite",
    "jud": "Judite",

    "ester": "Ester",
    "est": "Ester",
    "et": "Ester",

    "i macabeus": "I Macabeus",
    "1 macabeus": "I Macabeus",
    "1macabeus": "I Macabeus",
    "1mc": "I Macabeus",
    "1 mc": "I Macabeus",
    "imc": "I Macabeus",

    "ii macabeus": "II Macabeus",
    "2 macabeus": "II Macabeus",
    "2macabeus": "II Macabeus",
    "2mc": "II Macabeus",
    "2 mc": "II Macabeus",
    "iimc": "II Macabeus",

    # Sapienciais
    "jo": "Jó",
    "jó": "Jó",
    "job": "Jó",

    "salmos": "Salmos",
    "salmo": "Salmos",
    "sl": "Salmos",
    "sal": "Salmos",
    "sm": "Salmos",

    "proverbios": "Provérbios",
    "provérbios": "Provérbios",
    "pr": "Provérbios",
    "pv": "Provérbios",
    "prov": "Provérbios",

    "eclesiastes": "Eclesiastes",
    "ecl": "Eclesiastes",
    "ec": "Eclesiastes",
    "qoh": "Eclesiastes",

    "cantico dos canticos": "Cântico dos Cânticos",
    "cântico dos cânticos": "Cântico dos Cânticos",
    "cantico": "Cântico dos Cânticos",
    "cântico": "Cântico dos Cânticos",
    "ct": "Cântico dos Cânticos",
    "cant": "Cântico dos Cânticos",

    "sabedoria": "Sabedoria",
    "sb": "Sabedoria",
    "sab": "Sabedoria",
    "wis": "Sabedoria",

    "eclesiastico": "Eclesiástico",
    "eclesiástico": "Eclesiástico",
    "eclo": "Eclesiástico",
    "sir": "Eclesiástico",
    "siracida": "Eclesiástico",

    # Proféticos
    "isaias": "Isaías",
    "isaías": "Isaías",
    "is": "Isaías",
    "isa": "Isaías",

    "jeremias": "Jeremias",
    "jr": "Jeremias",
    "jer": "Jeremias",

    "lamentacoes": "Lamentações",
    "lamentações": "Lamentações",
    "lm": "Lamentações",
    "lam": "Lamentações",

    "baruc": "Baruc",
    "br": "Baruc",
    "bar": "Baruc",

    "ezequiel": "Ezequiel",
    "ez": "Ezequiel",
    "eze": "Ezequiel",

    "daniel": "Daniel",
    "dn": "Daniel",
    "dan": "Daniel",

    "oseias": "Oséias",
    "oséias": "Oséias",
    "os": "Oséias",
    "ose": "Oséias",

    "joel": "Joel",
    "jl": "Joel",

    "amos": "Amós",
    "amós": "Amós",
    "am": "Amós",

    "abdias": "Abdias",
    "ab": "Abdias",
    "ob": "Abdias",
    "obadias": "Abdias",

    "jonas": "Jonas",
    "jn": "Jonas",
    "jon": "Jonas",

    "miqueias": "Miquéias",
    "miquéias": "Miquéias",
    "mq": "Miquéias",
    "miq": "Miquéias",

    "naum": "Naum",
    "na": "Naum",

    "habacuc": "Habacuc",
    "habacuque": "Habacuc",
    "hab": "Habacuc",
    "hc": "Habacuc",
    "hb": "Habacuc",

    "sofonias": "Sofonias",
    "sf": "Sofonias",
    "sof": "Sofonias",

    "ageu": "Ageu",
    "ag": "Ageu",
    "age": "Ageu",

    "zacarias": "Zacarias",
    "zc": "Zacarias",
    "zac": "Zacarias",

    "malaquias": "Malaquias",
    "ml": "Malaquias",
    "mal": "Malaquias",

    # === NOVO TESTAMENTO ===
    # Evangelhos
    "sao mateus": "São Mateus",
    "são mateus": "São Mateus",
    "mateus": "São Mateus",
    "mt": "São Mateus",
    "mat": "São Mateus",

    "sao marcos": "São Marcos",
    "são marcos": "São Marcos",
    "marcos": "São Marcos",
    "mc": "São Marcos",
    "marc": "São Marcos",
    "mk": "São Marcos",

    "sao lucas": "São Lucas",
    "são lucas": "São Lucas",
    "lucas": "São Lucas",
    "lc": "São Lucas",
    "luc": "São Lucas",
    "lk": "São Lucas",

    "sao joao": "São João",
    "são joão": "São João",
    "joao": "São João",
    "joão": "São João",
    "jo": "São João",

    # Atos
    "atos dos apostolos": "Atos dos Apóstolos",
    "atos dos apóstolos": "Atos dos Apóstolos",
    "atos": "Atos dos Apóstolos",
    "at": "Atos dos Apóstolos",
    "act": "Atos dos Apóstolos",

    # Cartas Paulinas
    "romanos": "Romanos",
    "rm": "Romanos",
    "rom": "Romanos",
    "ro": "Romanos",

    "i corintios": "I Coríntios",
    "i coríntios": "I Coríntios",
    "1 corintios": "I Coríntios",
    "1 coríntios": "I Coríntios",
    "1cor": "I Coríntios",
    "1 cor": "I Coríntios",
    "1co": "I Coríntios",
    "icor": "I Coríntios",

    "ii corintios": "II Coríntios",
    "ii coríntios": "II Coríntios",
    "2 corintios": "II Coríntios",
    "2 coríntios": "II Coríntios",
    "2cor": "II Coríntios",
    "2 cor": "II Coríntios",
    "2co": "II Coríntios",
    "iicor": "II Coríntios",

    "galatas": "Gálatas",
    "gálatas": "Gálatas",
    "gl": "Gálatas",
    "gal": "Gálatas",

    "efesios": "Efésios",
    "efésios": "Efésios",
    "ef": "Efésios",
    "efe": "Efésios",

    "filipenses": "Filipenses",
    "fl": "Filipenses",
    "fp": "Filipenses",
    "fil": "Filipenses",
    "phil": "Filipenses",

    "colossenses": "Colossenses",
    "cl": "Colossenses",
    "col": "Colossenses",

    "i tessalonicenses": "I Tessalonicenses",
    "1 tessalonicenses": "I Tessalonicenses",
    "1ts": "I Tessalonicenses",
    "1 ts": "I Tessalonicenses",
    "1tes": "I Tessalonicenses",
    "its": "I Tessalonicenses",

    "ii tessalonicenses": "II Tessalonicenses",
    "2 tessalonicenses": "II Tessalonicenses",
    "2ts": "II Tessalonicenses",
    "2 ts": "II Tessalonicenses",
    "2tes": "II Tessalonicenses",
    "iits": "II Tessalonicenses",

    "i timoteo": "I Timóteo",
    "i timóteo": "I Timóteo",
    "1 timoteo": "I Timóteo",
    "1 timóteo": "I Timóteo",
    "1tm": "I Timóteo",
    "1 tm": "I Timóteo",
    "1tim": "I Timóteo",
    "itm": "I Timóteo",

    "ii timoteo": "II Timóteo",
    "ii timóteo": "II Timóteo",
    "2 timoteo": "II Timóteo",
    "2 timóteo": "II Timóteo",
    "2tm": "II Timóteo",
    "2 tm": "II Timóteo",
    "2tim": "II Timóteo",
    "iitm": "II Timóteo",

    "tito": "Tito",
    "tt": "Tito",
    "tit": "Tito",

    "filemon": "Filêmon",
    "filêmon": "Filêmon",
    "fm": "Filêmon",
    "flm": "Filêmon",
    "phlm": "Filêmon",

    "hebreus": "Hebreus",
    "hb": "Hebreus",
    "heb": "Hebreus",

    # Cartas Católicas
    "sao tiago": "São Tiago",
    "são tiago": "São Tiago",
    "tiago": "São Tiago",
    "tg": "São Tiago",
    "tia": "São Tiago",
    "jas": "São Tiago",

    "i sao pedro": "I São Pedro",
    "i são pedro": "I São Pedro",
    "1 sao pedro": "I São Pedro",
    "1 são pedro": "I São Pedro",
    "1pe": "I São Pedro",
    "1 pe": "I São Pedro",
    "1pd": "I São Pedro",
    "1pedro": "I São Pedro",
    "ipe": "I São Pedro",

    "ii sao pedro": "II São Pedro",
    "ii são pedro": "II São Pedro",
    "2 sao pedro": "II São Pedro",
    "2 são pedro": "II São Pedro",
    "2pe": "II São Pedro",
    "2 pe": "II São Pedro",
    "2pd": "II São Pedro",
    "2pedro": "II São Pedro",
    "iipe": "II São Pedro",

    "i sao joao": "I São João",
    "i são joão": "I São João",
    "1 sao joao": "I São João",
    "1 são joão": "I São João",
    "1jo": "I São João",
    "1 jo": "I São João",
    "1joao": "I São João",
    "ijo": "I São João",

    "ii sao joao": "II São João",
    "ii são joão": "II São João",
    "2 sao joao": "II São João",
    "2 são joão": "II São João",
    "2jo": "II São João",
    "2 jo": "II São João",
    "2joao": "II São João",
    "iijo": "II São João",

    "iii sao joao": "III São João",
    "iii são joão": "III São João",
    "3 sao joao": "III São João",
    "3 são joão": "III São João",
    "3jo": "III São João",
    "3 jo": "III São João",
    "3joao": "III São João",
    "iiijo": "III São João",

    "sao judas": "São Judas",
    "são judas": "São Judas",
    "judas": "São Judas",
    "jd": "São Judas",
    "jud": "São Judas",

    "apocalipse": "Apocalipse",
    "ap": "Apocalipse",
    "apoc": "Apocalipse",
    "apo": "Apocalipse",
    "rv": "Apocalipse",
    "rev": "Apocalipse",
}


def normalizar_nome(texto: str) -> str | None:
    """
    Recebe qualquer forma de nome/abreviação de livro e retorna
    o nome EXATO que está no JSON da Ave Maria.
    Retorna None se não encontrar.
    """
    if not texto:
        return None

    # Limpa e normaliza
    chave = texto.strip().lower()

    # Remove pontos e espaços extras
    chave = chave.replace(".", "").replace("  ", " ")

    return LIVROS.get(chave)
