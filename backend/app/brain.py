import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

import essential
import tools

# "bedrock" (default) or "anthropic" (Claude API, key read from SSM) — the fallback if Bedrock access is lost.
LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "bedrock")
# Free-plan accounts only get the bedrock-runtime path (not Mantle), and newer models are gated.
MODEL_ID = os.environ.get("MODEL_ID", "us.anthropic.claude-haiku-4-5-20251001-v1:0")
TABLE_NAME = os.environ.get("TABLE_NAME", "")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")
MAX_HISTORY_MESSAGES = 30
MAX_TOOL_ROUNDS = 3
# After the model fails, skip it for a while so each caller turn doesn't wait out the retries again.
LLM_COOLDOWN_SECONDS = {"permanente": 600, "temporaria": 120}
_llm_down_until = 0.0
HISTORY_TTL_SECONDS = 24 * 3600

KNOWLEDGE = (Path(__file__).parent / "knowledge.md").read_text(encoding="utf-8")

LANGUAGE_NAMES = {"pt_BR": "português do Brasil", "en_US": "English"}

SYSTEM_PROMPT = f"""Você é a assistente do Liga pra Mim, uma linha telefônica gratuita que ajuda pessoas de baixa renda no Brasil a descobrir e acessar benefícios sociais. Muitas pessoas que ligam são idosas, não sabem ler ou nunca usaram internet. Esta é uma LIGAÇÃO: tudo que você escrever em "fala" será lido em voz alta.

Como falar:
- Frases curtas e simples, como quem conversa com um vizinho. No máximo três frases por resposta.
- Uma pergunta por vez.
- Nada de listas, emojis, links, endereços de site ou siglas sem explicar. Escreva números sempre em algarismos, copiados exatamente da ferramenta ou da base ("600 reais", "Rua Colorado, 2000"): a voz lê os algarismos corretamente, e converter para palavras causa erros. Telefones longos: dígito por dígito separados por espaço, em grupos ("8 6, 9 9 4 4, 9 0 1 7"). Números curtos de serviço (121, 135, 180, 188, 190, 192, 100) escreva normalmente, como "180".
- Seja calorosa e paciente. Nunca faça a pessoa se sentir burra. Se não entender, peça para repetir de outro jeito.

Como ajudar:
1. Entenda a situação com perguntas simples: quantas pessoas moram na casa, quanto a casa ganha por mês somando todo mundo, se tem idoso de sessenta e cinco anos ou mais, pessoa com deficiência, criança, gestante ou estudante do ensino médio, e se a família já tem o Cadastro Único.
2. Assim que souber quantas pessoas moram na casa e a renda total, use a ferramenta calcular_direitos imediatamente, na mesma resposta, mesmo que seja a primeira fala da pessoa. Conte a própria pessoa e as crianças que ela mencionou. Não pergunte antes sobre Cadastro Único: se não souber, deixe tem_cadunico vazio. Diga o nome do benefício principal (por exemplo BPC ou Bolsa Família) e o valor estimado. Se um idoso de 65 anos ou mais, ou uma pessoa com deficiência da casa, já recebe aposentadoria, pensão ou BPC de até 1 salário mínimo, informe esse valor em beneficio_ate_1_sm_de_idoso_ou_pcd: a lei manda desconsiderar esse valor no BPC de outro membro. Ela aplica as regras oficiais: confie no resultado dela, não faça contas de cabeça. Conte primeiro o benefício mais importante; não despeje tudo de uma vez.
3. Quando a pessoa precisar ir ao CRAS, pergunte a cidade e o bairro e use a ferramenta buscar_cras. Diga o nome e o endereço de um CRAS por vez, devagar, e ofereça repetir. Se tiver telefone, ofereça dizer. Fale do horário exatamente como veio da ferramenta (por exemplo "abre cinco dias por semana"): nunca invente dias da semana nem horas de abertura, porque a pessoa pode perder a viagem.
Sobre documentos, diga exatamente o que está na base de conhecimento: para o Cadastro Único, o responsável leva CPF ou título de eleitor; para o BPC, CPF de todos e biometria. Não troque por outros documentos.
4. Antes de terminar, resuma o próximo passo em uma frase e pergunte se pode ajudar em mais alguma coisa.

Regras de segurança:
- Nunca peça CPF, NIS, senha, dados bancários ou nome completo. Se a pessoa quiser falar, diga que não precisa.
- Nunca prometa que a pessoa vai receber: nunca diga "tem sim", "tem direito" sem o "pode", "você vai receber" ou "com certeza". Em inglês, a mesma regra: nunca "you will get", "you can get", "she gets" ou "you are entitled"; diga "you may be entitled to" ou "she may qualify for". Diga "pelo que você me contou, você pode ter direito" e explique que quem confirma é o CRAS ou o INSS.
- Use somente a base de conhecimento. Se não souber, diga que não sabe e indique o CRAS ou o Disque Social 121.
- Quando fizer sentido, avise que ninguém do governo cobra para fazer cadastro e que pedir PIX ou senha é golpe.
- Se a pessoa falar de emergência, violência, fome grave ou vontade de se machucar, dê primeiro o número certo: SAMU 192, Polícia 190, Central da Mulher 180, CVV 188.
- Você não é advogada nem médica.

Idioma: responda sempre no idioma da ligação. Se for inglês, a pessoa provavelmente está conhecendo o projeto: explique os programas brasileiros em inglês, do mesmo jeito simples.

Campos da resposta:
- fala: o que será dito em voz alta.
- beneficios: identificadores dos benefícios que você orientou nesta resposta, entre: cadunico, bolsa_familia, bpc, tarifa_social, pe_de_meia, farmacia_popular, carteira_idoso, emergencia. Lista vazia se nenhum.
- encerrar: true só quando a pessoa se despedir ou disser que não precisa de mais nada; nesse caso "fala" é a despedida.

<base_de_conhecimento>
{KNOWLEDGE}
</base_de_conhecimento>"""

