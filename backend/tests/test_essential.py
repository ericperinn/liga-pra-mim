import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import brain  # noqa: E402
import essential  # noqa: E402
import tools  # noqa: E402

FAKE_CRAS = (
    {"uf": "PI", "municipio": "Altos", "nome": "CRAS II", "endereco": "Rua Colorado, 2000", "bairro": "Santa Inês",
     "referencia": "Próximo à Igreja São Raimundo Nonato", "telefone": "(86) 9944-9017", "horario": "5 dias por semana"},
    {"uf": "PI", "municipio": "Altos", "nome": "CRAS I", "endereco": "Rua A, 1", "bairro": "Centro"},
    {"uf": "SP", "municipio": "São Paulo", "nome": "CRAS Anhanguera", "endereco": "Av. Piero Tricca, 27", "bairro": "Jardim Santa Fé"},
)


@pytest.fixture(autouse=True)
def fresh(monkeypatch):
    essential._memory.clear()
    monkeypatch.setattr(tools, "carregar_cras", lambda: FAKE_CRAS)
    brain._llm_down_until = 0.0


@pytest.mark.parametrize("text,expected", [
    ("3", 3), ("somos três", 3), ("trezentos e cinquenta reais", 350), ("uns 1.500 por mês", 1500),
    ("dois mil e quinhentos", 2500), ("mil e duzentos", 1200), ("R$ 350,00", 350), ("moro sozinha", 1),
    ("nenhuma", 0), ("zero", 0), ("three hundred and fifty", 350), ("two thousand", 2), ("abc", None),
])
def test_parse_number(text, expected):
    if text == "two thousand":
        expected = 2000
    assert essential.parse_number(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("sim", True), ("tem sim", True), ("não", False), ("não tem ninguém", False), ("yes", True), ("no", False), ("hum", None),
])
def test_parse_yes_no(text, expected):
    assert essential.parse_yes_no(text) == expected


def test_find_location_with_state_and_neighborhood():
    city, uf, rest = essential.find_location("Moro em Altos, no Piauí, no bairro Santa Inês")
    assert (city, uf) == ("altos", "PI")
    assert "santa ines" in rest


def talk(session, *answers, locale="pt_BR"):
    return [essential.respond(session, locale, a) for a in answers]


def test_full_conversation_finds_bpc_and_cras():
    turns = talk("s1", "oi preciso de ajuda", "só eu", "trezentos reais", "sim", "não", "zero", "zero",
                 "Altos, Piauí, bairro Santa Inês", "não, obrigada")
    assert "Quantas pessoas" in turns[0]["fala"]
    result = turns[6]
    assert "o BPC, 1621 reais por mês" in result["fala"]
    assert "CPF ou título de eleitor" in result["fala"]
    assert "bpc" in result["beneficios"] and "calcular_direitos" in result["ferramentas"]
    cras = turns[7]
    assert "Rua Colorado, 2000" in cras["fala"] and "8 6, 9 9 4 4, 9 0 1 7" in cras["fala"]
    assert "buscar_cras" in cras["ferramentas"]
    assert turns[8]["encerrar"] is True


def test_minimum_wage_income_phrase():
    turns = talk("s2", "oi", "dois", "um salário mínimo", "sim", "não", "0", "0")
    assert "talvez o BPC" in turns[-1]["fala"]


def test_unclear_answer_repeats_question_without_advancing():
    turns = talk("s3", "oi", "não sei")
    assert "Diga só o número" in turns[1]["fala"] and "Quantas pessoas" in turns[1]["fala"]


def test_asking_for_cras_skips_questionnaire():
    out = essential.respond("s4", "pt_BR", "Onde fica o CRAS em São Paulo, Jardim Santa Fé?")
    assert "CRAS Anhanguera" in out["fala"]


def test_emergency_is_answered_first():
    out = essential.respond("s5", "pt_BR", "meu marido me bate")
    assert out["fala"].startswith("Se você está em perigo") and "180" in out["fala"]


def test_english_flow():
    turns = talk("s6", "hello", "three", "zero", "no", "no", "two", "one", locale="en_US")
    assert "How many people" in turns[0]["fala"]
    assert "Bolsa Família, 950 reais a month" in turns[-1]["fala"]


def test_unknown_city_asks_again():
    turns = talk("s7", "onde fica o cras", "Xyzópolis")
    assert "Não encontrei essa cidade" in turns[1]["fala"]


def test_brain_falls_back_to_essential_and_cools_down(monkeypatch):
    calls = []

    class Suspended(Exception):
        status_code = 400

    def broken(*a):
        calls.append(1)
        raise Suspended("Access to Bedrock models is not allowed")

    monkeypatch.setattr(brain, "ask_model", broken)
    monkeypatch.setattr(brain, "load_history", lambda s: [])
    monkeypatch.setattr(brain, "save_turn", lambda *a: None)

    first = brain.respond("s8", "pt_BR", "oi")
    assert "Quantas pessoas" in first.fala
    assert not brain.llm_available()
    other_caller = brain.respond("s9", "pt_BR", "oi")
    assert "Quantas pessoas" in other_caller.fala
    assert len(calls) == 1
