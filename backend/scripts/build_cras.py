"""Gera backend/app/data/cras.json.gz a partir do Censo SUAS (MDS), bloco CRAS - Dados Gerais.

Uso:  python backend/scripts/build_cras.py [caminho/para/1 - CRAS.rar]
Sem argumento, baixa SOURCE_URL. A extração do .rar usa o `tar` do sistema (bsdtar/libarchive,
que no Windows 10+ já vem instalado).
"""
import csv
import gzip
import io
import json
import math
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

SOURCE_URL = "https://aplicacoes.mds.gov.br/sagi/dicivip_datain/ckfinder/userfiles/files/1%20-%20CRAS(3).rar"
REFERENCE = "Censo SUAS 2023 - CRAS - Dados Gerais (MDS/SNAS, divulgação atualizada em 19/04/2024)"
CSV_MEMBER = "1 - CRAS/Censo_SUAS_2023_CRAS_Dados_Gerais.csv"
OUTPUT = Path(__file__).resolve().parents[1] / "app" / "data" / "cras.json.gz"
# Municipality seat coordinates keyed by IBGE code; used only to pick the right decimal position.
SEATS_URL = "https://raw.githubusercontent.com/kelvins/municipios-brasileiros/main/csv/municipios.csv"
MAX_KM_FROM_SEAT = 150

# The published CSV lost the decimal point in latitude/longitude ("-234.992.512" is -23.4992512).
# Each value is rebuilt by trying decimal positions: candidates must fall inside the state's box,
# and the pair closest to the municipality seat wins (near the equator -3.1 and -0.31 both fit AM).
UF_BOX = {  # lat_min, lat_max, lon_min, lon_max
    "AC": (-11.2, -7.1, -74.0, -66.6), "AL": (-10.5, -8.8, -38.3, -35.1), "AP": (-1.3, 4.5, -54.9, -49.8),
    "AM": (-9.9, 2.3, -73.8, -56.1), "BA": (-18.4, -8.5, -46.7, -37.3), "CE": (-7.9, -2.7, -41.5, -37.2),
    "DF": (-16.1, -15.5, -48.3, -47.3), "ES": (-21.4, -17.8, -41.9, -39.6), "GO": (-19.5, -12.4, -53.3, -45.9),
    "MA": (-10.3, -1.0, -48.8, -41.8), "MT": (-18.1, -7.3, -61.7, -50.2), "MS": (-24.1, -17.1, -58.2, -50.9),
    "MG": (-22.95, -14.2, -51.1, -39.8), "PA": (-9.9, 2.6, -58.9, -46.0), "PB": (-8.3, -6.0, -38.8, -34.8),
    "PR": (-26.8, -22.5, -54.7, -48.0), "PE": (-9.5, -3.8, -41.4, -32.3), "PI": (-10.95, -2.7, -45.99, -40.3),
    "RJ": (-23.4, -20.7, -44.9, -40.9), "RN": (-6.99, -4.8, -38.6, -34.9), "RS": (-33.8, -27.0, -57.7, -49.6),
    "RO": (-13.7, -7.9, -66.9, -59.7), "RR": (-1.6, 5.3, -64.9, -58.8), "SC": (-29.4, -25.9, -53.9, -48.3),
    "SP": (-25.4, -19.7, -53.2, -44.1), "SE": (-11.6, -9.5, -38.3, -36.4), "TO": (-13.5, -5.1, -50.8, -45.6),
}
MARGIN = 0.3

SMALL_WORDS = {"de", "da", "do", "das", "dos", "e", "em", "na", "no", "nas", "nos", "a", "o", "com"}
UPPER_WORDS = {"CRAS", "II", "III", "IV", "VI", "VII", "VIII", "IX", "XI", "XII", "SN", "BR", "UBS", "CEU"}
STREET_TYPES = {"rua", "avenida", "travessa", "praça", "rodovia", "estrada", "alameda", "largo", "quadra", "via"}


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip()


def title(value: str) -> str:
    words = clean(value).split(" ")
    out = []
    for i, w in enumerate(words):
        if not w:
            continue
        bare = re.sub(r"[^\wÀ-ÿ]", "", w)
        if bare.upper() in UPPER_WORDS:
            out.append(w.upper())
        elif i > 0 and w.lower() in SMALL_WORDS:
            out.append(w.lower())
        else:
            out.append(w[:1].upper() + w[1:].lower())
    return " ".join(out)


def coord_candidates(raw: str, lo: float, hi: float) -> list[float]:
    raw = clean(raw).replace(",", ".")
    if not raw:
        return []
    if raw.count(".") <= 1:
        try:
            v = float(raw)
        except ValueError:
            return []
        return [v] if lo - MARGIN <= v <= hi + MARGIN else []
    sign = -1.0 if raw.startswith("-") else 1.0
    digits = re.sub(r"\D", "", raw)
    out = []
    for k in (0, 1, 2):
        if k > len(digits):
            continue
        v = sign * float(f"{digits[:k] or '0'}.{digits[k:] or '0'}")
        if lo - MARGIN <= v <= hi + MARGIN:
            out.append(v)
    return out