REPLY_SCHEMA = {
    "type": "object",
    "properties": {
        "fala": {"type": "string"},
        "beneficios": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": [
                    "cadunico", "bolsa_familia", "bpc", "tarifa_social",
                    "pe_de_meia", "farmacia_popular", "carteira_idoso", "emergencia",
                ],
            },
        },
        "encerrar": {"type": "boolean"},
    },
    "required": ["fala", "beneficios", "encerrar"],
    "additionalProperties": False,
}


@dataclass
class Reply:
    fala: str
    beneficios: list[str] = field(default_factory=list)
    encerrar: bool = False
    ferramentas: list[str] = field(default_factory=list)
    chamadas: list[dict] = field(default_factory=list)


_client = None
_table = None


def _anthropic_api_key() -> str:
    import boto3

    param = boto3.client("ssm").get_parameter(Name=os.environ["ANTHROPIC_API_KEY_PARAM"], WithDecryption=True)
    return param["Parameter"]["Value"]


def _get_client():
    global _client
    if _client is None:
        # Typical latency is ~4 s but the model occasionally stalls for a minute; a fresh retry beats waiting on a call.
        if LLM_PROVIDER == "anthropic":
            from anthropic import Anthropic

            _client = Anthropic(api_key=_anthropic_api_key(), timeout=8.0, max_retries=2)
        else:
            from anthropic import AnthropicBedrock

            _client = AnthropicBedrock(aws_region=AWS_REGION, timeout=8.0, max_retries=2)
    return _client


def _get_table():
    global _table
    if _table is None and TABLE_NAME:
        import boto3

        _table = boto3.resource("dynamodb").Table(TABLE_NAME)
    return _table


def warm_up() -> None:
    """Opens the Bedrock and DynamoDB connections so a caller never pays for a cold container."""
    # Same system/tools/format as a real turn: keeps Bedrock's prompt cache (5-min TTL) and schema compilation hot.
    _get_client().messages.create(
        model=MODEL_ID,
        max_tokens=1,
        system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
        tools=tools.TOOLS,
        output_config={"format": {"type": "json_schema", "schema": REPLY_SCHEMA}},
        messages=[{"role": "user", "content": "ok"}],
    )
    table = _get_table()
    if table is not None:
        table.get_item(Key={"pk": "AQUECIMENTO"})


def load_history(session_id: str) -> list[dict]:
    table = _get_table()
    if table is None:
        return []
    item = table.get_item(Key={"pk": f"CONVERSA#{session_id}"}).get("Item")
    return list(item["mensagens"]) if item else []


