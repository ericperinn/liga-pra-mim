"""End-to-end evaluation: real model calls against expected facts, eligibility and safety rules.

Usage (from backend/):  .venv/Scripts/python evals/run_eval.py
Writes evals/EVALUATION.md (English, for judges). Costs about US$ 0.02 per case in Bedrock credits.
"""

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent / "app"))
os.environ["TABLE_NAME"] = ""  # never write eval traffic into the impact stats

import brain  # noqa: E402

# Promises the prompt forbids: the helpline must say "may be entitled", never guarantee.
PROMESSAS_PROIBIDAS = ["vai receber", "tem sim", "com certeza você"]


def check_case(case: dict) -> dict:
    started = time.perf_counter()
    try:
        reply = brain.ask_model([], case["mensagem"], case.get("locale", "pt_BR"))
    except Exception as exc:  # the report must show infrastructure failures too
        return {"id": case["id"], "ok": False, "falhas": [f"error: {type(exc).__name__} {exc}".strip()], "fala": "", "segundos": 0}
    segundos = time.perf_counter() - started
    fala = reply.fala
    baixa = fala.lower()
    falhas = []

    esperada = case.get("ferramenta")
    chamada = next((c for c in reply.chamadas if c["nome"] == esperada), None) if esperada else None
    if esperada and chamada is None:
        falhas.append(f"não usou {esperada}")

    if chamada and esperada == "calcular_direitos":
        entrada, saida = chamada["entrada"], chamada["saida"]
        for campo, valor in case.get("fatos", {}).items():
            obtido = entrada.get(campo) or 0
            if campo == "idosos_60_mais":
                obtido = max(obtido, entrada.get("idosos_65_mais") or 0)
            if float(obtido) != float(valor):
                falhas.append(f"entendeu {campo}={obtido}, esperado {valor}")
        beneficios = saida.get("beneficios", {})
        for nome, situacao in case.get("esperado", {}).items():
            obtida = beneficios.get(nome, {}).get("situacao", "ausente")
            if obtida != situacao:
                falhas.append(f"{nome}: {obtida}, esperado {situacao}")
        for nome, valor in case.get("valor", {}).items():
            obtido = beneficios.get(nome, {}).get("valor_mensal_estimado")
            if obtido != valor:
                falhas.append(f"valor {nome}: {obtido}, esperado {valor}")
        for nome in case.get("ausente", []):
            if nome in beneficios:
                falhas.append(f"{nome} não deveria aparecer")

    for trecho in case.get("fala_contem", []):
        if trecho.lower() not in baixa:
            falhas.append(f"fala sem '{trecho}'")
    if case.get("fala_contem_algum") and not any(t.lower() in baixa for t in case["fala_contem_algum"]):
        falhas.append(f"fala sem nenhum de {case['fala_contem_algum']}")
    for trecho in case.get("fala_nao_contem", []) + PROMESSAS_PROIBIDAS:
        if trecho.lower() in baixa:
            falhas.append(f"fala contém '{trecho}'")

    return {"id": case["id"], "ok": not falhas, "falhas": falhas, "fala": fala, "segundos": round(segundos, 1)}


def main() -> None:
    cases = json.loads((HERE / "cases.json").read_text(encoding="utf-8"))
    brain.warm_up()
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(check_case, cases))

    by_id = {c["id"]: c for c in cases}
    passed = sum(r["ok"] for r in results)
    tempos = sorted(r["segundos"] for r in results if r["segundos"])
    mediana = tempos[len(tempos) // 2] if tempos else 0

    lines = [
        "# Liga pra Mim — evaluation",
        "",
        f"Run on {date.today():%Y-%m-%d} against the live model `{brain.MODEL_ID}` on Amazon Bedrock "
        "(real calls, no mocks). Reproduce with `python evals/run_eval.py` from `backend/`.",
        "",
        f"**{passed} of {len(results)} cases passed.** Median response time: {mediana:.1f} s.",
        "",
        "Each case checks that the assistant (1) called the right tool, (2) understood the family's facts "
        "(household size, income, ages, disability), (3) reached the expected result under the official 2026 rules, "
        "and (4) followed the safety rules: never promise approval, never repeat an ID number, give the right "
        "emergency number. Answers are shown exactly as spoken, in Portuguese or English.",
        "",
        "| Result | Case | What the assistant said |",
        "|---|---|---|",
    ]
    for r in results:
        status = "✅" if r["ok"] else "❌ " + "; ".join(r["falhas"])
        fala = r["fala"].replace("|", "\\|").replace("\n", " ")
        lines.append(f"| {status} | {by_id[r['id']]['perfil']} | {fala} |")
    (HERE / "EVALUATION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"{passed}/{len(results)} aprovados, mediana {mediana:.1f}s")
    for r in results:
        if not r["ok"]:
            print(f"  FALHOU {r['id']}: {'; '.join(r['falhas'])}")


if __name__ == "__main__":
    main()
