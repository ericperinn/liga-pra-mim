import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import brain  # noqa: E402
import lex_handler  # noqa: E402


def lex_event(text, locale="pt_BR", intent="FallbackIntent"):
    return {
        "sessionId": "contato-123",
        "inputTranscript": text,
        "bot": {"localeId": locale},
        "sessionState": {"intent": {"name": intent, "state": "InProgress"}, "sessionAttributes": {"a": "1"}},
    }


def test_keeps_conversation_open(monkeypatch):
    monkeypatch.setattr(brain, "respond", lambda s, l, t: brain.Reply(fala="Quantas pessoas moram na sua casa?"))
    out = lex_handler.handler(lex_event("quero saber do bolsa família"), None)
    assert out["sessionState"]["dialogAction"]["type"] == "ElicitIntent"
    assert out["sessionState"]["sessionAttributes"] == {"a": "1"}
    assert "Quantas pessoas moram na sua casa?" in out["messages"][0]["content"]
    assert out["messages"][0]["content"].startswith("<speak>")


def test_closes_when_model_says_goodbye(monkeypatch):
    monkeypatch.setattr(brain, "respond", lambda s, l, t: brain.Reply(fala="Tchau!", encerrar=True))
    out = lex_handler.handler(lex_event("era só isso, obrigado"), None)
    assert out["sessionState"]["dialogAction"]["type"] == "Close"
    assert out["sessionState"]["intent"] == {"name": "FallbackIntent", "state": "Fulfilled"}


def test_empty_transcript_asks_to_repeat_without_calling_model(monkeypatch):
    def boom(*a):
        raise AssertionError("não deveria chamar o modelo")

    monkeypatch.setattr(brain, "respond", boom)
    out = lex_handler.handler(lex_event("  "), None)
    assert "falar de novo" in out["messages"][0]["content"]


def test_model_failure_becomes_spoken_apology(monkeypatch):
    def fail(*a):
        raise RuntimeError("bedrock fora do ar")

    monkeypatch.setattr(brain, "respond", fail)
    out = lex_handler.handler(lex_event("hello", locale="en_US"), None)
    assert "Sorry" in out["messages"][0]["content"]
    assert out["sessionState"]["dialogAction"]["type"] == "ElicitIntent"


def test_warm_up_event_skips_conversation(monkeypatch):
    called = []
    monkeypatch.setattr(brain, "warm_up", lambda: called.append(True))
    assert lex_handler.handler({"aquecer": True}, None) == {"aquecido": True}
    assert called == [True]


def test_ssml_escapes_special_characters():
    assert lex_handler.to_ssml("R$ 600 & mais <x>") == (
        '<speak><prosody rate="92%">R$ 600 &amp; mais &lt;x&gt;</prosody></speak>'
    )


def test_parse_reply_dedupes_benefits():
    reply = brain.parse_reply('{"fala": " Oi ", "beneficios": ["bpc", "bpc", "cadunico"], "encerrar": false}')
    assert reply == brain.Reply(fala="Oi", beneficios=["bpc", "cadunico"], encerrar=False)


def test_respond_sends_history_and_saves_turn(monkeypatch):
    saved = {}
    monkeypatch.setattr(brain, "load_history", lambda s: [{"role": "user", "content": "oi"}, {"role": "assistant", "content": "Olá!"}])

    def fake_ask(history, text, locale):
        assert history[-1]["content"] == "Olá!"
        return brain.Reply(fala="Entendi.", beneficios=["bpc"])

    def fake_save(session_id, locale, history, text, reply, canal):
        saved.update(session=session_id, text=text, reply=reply, n=len(history))

    monkeypatch.setattr(brain, "ask_model", fake_ask)
    monkeypatch.setattr(brain, "save_turn", fake_save)
    reply = brain.respond("s1", "pt_BR", "minha mãe tem 70 anos")
    assert reply.fala == "Entendi."
    assert saved == {"session": "s1", "text": "minha mãe tem 70 anos", "reply": reply, "n": 2}


def test_system_prompt_contains_knowledge():
    assert "Bolsa Família" in brain.SYSTEM_PROMPT
    assert "Disque Social 121" in brain.SYSTEM_PROMPT
