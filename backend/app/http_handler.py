import base64
import json
import logging
import os
import re
from collections import Counter

import brain
from lex_handler import MENSAGENS, to_ssml

logger = logging.getLogger()
logger.setLevel(logging.INFO)

MAX_TEXT_CHARS = 500
MAX_TURNS = 30
SESSION_RE = re.compile(r"^[A-Za-z0-9-]{8,64}$")
VOICES = {"pt_BR": "Camila", "en_US": "Joanna"}
CACHE_SECONDS_IMPACTO = 60

_polly = None


def _get_polly():
    global _polly
    if _polly is None:
        import boto3

        _polly = boto3.client("polly")
    return _polly


def _response(status: int, body: dict, cache_seconds: int = 0) -> dict:
    headers = {"content-type": "application/json; charset=utf-8"}
    if cache_seconds:
        headers["cache-control"] = f"public, max-age={cache_seconds}"
    return {"statusCode": status, "headers": headers, "body": json.dumps(body, ensure_ascii=False)}


def synthesize(text: str, locale: str) -> str:
    audio = _get_polly().synthesize_speech(
        Text=to_ssml(text), TextType="ssml", VoiceId=VOICES[locale], Engine="neural", OutputFormat="mp3"
    )
    return base64.b64encode(audio["AudioStream"].read()).decode()


def chat(body: dict) -> dict:
    session_id = str(body.get("sessionId", ""))
    locale = body.get("locale", "pt_BR")
    text = str(body.get("text", "")).strip()
    if not SESSION_RE.match(session_id) or locale not in VOICES:
        return _response(400, {"erro": "sessionId ou locale inválido"})
    if not text or len(text) > MAX_TEXT_CHARS:
        return _response(400, {"erro": f"mensagem vazia ou maior que {MAX_TEXT_CHARS} caracteres"})
    web_session = f"web-{session_id}"
    if len(brain.load_history(web_session)) >= MAX_TURNS * 2:
        return _response(429, {"erro": "conversa muito longa; comece uma nova"})

    try:
        reply = brain.respond(web_session, locale, text, canal="web")
    except Exception:
        logger.exception("falha ao gerar resposta")
        reply = brain.Reply(fala=MENSAGENS[locale]["erro"])

    payload = {"fala": reply.fala, "beneficios": reply.beneficios, "encerrar": reply.encerrar, "modo": reply.modo}
    if body.get("voz"):
        try:
            payload["audio"] = synthesize(reply.fala, locale)
        except Exception:
            logger.exception("falha ao sintetizar voz")
    return _response(200, payload)


def aggregate(items: list[dict]) -> dict:
    beneficios, canais, idiomas, ferramentas = Counter(), Counter(), Counter(), Counter()
    turnos = 0
    for item in items:
        canais[item.get("canal", "telefone")] += 1
        idiomas[item.get("idioma", "pt_BR")] += 1
        beneficios.update(item.get("beneficios", set()))
        ferramentas.update(item.get("ferramentas", set()))
        turnos += int(item.get("turnos", 0))
    total = len(items)
    return {
        "conversas": total,
        "por_canal": dict(canais),
        "por_idioma": dict(idiomas),
        "beneficios_orientados": dict(beneficios.most_common()),
        "calculos_de_direitos": ferramentas["calcular_direitos"],
        "cras_encontrados": ferramentas["buscar_cras"],
        "media_turnos": round(turnos / total, 1) if total else 0,
    }


def impacto() -> dict:
    table = brain._get_table()
    items, kwargs = [], {
        "FilterExpression": "begins_with(pk, :p)",
        "ExpressionAttributeValues": {":p": "LIGACAO#"},
    }
    while True:
        page = table.scan(**kwargs)
        items.extend(page.get("Items", []))
        if "LastEvaluatedKey" not in page:
            break
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]
    return _response(200, aggregate(items), cache_seconds=CACHE_SECONDS_IMPACTO)


def handler(event, context):
    if event.get("aquecer"):
        brain.warm_up()
        return {"aquecido": True}
    route = event.get("routeKey", "")
    if route == "POST /chat":
        try:
            body = json.loads(event.get("body") or "{}")
        except json.JSONDecodeError:
            return _response(400, {"erro": "JSON inválido"})
        return chat(body)
    if route == "GET /impacto":
        return impacto()
    return _response(404, {"erro": "rota não encontrada"})