def save_turn(session_id: str, locale: str, history: list[dict], user_text: str, reply: Reply, canal: str = "telefone") -> None:
    table = _get_table()
    if table is None:
        return
    now = int(time.time())
    mensagens = history + [
        {"role": "user", "content": user_text},
        {"role": "assistant", "content": reply.fala},
    ]
    table.put_item(Item={
        "pk": f"CONVERSA#{session_id}",
        "mensagens": mensagens[-MAX_HISTORY_MESSAGES:],
        "ttl": now + HISTORY_TTL_SECONDS,
    })
    update = "SET idioma = :idioma, canal = :canal, atualizado = :agora, turnos = if_not_exists(turnos, :zero) + :um, inicio = if_not_exists(inicio, :agora)"
    values = {":idioma": locale, ":canal": canal, ":agora": now, ":zero": 0, ":um": 1}
    adds = []
    if reply.beneficios:
        adds.append("beneficios :b")
        values[":b"] = set(reply.beneficios)
    if reply.ferramentas:
        adds.append("ferramentas :f")
        values[":f"] = set(reply.ferramentas)
    if adds:
        update += " ADD " + ", ".join(adds)
    table.update_item(
        Key={"pk": f"LIGACAO#{session_id}"},
        UpdateExpression=update,
        ExpressionAttributeValues=values,
    )


def parse_reply(text: str) -> Reply:
    data = json.loads(text)
    return Reply(
        fala=data["fala"].strip(),
        beneficios=list(dict.fromkeys(data.get("beneficios", []))),
        encerrar=bool(data.get("encerrar", False)),
    )


def ask_model(history: list[dict], user_text: str, locale: str) -> Reply:
    idioma = LANGUAGE_NAMES.get(locale, "português do Brasil")
    messages = history + [{"role": "user", "content": f"[idioma da ligação: {idioma}]\n{user_text}"}]
    ferramentas_usadas = []
    chamadas = []
    for _ in range(MAX_TOOL_ROUNDS + 1):
        response = _get_client().messages.create(
            model=MODEL_ID,
            max_tokens=2000,
            system=[{"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}}],
            tools=tools.TOOLS,
            output_config={"format": {"type": "json_schema", "schema": REPLY_SCHEMA}},
            messages=messages,
        )
        if response.stop_reason == "refusal":
            raise RuntimeError("modelo recusou a resposta")
        if response.stop_reason != "tool_use":
            # Rarely the model ends a turn with no text after a tool call; on a phone line that is silence, so ask again.
            if any(b.type == "text" for b in response.content):
                break
            continue
        messages.append({"role": "assistant", "content": response.content})
        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            ferramentas_usadas.append(block.name)
            try:
                output = tools.executar(block.name, block.input)
                chamadas.append({"nome": block.name, "entrada": block.input, "saida": output})
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(output, ensure_ascii=False)})
            except Exception as exc:
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": str(exc), "is_error": True})
        messages.append({"role": "user", "content": results})
    else:
        raise RuntimeError("limite de chamadas de ferramenta atingido")
    text = next(b.text for b in response.content if b.type == "text")
    reply = parse_reply(text)
    reply.ferramentas = ferramentas_usadas
    reply.chamadas = chamadas
    return reply


def _failure_kind(exc: Exception) -> str:
    status = getattr(exc, "status_code", None)
    return "permanente" if status in (400, 401, 403, 404) else "temporaria"


def llm_available() -> bool:
    return time.time() >= _llm_down_until


def _essential_reply(session_id: str, locale: str, user_text: str) -> Reply:
    out = essential.respond(session_id, locale, user_text, _get_table())
    return Reply(fala=out["fala"], beneficios=out["beneficios"], encerrar=out["encerrar"], ferramentas=out["ferramentas"])


def respond(session_id: str, locale: str, user_text: str, canal: str = "telefone") -> Reply:
    global _llm_down_until
    t0 = time.perf_counter()
    history = load_history(session_id)
    t1 = time.perf_counter()
    modo = "ia"
    in_essential = essential.load_state(session_id, _get_table()) is not None
    if in_essential or not llm_available():
        reply, modo = _essential_reply(session_id, locale, user_text), "essencial"
    else:
        try:
            reply = ask_model(history, user_text, locale)
        except Exception as exc:
            kind = _failure_kind(exc)
            _llm_down_until = time.time() + LLM_COOLDOWN_SECONDS[kind]
            print(json.dumps({"falha_modelo": type(exc).__name__, "tipo": kind, "detalhe": str(exc)[:300]}))
            reply, modo = _essential_reply(session_id, locale, user_text), "essencial"
    t2 = time.perf_counter()
    save_turn(session_id, locale, history, user_text, reply, canal)
    t3 = time.perf_counter()
    print(json.dumps({"tempo_ms": {"historico": round((t1 - t0) * 1000), "modelo": round((t2 - t1) * 1000),
                                   "salvar": round((t3 - t2) * 1000)}, "turnos": len(history) // 2, "modo": modo}))
    return reply
