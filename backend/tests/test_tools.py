import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

import brain  # noqa: E402
import tools  # noqa: E402

FAKE_CRAS = (
    {"uf": "SP", "municipio": "Campinas", "nome": "CRAS Satélite Íris", "endereco": "Rua A, 10", "bairro": "Satélite Íris", "cep": "13059000", "telefone": "(19) 3222-0000"},
    {"uf": "SP", "municipio": "Campinas", "nome": "CRAS Vila União", "endereco": "Rua B, 20", "bairro": "Vila União", "cep": "13060000", "telefone": None},
    {"uf": "SP", "municipio": "Campinas", "nome": "CRAS Campo Grande", "endereco": "Rua C, 30", "bairro": "Campo Grande", "cep": "13061000"},
    {"uf": "SP", "municipio": "Campinas", "nome": "CRAS Nova Europa", "endereco": "Rua D, 40", "bairro": "Nova Europa", "cep": "13062000"},
    {"uf": "MG", "municipio": "Bom Jesus", "nome": "CRAS Bom Jesus MG", "endereco": "Rua E", "bairro": "Centro", "cep": "1"},
    {"uf": "RS", "municipio": "Bom Jesus", "nome": "CRAS Bom Jesus RS", "endereco": "Rua F", "bairro": "Centro", "cep": "2"},
)


def use_fake_cras(monkeypatch):
    monkeypatch.setattr(tools, "carregar_cras", lambda: FAKE_CRAS)


def test_cras_prioriza_bairro_sem_acento(monkeypatch):
    use_fake_cras(monkeypatch)
    r = tools.buscar_cras("campinas", "sp", "vila uniao")
    assert r["cras"][0]["nome"] == "CRAS Vila União"
    assert r["total_na_cidade"] == 4
    assert len(r["cras"]) == 3
    assert "telefone" not in r["cras"][0]


def test_cras_tolera_erro_de_digitacao_na_cidade(monkeypatch):
    use_fake_cras(monkeypatch)
    assert tools.buscar_cras("Campinass")["municipio"] == "Campinas"


def test_cras_cidade_homonima_pede_estado(monkeypatch):
    use_fake_cras(monkeypatch)
    r = tools.buscar_cras("Bom Jesus")
    assert r["estados"] == ["MG", "RS"]
    assert tools.buscar_cras("Bom Jesus", "RS")["cras"][0]["nome"] == "CRAS Bom Jesus RS"


def test_cras_cidade_inexistente(monkeypatch):
    use_fake_cras(monkeypatch)
    assert "erro" in tools.buscar_cras("Xyzópolis", "SP")


def test_executar_calculadora_aceita_campos_faltando():
    r = tools.executar("calcular_direitos", {"pessoas": 1, "renda_total_mensal": 300, "idosos_65_mais": 1})
    assert r["beneficios"]["bpc"]["situacao"] == "provavel"
    assert "carteira_idoso" in r["beneficios"]


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(json.loads(json.dumps(kwargs["messages"], default=lambda o: o.__dict__)))
        return self.responses.pop(0)


def block(**kw):
    return SimpleNamespace(**kw)


def test_ask_model_executa_ferramenta_e_devolve_resposta_final(monkeypatch):
    tool_call = SimpleNamespace(stop_reason="tool_use", content=[
        block(type="tool_use", id="t1", name="calcular_direitos", input={"pessoas": 1, "renda_total_mensal": 300, "idosos_65_mais": 1}),
    ])
    final = SimpleNamespace(stop_reason="end_turn", content=[
        block(type="text", text='{"fala": "Ela pode ter o BPC.", "beneficios": ["bpc"], "encerrar": false}'),
    ])
    client = FakeClient([tool_call, final])
    monkeypatch.setattr(brain, "_get_client", lambda: client)

    reply = brain.ask_model([], "minha mãe tem 70 anos e ganha 300", "pt_BR")

    assert reply.fala == "Ela pode ter o BPC."
    assert reply.ferramentas == ["calcular_direitos"]
    tool_result = client.calls[1][-1]["content"][0]
    assert tool_result["tool_use_id"] == "t1"
    assert json.loads(tool_result["content"])["beneficios"]["bpc"]["situacao"] == "provavel"
