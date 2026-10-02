"""Guided conversation that needs no language model.

Used when the model is unavailable (outage, timeouts, account suspension): the caller still gets a
complete answer from the same eligibility rules and the same CRAS list, through short fixed questions.
"""

import re
import time

import tools
from eligibility import SALARIO_MINIMO, Familia, avaliar

STATE_TTL_SECONDS = 24 * 3600
_memory: dict[str, dict] = {}

PT_NUMBERS = {
    "zero": 0, "um": 1, "uma": 1, "dois": 2, "duas": 2, "tres": 3, "quatro": 4, "cinco": 5, "seis": 6,
    "sete": 7, "oito": 8, "nove": 9, "dez": 10, "onze": 11, "doze": 12, "treze": 13, "quatorze": 14,
    "catorze": 14, "quinze": 15, "dezesseis": 16, "dezessete": 17, "dezoito": 18, "dezenove": 19,
    "vinte": 20, "trinta": 30, "quarenta": 40, "cinquenta": 50, "sessenta": 60, "setenta": 70,
    "oitenta": 80, "noventa": 90, "cem": 100, "cento": 100, "duzentos": 200, "duzentas": 200,
    "trezentos": 300, "trezentas": 300, "quatrocentos": 400, "quinhentos": 500, "seiscentos": 600,
    "setecentos": 700, "oitocentos": 800, "novecentos": 900,
}
EN_NUMBERS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8,
    "nine": 9, "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "sixteen": 16, "seventeen": 17, "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30,
    "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
}
NONE_WORDS = {"nenhum", "nenhuma", "ninguem", "nada", "none", "nobody", "nothing", "no one"}
ALONE_PHRASES = ("so eu", "sozinho", "sozinha", "moro so", "just me", "alone", "only me")
NO_WORDS = ("nao", "nenhum", "ninguem", "no", "nope", "nobody", "none")
YES_WORDS = ("sim", "tem", "temos", "tenho", "yes", "yeah", "yep", "sure", "claro", "isso")
GOODBYE = ("tchau", "obrigad", "era so isso", "so isso", "ate logo", "bye", "thank", "that's all", "thats all")
EMERGENCY = ("me bate", "bateu", "apanh", "violencia", "agredi", "estupr", "me matar", "suicid", "socorro",
             "hits me", "beats me", "abuse", "kill myself", "emergency")
CRAS_WORDS = ("cras", "onde fica", "endereco", "where is", "where's", "address")

STATES = {
    "acre": "AC", "alagoas": "AL", "amapa": "AP", "amazonas": "AM", "bahia": "BA", "ceara": "CE",
    "distrito federal": "DF", "espirito santo": "ES", "goias": "GO", "maranhao": "MA", "mato grosso do sul": "MS",
    "mato grosso": "MT", "minas gerais": "MG", "para": "PA", "paraiba": "PB", "parana": "PR",
    "pernambuco": "PE", "piaui": "PI", "rio de janeiro": "RJ", "rio grande do norte": "RN",
    "rio grande do sul": "RS", "rondonia": "RO", "roraima": "RR", "santa catarina": "SC",
    "sao paulo": "SP", "sergipe": "SE", "tocantins": "TO",
}

