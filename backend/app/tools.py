import difflib
import gzip
import json
import unicodedata
from functools import lru_cache
from pathlib import Path

from eligibility import Familia, avaliar

CRAS_FILE = Path(__file__).parent / "data" / "cras.json.gz"
MAX_CRAS = 3

TOOLS = [
    {
        "name": "calcular_direitos",
        "description": (
            "Aplica as regras oficiais dos benefícios à situação da família e diz quais são prováveis, "
            "possíveis ou improváveis, com valores estimados e próximo passo. Use sempre que souber pelo menos "
            "quantas pessoas moram na casa e a renda total do mês, em vez de fazer a conta de cabeça. "
            "Campos que a pessoa não informou devem ser 0 (ou null em tem_cadunico)."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "pessoas": {"type": "integer", "description": "Número de pessoas que moram na casa."},
                "renda_total_mensal": {"type": "number", "description": "Soma do que todos da casa ganham por mês, em reais. Sem Bolsa Família."},
                "idosos_60_mais": {"type": "integer"},
                "idosos_65_mais": {"type": "integer"},
                "pessoas_com_deficiencia": {"type": "integer"},
                "criancas_0_6": {"type": "integer"},
                "criancas_7_17": {"type": "integer"},
                "gestantes_ou_amamentando": {"type": "integer"},
                "estudantes_ensino_medio_publico": {"type": "integer"},
                "tem_cadunico": {"type": ["boolean", "null"]},
            },
            "required": ["pessoas", "renda_total_mensal"],
        },
    },
    {
        "name": "buscar_cras",
        "description": (
            "Busca na lista oficial do governo os CRAS de uma cidade, priorizando o bairro informado. "
            "Use quando a pessoa precisar ir ao CRAS e disser a cidade (e, se possível, o bairro). "
            "Leia só um endereço por vez em voz alta, começando pelo primeiro."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "municipio": {"type": "string", "description": "Nome da cidade."},
                "uf": {"type": "string", "description": "Sigla do estado, ex.: SP. Vazio se não souber."},
                "bairro": {"type": "string", "description": "Bairro de quem ligou. Vazio se não souber."},
            },
            "required": ["municipio"],
        },
    },
]


def normalizar(texto: str | None) -> str:
    sem_acento = unicodedata.normalize("NFKD", texto or "").encode("ascii", "ignore").decode()
    return " ".join(sem_acento.lower().replace("-", " ").split())


@lru_cache(maxsize=1)
def carregar_cras() -> tuple[dict, ...]:
    if not CRAS_FILE.exists():
        return ()
    with gzip.open(CRAS_FILE, "rt", encoding="utf-8") as f:
        return tuple(json.load(f))


def buscar_cras(municipio: str, uf: str = "", bairro: str = "") -> dict:
    registros = carregar_cras()
    if not registros:
        return {"erro": "lista de CRAS indisponível; oriente ligar no Disque Social 121"}
    uf_n = normalizar(uf).upper()
    candidatos = [r for r in registros if not uf_n or r["uf"] == uf_n]
    cidades = {normalizar(r["municipio"]) for r in candidatos}
    alvo = normalizar(municipio)
    if alvo not in cidades:
        parecidas = difflib.get_close_matches(alvo, cidades, n=1, cutoff=0.8)
        if not parecidas:
            return {"erro": f"não encontrei a cidade {municipio}", "dica": "confirme o nome da cidade e o estado"}
        alvo = parecidas[0]
    da_cidade = [r for r in candidatos if normalizar(r["municipio"]) == alvo]
    ufs = {r["uf"] for r in da_cidade}
    if len(ufs) > 1:
        return {"erro": "existe cidade com esse nome em mais de um estado", "estados": sorted(ufs)}

    bairro_n = normalizar(bairro)

    def proximidade(r: dict) -> float:
        if not bairro_n:
            return 0.0
        b = normalizar(r.get("bairro"))
        if bairro_n == b:
            return 2.0
        if bairro_n in normalizar(r.get("endereco")) or (b and (bairro_n in b or b in bairro_n)):
            return 1.5
        return difflib.SequenceMatcher(None, bairro_n, b).ratio()

    ordenados = sorted(da_cidade, key=proximidade, reverse=True)[:MAX_CRAS]
    campos = ("nome", "endereco", "bairro", "referencia", "telefone", "horario")
    return {
        "municipio": da_cidade[0]["municipio"],
        "uf": da_cidade[0]["uf"],
        "total_na_cidade": len(da_cidade),
        "cras": [{k: r.get(k) for k in campos if r.get(k)} for r in ordenados],
        "observacao": "sem bairro informado, a ordem não indica distância" if not bairro_n else "",
    }


def _int(entrada: dict, campo: str) -> int:
    return max(0, int(entrada.get(campo) or 0))


def executar(nome: str, entrada: dict) -> dict:
    if nome == "calcular_direitos":
        familia = Familia(
            pessoas=max(1, _int(entrada, "pessoas")),
            renda_total_mensal=float(entrada.get("renda_total_mensal") or 0),
            idosos_60_mais=max(_int(entrada, "idosos_60_mais"), _int(entrada, "idosos_65_mais")),
            idosos_65_mais=_int(entrada, "idosos_65_mais"),
            pessoas_com_deficiencia=_int(entrada, "pessoas_com_deficiencia"),
            criancas_0_6=_int(entrada, "criancas_0_6"),
            criancas_7_17=_int(entrada, "criancas_7_17"),
            gestantes_ou_amamentando=_int(entrada, "gestantes_ou_amamentando"),
            estudantes_ensino_medio_publico=_int(entrada, "estudantes_ensino_medio_publico"),
            tem_cadunico=entrada.get("tem_cadunico"),
        )
        return avaliar(familia)
    if nome == "buscar_cras":
        return buscar_cras(entrada.get("municipio", ""), entrada.get("uf", ""), entrada.get("bairro", ""))
    return {"erro": f"ferramenta desconhecida: {nome}"}
