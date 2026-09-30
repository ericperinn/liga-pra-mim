"""Deterministic benefit screening: the model gathers facts in conversation, this code applies the rules."""

from dataclasses import dataclass

SALARIO_MINIMO = 1621.00
LINHA_BOLSA_FAMILIA = 218.00
BF_RENDA_CIDADANIA_POR_PESSOA = 142.00
BF_MINIMO_FAMILIA = 600.00
BF_PRIMEIRA_INFANCIA = 150.00
BF_VARIAVEL = 50.00


@dataclass
class Familia:
    pessoas: int
    renda_total_mensal: float
    idosos_60_mais: int = 0
    idosos_65_mais: int = 0
    pessoas_com_deficiencia: int = 0
    criancas_0_6: int = 0
    criancas_7_17: int = 0
    gestantes_ou_amamentando: int = 0
    estudantes_ensino_medio_publico: int = 0
    tem_cadunico: bool | None = None


def _resultado(situacao: str, motivo: str, valor_mensal: float | None = None, proximo_passo: str = "") -> dict:
    r = {"situacao": situacao, "motivo": motivo, "proximo_passo": proximo_passo}
    if valor_mensal is not None:
        r["valor_mensal_estimado"] = round(valor_mensal, 2)
    return r


def valor_bolsa_familia(f: Familia) -> float:
    base = max(BF_MINIMO_FAMILIA, BF_RENDA_CIDADANIA_POR_PESSOA * f.pessoas)
    return (
        base
        + BF_PRIMEIRA_INFANCIA * f.criancas_0_6
        + BF_VARIAVEL * (f.criancas_7_17 + f.gestantes_ou_amamentando)
    )


def avaliar(f: Familia) -> dict:
    if f.pessoas < 1:
        raise ValueError("a família precisa ter pelo menos 1 pessoa")
    renda = max(0.0, f.renda_total_mensal)
    per_capita = renda / f.pessoas
    quarto_sm, meio_sm = SALARIO_MINIMO / 4, SALARIO_MINIMO / 2
    cad_passo = (
        "Atualizar o Cadastro Único no CRAS, se tiver mais de dois anos."
        if f.tem_cadunico
        else "Fazer o Cadastro Único no CRAS, levando CPF ou título de eleitor."
    )
    beneficios: dict[str, dict] = {}

    if per_capita <= meio_sm:
        beneficios["cadunico"] = _resultado(
            "ja_tem" if f.tem_cadunico else "provavel",
            f"renda de {per_capita:.2f} reais por pessoa, até meio salário mínimo",
            proximo_passo=cad_passo,
        )
    else:
        beneficios["cadunico"] = _resultado(
            "improvavel", f"renda de {per_capita:.2f} reais por pessoa, acima de meio salário mínimo"
        )

    if per_capita <= LINHA_BOLSA_FAMILIA:
        beneficios["bolsa_familia"] = _resultado(
            "provavel",
            f"renda de {per_capita:.2f} reais por pessoa, até {LINHA_BOLSA_FAMILIA:.0f}",
            valor_bolsa_familia(f),
            "A seleção é automática depois do Cadastro Único. Acompanhar pelo app Bolsa Família ou no 121.",
        )
    else:
        beneficios["bolsa_familia"] = _resultado(
            "improvavel", f"renda de {per_capita:.2f} reais por pessoa, acima de {LINHA_BOLSA_FAMILIA:.0f}"
        )

    tem_publico_bpc = f.idosos_65_mais > 0 or f.pessoas_com_deficiencia > 0
    if tem_publico_bpc and per_capita <= quarto_sm:
        beneficios["bpc"] = _resultado(
            "provavel",
            "tem idoso de 65 anos ou mais ou pessoa com deficiência, e renda até um quarto do salário mínimo por pessoa",
            SALARIO_MINIMO,
            f"{cad_passo} Depois pedir o BPC no INSS pelo 135 ou pelo Meu INSS. Precisa de biometria e CPF de todos.",
        )
    elif tem_publico_bpc and per_capita <= meio_sm:
        beneficios["bpc"] = _resultado(
            "possivel",
            "renda um pouco acima de um quarto do salário mínimo; gastos com remédios e fraldas podem ser descontados e o INSS avalia",
            SALARIO_MINIMO,
            "Pedir mesmo assim no INSS pelo 135, levando comprovantes de gastos com saúde.",
        )
    elif tem_publico_bpc:
        beneficios["bpc"] = _resultado("improvavel", "renda por pessoa acima de meio salário mínimo")

    if per_capita <= meio_sm:
        beneficios["tarifa_social"] = _resultado(
            "provavel",
            "renda até meio salário mínimo por pessoa",
            proximo_passo="Com o Cadastro Único, a luz fica grátis até 80 kWh por mês. Se não aparecer na conta, ligar para a companhia de energia.",
        )
    elif per_capita <= SALARIO_MINIMO:
        beneficios["tarifa_social"] = _resultado(
            "possivel",
            "renda entre meio e um salário mínimo por pessoa: desconto menor até 120 kWh",
            proximo_passo="Estar no Cadastro Único e conferir o desconto na conta de luz.",
        )

    if f.estudantes_ensino_medio_publico > 0:
        if per_capita <= meio_sm:
            beneficios["pe_de_meia"] = _resultado(
                "provavel",
                "estudante do ensino médio público em família de baixa renda",
                200.0 * f.estudantes_ensino_medio_publico,
                "É automático com o Cadastro Único. Ir a pelo menos 80% das aulas. Dúvidas na escola.",
            )
        else:
            beneficios["pe_de_meia"] = _resultado("improvavel", "renda por pessoa acima de meio salário mínimo")

    if f.idosos_60_mais > 0 and per_capita <= 2 * SALARIO_MINIMO:
        beneficios["carteira_idoso"] = _resultado(
            "possivel",
            "idoso de 60 anos ou mais; a regra olha a renda individual dele, até dois salários mínimos",
            proximo_passo="Pedir a Carteira da Pessoa Idosa no CRAS, com o Cadastro Único atualizado.",
        )

    beneficios["farmacia_popular"] = _resultado(
        "disponivel",
        "todos os itens do programa são gratuitos para qualquer pessoa com receita",
        proximo_passo="Levar receita e documento com foto e CPF a uma farmácia com a placa Aqui tem Farmácia Popular.",
    )

    return {"renda_por_pessoa": round(per_capita, 2), "salario_minimo": SALARIO_MINIMO, "beneficios": beneficios}