TEXT = {
    "pt_BR": {
        "intro": "Vou te fazer algumas perguntas rápidas para descobrir seus direitos.",
        "ask": [
            "Quantas pessoas moram na sua casa, contando com você?",
            "Somando o que todo mundo da casa ganha por mês, quanto dá, em reais? Se ninguém tem renda, diga zero.",
            "Alguém na casa tem 65 anos ou mais? Responda sim ou não.",
            "Alguém na casa tem alguma deficiência, inclusive autismo? Sim ou não.",
            "Quantas crianças de até 6 anos moram com você? Se nenhuma, diga zero.",
            "E quantas crianças ou adolescentes de 7 a 17 anos?",
        ],
        "repeat_number": "Desculpe, não entendi. Diga só o número, por exemplo: três.",
        "repeat_yes_no": "Desculpe, não entendi. Responda sim ou não.",
        "result_intro": "Pelo que você me contou, você pode ter direito a:",
        "result_none": "Pelo que você me contou, a renda está acima do limite dos principais benefícios. Mesmo assim, os remédios da Farmácia Popular são gratuitos para todos, com receita.",
        "confirm": "Quem confirma é o CRAS ou o INSS.",
        "first_step": "O primeiro passo é fazer ou atualizar o Cadastro Único no CRAS, levando CPF ou título de eleitor. É gratuito.",
        "ask_city": "Quer que eu procure o CRAS mais perto? Diga a sua cidade, o estado e o bairro.",
        "city_not_found": "Não encontrei essa cidade. Diga de novo o nome da cidade e o estado, por exemplo: Campinas, São Paulo.",
        "cras": "O CRAS mais perto é o {nome}, na {endereco}, bairro {bairro}.",
        "reference": " Fica {referencia}.",
        "phone": " O telefone é {telefone}.",
        "hours": " Funciona {horario}.",
        "anything_else": "Posso ajudar em mais alguma coisa?",
        "goodbye": "Foi um prazer ajudar. Para outras dúvidas, ligue no Disque Social 121. Até logo!",
        "emergency": "Se você está em perigo, ligue agora para a Polícia, no 190, ou para a Central da Mulher, no 180. Se pensar em se machucar, ligue para o CVV, no 188.",
        "per_month": "{valor} reais por mês",
        "maybe": "talvez",
        "names": {
            "bpc": "o BPC", "bolsa_familia": "o Bolsa Família", "pe_de_meia": "o Pé-de-Meia",
            "tarifa_social": "o desconto na conta de luz", "carteira_idoso": "a Carteira da Pessoa Idosa",
        },
        "join": " e ",
    },
    "en_US": {
        "intro": "I'll ask you a few quick questions to find out your rights.",
        "ask": [
            "How many people live in your household, including you?",
            "Adding up what everyone in the house earns per month, how much is it, in reais? If nobody has income, say zero.",
            "Is anyone in the house 65 or older? Please answer yes or no.",
            "Does anyone in the house have a disability, including autism? Yes or no.",
            "How many children aged 6 or under live with you? If none, say zero.",
            "And how many children or teenagers aged 7 to 17?",
        ],
        "repeat_number": "Sorry, I didn't catch that. Please just say the number, for example: three.",
        "repeat_yes_no": "Sorry, I didn't catch that. Please answer yes or no.",
        "result_intro": "From what you told me, you may be entitled to:",
        "result_none": "From what you told me, the income is above the limit for the main benefits. Even so, medicines from the Popular Pharmacy program are free for everyone with a prescription.",
        "confirm": "Only CRAS or INSS can confirm it.",
        "first_step": "The first step is to register or update the Cadastro Único at the CRAS, bringing a CPF or voter ID. It is free.",
        "ask_city": "Would you like me to find the nearest CRAS? Tell me your city, state and neighborhood.",
        "city_not_found": "I couldn't find that city. Please say the city and the state again, for example: Campinas, São Paulo.",
        "cras": "The nearest CRAS is {nome}, at {endereco}, in {bairro}.",
        "reference": " It is {referencia}.",
        "phone": " The phone number is {telefone}.",
        "hours": " Opening hours: {horario}.",
        "anything_else": "Can I help you with anything else?",
        "goodbye": "It was a pleasure to help. For other questions, call Disque Social at 121. Goodbye!",
        "emergency": "If you are in danger, call the police now at 190, or the women's helpline at 180. If you are thinking of hurting yourself, call CVV at 188.",
        "per_month": "{valor} reais a month",
        "maybe": "possibly",
        "names": {
            "bpc": "BPC, the minimum-wage benefit", "bolsa_familia": "Bolsa Família", "pe_de_meia": "Pé-de-Meia",
            "tarifa_social": "the electricity discount", "carteira_idoso": "the senior travel card",
        },
        "join": " and ",
    },
}

QUESTION_FIELDS = ["pessoas", "renda", "idoso", "deficiencia", "criancas_0_6", "criancas_7_17"]
YES_NO_FIELDS = {"idoso", "deficiencia"}
STEP_CITY = len(QUESTION_FIELDS)
STEP_DONE = STEP_CITY + 1
BENEFIT_ORDER = ["bpc", "bolsa_familia", "pe_de_meia", "tarifa_social", "carteira_idoso"]


