import logging
from xml.sax.saxutils import escape

import brain

logger = logging.getLogger()
logger.setLevel(logging.INFO)

MENSAGENS = {
    "pt_BR": {
        "nao_ouvi": "Desculpe, não consegui ouvir. Pode falar de novo, com calma?",
        "erro": "Desculpe, tive um probleminha aqui. Pode repetir o que você disse?",
    },
    "en_US": {
        "nao_ouvi": "Sorry, I couldn't hear you. Could you say that again?",
        "erro": "Sorry, I had a small problem. Could you repeat that?",
    },
}

# Elderly callers speak slower; a slightly slower voice is easier to follow on a phone line.
SPEECH_RATE = "92%"


def to_ssml(text: str) -> str:
    return f'<speak><prosody rate="{SPEECH_RATE}">{escape(text)}</prosody></speak>'


def build_response(event: dict, reply: brain.Reply) -> dict:
    session_attributes = event.get("sessionState", {}).get("sessionAttributes") or {}
    message = {"contentType": "SSML", "content": to_ssml(reply.fala)}
    if reply.encerrar:
        intent = event["sessionState"]["intent"]
        return {
            "sessionState": {
                "sessionAttributes": session_attributes,
                "dialogAction": {"type": "Close"},
                "intent": {"name": intent["name"], "state": "Fulfilled"},
            },
            "messages": [message],
        }
    return {
        "sessionState": {
            "sessionAttributes": session_attributes,
            "dialogAction": {"type": "ElicitIntent"},
        },
        "messages": [message],
    }


def handler(event, context):
    if event.get("aquecer"):
        brain.warm_up()
        return {"aquecido": True}
    session_id = event["sessionId"]
    locale = event.get("bot", {}).get("localeId", "pt_BR")
    textos = MENSAGENS.get(locale, MENSAGENS["pt_BR"])
    user_text = (event.get("inputTranscript") or "").strip()

    if not user_text:
        return build_response(event, brain.Reply(fala=textos["nao_ouvi"]))
    try:
        reply = brain.respond(session_id, locale, user_text)
    except Exception:
        logger.exception("falha ao gerar resposta")
        reply = brain.Reply(fala=textos["erro"])
    return build_response(event, reply)
