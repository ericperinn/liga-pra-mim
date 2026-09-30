import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from eligibility import Familia, avaliar  # noqa: E402


def situacoes(resultado):
    return {k: v["situacao"] for k, v in resultado["beneficios"].items()}


def test_idosa_sozinha_com_renda_baixa_tem_bpc_provavel():
    r = avaliar(Familia(pessoas=1, renda_total_mensal=300, idosos_60_mais=1, idosos_65_mais=1))
    s = situacoes(r)
    assert r["renda_por_pessoa"] == 300
    assert s["bpc"] == "provavel"
    assert r["beneficios"]["bpc"]["valor_mensal_estimado"] == 1621
    assert s["bolsa_familia"] == "improvavel"
    assert s["cadunico"] == "provavel"
    assert s["tarifa_social"] == "provavel"
    assert s["carteira_idoso"] == "possivel"


def test_bolsa_familia_soma_adicionais_por_crianca():
    r = avaliar(Familia(pessoas=4, renda_total_mensal=600, criancas_0_6=1, criancas_7_17=1))
    bf = r["beneficios"]["bolsa_familia"]
    assert bf["situacao"] == "provavel"
    assert bf["valor_mensal_estimado"] == 600 + 150 + 50


def test_bolsa_familia_familia_grande_usa_142_por_pessoa():
    r = avaliar(Familia(pessoas=6, renda_total_mensal=0))
    assert r["beneficios"]["bolsa_familia"]["valor_mensal_estimado"] == 6 * 142


def test_linha_do_bolsa_familia_e_inclusiva():
    assert situacoes(avaliar(Familia(pessoas=2, renda_total_mensal=436)))["bolsa_familia"] == "provavel"
    assert situacoes(avaliar(Familia(pessoas=2, renda_total_mensal=438)))["bolsa_familia"] == "improvavel"


def test_bpc_entre_um_quarto_e_meio_salario_e_possivel():
    r = avaliar(Familia(pessoas=2, renda_total_mensal=1000, pessoas_com_deficiencia=1))
    assert situacoes(r)["bpc"] == "possivel"


def test_sem_idoso_nem_deficiencia_nao_menciona_bpc():
    assert "bpc" not in avaliar(Familia(pessoas=3, renda_total_mensal=300))["beneficios"]


def test_renda_media_tem_desconto_menor_de_luz_e_sem_cadunico():
    s = situacoes(avaliar(Familia(pessoas=1, renda_total_mensal=1000)))
    assert s["tarifa_social"] == "possivel"
    assert s["cadunico"] == "improvavel"


def test_pe_de_meia_por_estudante():
    r = avaliar(Familia(pessoas=3, renda_total_mensal=900, estudantes_ensino_medio_publico=2))
    assert r["beneficios"]["pe_de_meia"]["valor_mensal_estimado"] == 400


def test_ja_tem_cadunico_orienta_atualizar():
    cad = avaliar(Familia(pessoas=2, renda_total_mensal=200, tem_cadunico=True))["beneficios"]["cadunico"]
    assert cad["situacao"] == "ja_tem"
    assert "Atualizar" in cad["proximo_passo"]


def test_farmacia_popular_sempre_disponivel():
    assert situacoes(avaliar(Familia(pessoas=1, renda_total_mensal=10000)))["farmacia_popular"] == "disponivel"


def test_familia_sem_pessoas_e_invalida():
    with pytest.raises(ValueError):
        avaliar(Familia(pessoas=0, renda_total_mensal=100))


def test_aposentadoria_de_1_sm_do_idoso_nao_conta_para_bpc_do_conjuge():
    casal = Familia(pessoas=2, renda_total_mensal=1621, idosos_60_mais=2, idosos_65_mais=2)
    assert avaliar(casal)["beneficios"]["bpc"]["situacao"] == "possivel"
    casal.beneficio_ate_1_sm_de_idoso_ou_pcd = 1621
    assert avaliar(casal)["beneficios"]["bpc"]["situacao"] == "provavel"


def test_exclusao_do_bpc_limitada_a_um_salario_minimo():
    # Only 1621 of the declared 5000 is excluded: (5000 - 1621) / 2 is above half a minimum wage.
    f = Familia(pessoas=2, renda_total_mensal=5000, idosos_65_mais=1, beneficio_ate_1_sm_de_idoso_ou_pcd=5000)
    assert avaliar(f)["beneficios"]["bpc"]["situacao"] == "improvavel"


def test_idoso_abaixo_de_65_recebe_explicacao_da_idade_do_bpc():
    bpc = avaliar(Familia(pessoas=1, renda_total_mensal=100, idosos_60_mais=1))["beneficios"]["bpc"]
    assert bpc["situacao"] == "improvavel"
    assert "65" in bpc["motivo"]