def _words_to_number(tokens: list[str], table: dict[str, int], hundred: str | None, thousand: str) -> int | None:
    total, current, seen = 0, 0, False
    for tok in tokens:
        if tok in table:
            current += table[tok]
            seen = True
        elif hundred and tok == hundred:
            current = max(current, 1) * 100
            seen = True
        elif tok == thousand:
            total += max(current, 1) * 1000
            current, seen = 0, True
        elif tok in ("e", "and", "reais", "real", "a", "per", "por", "mes", "month"):
            continue
        elif seen:
            break
    return total + current if seen else None


def parse_number(text: str) -> int | None:
    norm = tools.normalizar(text)
    digits = re.search(r"\d[\d.,]*", norm)
    if digits:
        raw = re.sub(r"[.,]\d{2}$", "", digits.group())  # drop cents: 1.500,00 / 350.00
        return int(re.sub(r"[.,]", "", raw) or 0)
    if any(w in norm for w in ALONE_PHRASES):
        return 1
    tokens = re.findall(r"[a-z]+", norm)
    for i, tok in enumerate(tokens):
        if tok in PT_NUMBERS or tok in ("mil", "cem", "cento"):
            return _words_to_number(tokens[i:], PT_NUMBERS, None, "mil")
        if tok in EN_NUMBERS or tok in ("hundred", "thousand"):
            return _words_to_number(tokens[i:], EN_NUMBERS, "hundred", "thousand")
    if any(w in norm for w in NONE_WORDS):
        return 0
    return None


def parse_yes_no(text: str) -> bool | None:
    tokens = set(re.findall(r"[a-z]+", tools.normalizar(text)))
    if tokens & set(NO_WORDS):
        return False
    if tokens & set(YES_WORDS):
        return True
    return None


def find_location(text: str) -> tuple[str, str, str] | None:
    """Finds (city, state, rest-of-text) in free speech like 'moro em Altos, Piauí, no bairro Santa Inês'."""
    norm = f" {tools.normalizar(text).replace(',', ' ')} "
    uf = ""
    for name in sorted(STATES, key=len, reverse=True):
        if f" {name} " in norm:
            uf = STATES[name]
            break
    if not uf:
        sigla = re.search(r" (ac|al|ap|am|ba|ce|df|es|go|ma|ms|mt|mg|pa|pb|pr|pe|pi|rj|rn|rs|ro|rr|sc|sp|se|to) ", norm)
        uf = sigla.group(1).upper() if sigla else ""
    cities = {(tools.normalizar(r["municipio"]), r["uf"]) for r in tools.carregar_cras() if not uf or r["uf"] == uf}
    matches = [(c, u) for c, u in cities if f" {c} " in norm]
    if not matches:
        return None
    city, city_uf = max(matches, key=lambda m: len(m[0]))
    rest = norm.replace(f" {city} ", " ")
    return city, uf or city_uf, rest.strip()


def _money(value: float) -> str:
    return f"{value:.0f}" if float(value).is_integer() else f"{value:.2f}".replace(".", ",")


def describe_result(result: dict, t: dict) -> tuple[str, list[str]]:
    items, names = [], []
    for key in BENEFIT_ORDER:
        b = result["beneficios"].get(key)
        if not b or b["situacao"] not in ("provavel", "possivel"):
            continue
        label = t["names"][key]
        if b.get("valor_mensal_estimado"):
            label += ", " + t["per_month"].format(valor=_money(b["valor_mensal_estimado"]))
        if b["situacao"] == "possivel":
            label = f"{t['maybe']} {label}"
        items.append(label)
        names.append(key)
    if not items:
        return t["result_none"], ["farmacia_popular"]
    listing = t["join"].join([", ".join(items[:-1]), items[-1]] if len(items) > 1 else items)
    return f"{t['result_intro']} {listing}. {t['confirm']} {t['first_step']}", ["cadunico", *names]


def describe_cras(found: dict, t: dict) -> str:
    c = found["cras"][0]
    text = t["cras"].format(nome=c.get("nome", "CRAS"), endereco=c.get("endereco", ""), bairro=c.get("bairro", ""))
    if c.get("referencia"):
        text += t["reference"].format(referencia=c["referencia"].lower())
    if c.get("telefone"):
        digits = re.sub(r"\D", "", c["telefone"])
        spoken = " ".join(digits[:2]) + ", " + " ".join(digits[2:-4]) + ", " + " ".join(digits[-4:])
        text += t["phone"].format(telefone=spoken)
    if c.get("horario"):
        text += t["hours"].format(horario=c["horario"])
    return text


