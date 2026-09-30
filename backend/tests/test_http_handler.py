import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import brain  # noqa: E402
import http_handler  # noqa: E402

SESSION = "abcd1234-efgh"


def post(body):
    return http_handler.handler({"routeKey": "POST /chat", "body": json.dumps(body)}, None)


def test_chat_uses_web_channel_and_prefixed_session(monkeypatch):
    seen = {}
    monkeypatch.setattr(brain, "load_history", lambda s: [])

    def fake_respond(session_id, locale, text, canal):
        seen.update(session=session_id, canal=canal)
        return brain.Reply(fala="Oi!", beneficios=["bpc"])

    monkeypatch.setattr(brain, "respond", fake_respond)
    out = post({"sessionId": SESSION, "text": "oi", "locale": "pt_BR"})
    assert out["statusCode"] == 200
    assert json.loads(out["body"]) == {"fala": "Oi!", "beneficios": ["bpc"], "encerrar": False}
    assert seen == {"session": f"web-{SESSION}", "canal": "web"}


def test_chat_returns_audio_when_voice_requested(monkeypatch):
    monkeypatch.setattr(brain, "load_history", lambda s: [])
    monkeypatch.setattr(brain, "respond", lambda *a, **k: brain.Reply(fala="Oi!"))
    monkeypatch.setattr(http_handler, "synthesize", lambda text, locale: "QUJD")
    body = json.loads(post({"sessionId": SESSION, "text": "oi", "voz": True})["body"])
    assert body["audio"] == "QUJD"


def test_chat_rejects_bad_input():
    assert post({"sessionId": "x", "text": "oi"})["statusCode"] == 400
    assert post({"sessionId": SESSION, "text": ""})["statusCode"] == 400
    assert post({"sessionId": SESSION, "text": "a" * 501})["statusCode"] == 400
    assert post({"sessionId": SESSION, "text": "oi", "locale": "fr_FR"})["statusCode"] == 400
    bad_json = http_handler.handler({"routeKey": "POST /chat", "body": "{"}, None)
    assert bad_json["statusCode"] == 400


def test_chat_limits_conversation_length(monkeypatch):
    monkeypatch.setattr(brain, "load_history", lambda s: [{}] * 60)
    assert post({"sessionId": SESSION, "text": "oi"})["statusCode"] == 429


def test_model_failure_still_answers(monkeypatch):
    monkeypatch.setattr(brain, "load_history", lambda s: [])

    def fail(*a, **k):
        raise RuntimeError("fora do ar")

    monkeypatch.setattr(brain, "respond", fail)
    body = json.loads(post({"sessionId": SESSION, "text": "oi"})["body"])
    assert "probleminha" in body["fala"]


def test_aggregate_counts_channels_benefits_and_tools():
    items = [
        {"canal": "telefone", "idioma": "pt_BR", "beneficios": {"bpc", "cadunico"}, "ferramentas": {"calcular_direitos", "buscar_cras"}, "turnos": 4},
        {"canal": "web", "idioma": "en_US", "beneficios": {"bpc"}, "turnos": 2},
        {"idioma": "pt_BR", "turnos": 3},
    ]
    r = http_handler.aggregate(items)
    assert r["conversas"] == 3
    assert r["por_canal"] == {"telefone": 2, "web": 1}
    assert r["beneficios_orientados"] == {"bpc": 2, "cadunico": 1}
    assert r["calculos_de_direitos"] == 1 and r["cras_encontrados"] == 1
    assert r["media_turnos"] == 3.0


def test_unknown_route_is_404():
    assert http_handler.handler({"routeKey": "GET /nada"}, None)["statusCode"] == 404