def km(a: tuple[float, float], b: tuple[float, float]) -> float:
    dlat = (a[0] - b[0]) * 111.0
    dlon = (a[1] - b[1]) * 111.0 * math.cos(math.radians((a[0] + b[0]) / 2))
    return math.hypot(dlat, dlon)


def fix_point(raw_lat: str, raw_lon: str, box, seat) -> tuple[float | None, float | None]:
    lats = coord_candidates(raw_lat, box[0], box[1])
    lons = coord_candidates(raw_lon, box[2], box[3])
    pairs = [(la, lo) for la in lats for lo in lons]
    if not pairs:
        return None, None
    if seat is None:
        return (round(pairs[0][0], 6), round(pairs[0][1], 6)) if len(pairs) == 1 else (None, None)
    best = min(pairs, key=lambda p: km(p, seat))
    if km(best, seat) > MAX_KM_FROM_SEAT:
        return None, None
    return round(best[0], 6), round(best[1], 6)


def load_seats() -> dict[str, tuple[float, float]]:
    try:
        req = urllib.request.Request(SEATS_URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            text = resp.read().decode("utf-8")
    except OSError as e:
        print(f"aviso: sem tabela de sedes ({e}); usando só as caixas por UF")
        return {}
    return {
        r["codigo_ibge"][:6]: (float(r["latitude"]), float(r["longitude"]))
        for r in csv.DictReader(io.StringIO(text))
    }


def phone(raw: str) -> str | None:
    d = re.sub(r"\D", "", raw or "").lstrip("0")
    if len(d) == 10:
        return f"({d[:2]}) {d[2:6]}-{d[6:]}"
    if len(d) == 11:
        return f"({d[:2]}) {d[2:7]}-{d[7:]}"
    return d or None


def address(tipo: str, logradouro: str, numero: str, complemento: str) -> str:
    rua = title(logradouro)
    tipo = title(tipo)
    if tipo and rua.lower().split(" ")[0] not in STREET_TYPES and tipo.lower() != "outros":
        rua = f"{tipo} {rua}"
    numero = clean(numero)
    parts = [rua]
    if numero and numero not in {"0", "00", "000"} and numero.upper() not in {"SN", "S/N"}:
        parts[0] += f", {numero}"
    else:
        parts[0] += ", sem número"
    comp = title(complemento)
    if comp:
        parts.append(comp)
    return " - ".join(parts)


def horario(dias: str, horas: str) -> str | None:
    dias, horas = clean(dias), clean(horas)
    return ", ".join(x for x in (dias, horas) if x) or None


def load_rows(rar_path: Path) -> list[dict]:
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["tar", "-xf", str(rar_path), "-C", tmp, CSV_MEMBER], check=True)
        with open(Path(tmp) / CSV_MEMBER, encoding="latin-1", newline="") as f:
            return list(csv.DictReader(f, delimiter=";"))


def convert(rows: list[dict], seats: dict[str, tuple[float, float]]) -> list[dict]:
    out = []
    for r in rows:
        uf = clean(r["q010"]).upper()
        box = UF_BOX.get(uf)
        seat = seats.get(clean(r["IBGE"])[:6])
        lat, lon = fix_point(r["latitude"], r["longitude"], box, seat) if box else (None, None)
        cep = re.sub(r"\D", "", r["q08"] or "")
        out.append({
            "id": clean(r["NU_IDENTIFICADOR"]),
            "ibge": clean(r["IBGE"]),
            "uf": uf,
            "municipio": title(r["q09"]),
            "nome": title(r["q01"]),
            "endereco": address(r["q02"], r["q03"], r["q04"], r["q05"]),
            "bairro": title(r["q06"]) or None,
            "referencia": clean(r["q07"]) or None,
            "cep": cep.zfill(8) if cep else None,
            "telefone": phone(r["q012"]),
            "horario": horario(r["q2_1"], r["q2_2"]),
            "lat": lat,
            "lon": lon,
        })
    out.sort(key=lambda c: (c["uf"], c["municipio"], c["nome"]))
    return out


def main() -> None:
    if len(sys.argv) > 1:
        rar = Path(sys.argv[1])
    else:
        rar = Path(tempfile.gettempdir()) / "censo_suas_cras.rar"
        if not rar.exists():
            req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=300) as resp:
                rar.write_bytes(resp.read())
    data = convert(load_rows(rar), load_seats())
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(OUTPUT, "wt", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, separators=(",", ":"))
    n = len(data)
    geo = sum(1 for c in data if c["lat"] is not None)
    tel = sum(1 for c in data if c["telefone"])
    hor = sum(1 for c in data if c["horario"])
    print(f"{REFERENCE}\n{n} CRAS -> {OUTPUT} ({OUTPUT.stat().st_size / 1024:.0f} KB)")
    print(f"lat/lon: {geo} ({geo / n:.1%})  telefone: {tel} ({tel / n:.1%})  horario: {hor} ({hor / n:.1%})")


if __name__ == "__main__":
    main()