def load_state(session_id: str, table) -> dict | None:
    if table is None:
        return _memory.get(session_id)
    item = table.get_item(Key={"pk": f"ESSENCIAL#{session_id}"}).get("Item")
    return item["estado"] if item else None


def save_state(session_id: str, state: dict, table) -> None:
    if table is None:
        _memory[session_id] = state
        return
    table.put_item(Item={"pk": f"ESSENCIAL#{session_id}", "estado": state, "ttl": int(time.time()) + STATE_TTL_SECONDS})


def respond(session_id: str, locale: str, user_text: str, table=None) -> dict:
    """Returns {fala, beneficios, ferramentas, encerrar}."""
    t = TEXT.get(locale, TEXT["pt_BR"])
    norm = tools.normalizar(user_text)
    state = load_state(session_id, table)
    out = {"fala": "", "beneficios": [], "ferramentas": [], "encerrar": False}
    prefix = t["emergency"] + " " if any(w in norm for w in EMERGENCY) else ""
    if prefix:
        out["beneficios"].append("emergencia")

    if state is None:
        wants_cras = any(w in norm for w in CRAS_WORDS)
        state = {"passo": STEP_CITY if wants_cras else 0, "dados": {}}
        if wants_cras and find_location(user_text):
            return _answer_city(session_id, state, user_text, t, out, prefix, table)
        question = t["ask_city"] if wants_cras else t["ask"][0]
        save_state(session_id, state, table)
        out["fala"] = f"{prefix}{t['intro']} {question}"
        return out

    passo = int(state["passo"])
    if passo >= STEP_DONE or (passo != STEP_CITY and any(w in norm for w in GOODBYE) and passo > 0):
        out.update(fala=prefix + t["goodbye"], encerrar=True)
        return out

    if passo < len(QUESTION_FIELDS):
        field = QUESTION_FIELDS[passo]
        value = parse_yes_no(user_text) if field in YES_NO_FIELDS else parse_number(user_text)
        if field == "renda" and ("salario" in norm or "minimum wage" in norm):
            value = SALARIO_MINIMO * (0.5 if ("meio" in norm or "half" in norm) else (value or 1))
        if value is None:
            out["fala"] = prefix + (t["repeat_yes_no"] if field in YES_NO_FIELDS else t["repeat_number"]) + " " + t["ask"][passo]
            return out
        state["dados"][field] = value
        state["passo"] = passo + 1
        if state["passo"] < len(QUESTION_FIELDS):
            save_state(session_id, state, table)
            out["fala"] = prefix + t["ask"][state["passo"]]
            return out
        d = state["dados"]
        familia = Familia(
            pessoas=max(1, int(d["pessoas"])),
            renda_total_mensal=float(d["renda"]),
            idosos_65_mais=int(bool(d["idoso"])),
            idosos_60_mais=int(bool(d["idoso"])),
            pessoas_com_deficiencia=int(bool(d["deficiencia"])),
            criancas_0_6=int(d["criancas_0_6"]),
            criancas_7_17=int(d["criancas_7_17"]),
        )
        speech, benefits = describe_result(avaliar(familia), t)
        save_state(session_id, state, table)
        out["beneficios"] += benefits
        out["ferramentas"].append("calcular_direitos")
        out["fala"] = f"{prefix}{speech} {t['ask_city']}"
        return out

    if not find_location(user_text) and (any(w in norm for w in GOODBYE) or parse_yes_no(user_text) is False):
        out.update(fala=prefix + t["goodbye"], encerrar=True)
        return out
    return _answer_city(session_id, state, user_text, t, out, prefix, table)


def _answer_city(session_id, state, user_text, t, out, prefix, table) -> dict:
    location = find_location(user_text)
    found = tools.buscar_cras(location[0], location[1], location[2]) if location else {"erro": "sem cidade"}
    if "erro" in found or not found.get("cras"):
        save_state(session_id, state, table)
        out["fala"] = prefix + t["city_not_found"]
        return out
    state["passo"] = STEP_DONE
    save_state(session_id, state, table)
    out["ferramentas"].append("buscar_cras")
    out["fala"] = f"{prefix}{describe_cras(found, t)} {t['anything_else']}"
    return out


__all__ = ["respond", "parse_number", "parse_yes_no", "find_location", "SALARIO_MINIMO"]
