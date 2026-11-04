"""Atualiza os dados do site (site/escola.html) com fontes públicas.

Roda no GitHub Actions: a cada 5 minutos durante o pregão e uma vez depois do fechamento.
Cada bloco de dados é independente: se uma fonte falhar, o site mantém o valor anterior.

Fontes: Banco Central (SGS e Focus), Tesouro Transparente e Yahoo Finance.
"""
from __future__ import annotations

import datetime as dt
import io
import json
import re
import sys
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

RAIZ = Path(__file__).resolve().parent.parent
HTML = RAIZ / "site" / "escola.html"
JSON_SAIDA = RAIZ / "site" / "diario.json"
FUSO = ZoneInfo("America/Sao_Paulo")
HDR = {"User-Agent": "Mozilla/5.0 (DiaADiaNoMercado; atualizacao automatica)"}
AGORA = dt.datetime.now(FUSO)
LOG: list[str] = []


def br(v: float, d: int = 2) -> str:
    return f"{v:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def sinal(v: float, d: int = 2) -> str:
    return ("+" if v >= 0 else "−") + br(abs(v), d)


def get(url: str, **kw):
    r = requests.get(url, headers=HDR, timeout=30, **kw)
    r.raise_for_status()
    return r


def js_para_json(txt: str):
    """Converte um array JavaScript simples (aspas simples, true/false) em objeto Python."""
    return json.loads(txt.replace("'", '"'))


# ---------------- Banco Central ----------------
def sgs(serie: int, n: int):
    v = get(f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados/ultimos/{n}?formato=json").json()
    return [(x["data"], float(x["valor"])) for x in v]


def acumulado(valores):
    f = 1.0
    for v in valores:
        f *= 1 + v / 100
    return (f - 1) * 100


def bloco_bc(D: dict):
    selic = sgs(432, 1)[-1][1]
    ipca = sgs(433, 24)
    selic_m = [v for _, v in sgs(4390, 12)]
    cdi_m = [v for _, v in sgs(4391, 12)]
    idx = D.setdefault("indexadores", {})
    idx.update({"data": AGORA.strftime("%d/%m/%Y"), "fonte": "Banco Central (SGS)", "selicMeta": selic,
                "selic12": round(acumulado(selic_m), 2), "cdi12": round(acumulado(cdi_m), 2),
                "ipca12": round(acumulado([v for _, v in ipca[-12:]]), 2), "ipcaRef": ipca[-1][0][3:]})
    m = D.setdefault("macro", {})
    m.setdefault("selic", {})["atual"] = selic
    m["ipcaMensal"] = [[f"{d[6:10]}-{d[3:5]}", v] for d, v in ipca]
    D.setdefault("fontes", {})["indexadores"] = AGORA.strftime("%d/%m/%Y")
    LOG.append(f"Banco Central: Selic {selic}, IPCA 12m {idx['ipca12']}")


def bloco_focus(D: dict):
    base = "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/"
    m = D.setdefault("macro", {})
    for ind, chave in (("IPCA", "ipcaAnual"), ("Selic", "selic")):
        url = (base + "ExpectativasMercadoAnuais?$top=60&$format=json&$orderby=Data%20desc"
               f"&$filter=Indicador%20eq%20'{ind}'%20and%20baseCalculo%20eq%200")
        v = get(url).json()["value"]
        ult = v[0]["Data"]
        anos = {str(x["DataReferencia"]): float(x["Mediana"]) for x in v if x["Data"] == ult}
        m.setdefault(chave, {}).update(anos)
        m["focusData"] = dt.date.fromisoformat(ult).strftime("%d/%m/%Y")
    LOG.append(f"Focus de {m['focusData']}")


# ---------------- Tesouro Direto ----------------
URL_TD = ("https://www.tesourotransparente.gov.br/ckan/dataset/df56aa42-484a-4a59-8184-7676580c81e3/"
          "resource/796d2059-14e9-44e3-80c9-2d9e30b405c1/download/PrecoTaxaTesouroDireto.csv")


def bloco_tesouro(D: dict, td_site: list):
    import pandas as pd
    df = pd.read_csv(io.BytesIO(get(URL_TD).content), sep=";", decimal=",", encoding="latin-1")
    df["Data Base"] = pd.to_datetime(df["Data Base"], dayfirst=True)
    df["Data Vencimento"] = pd.to_datetime(df["Data Vencimento"], dayfirst=True)
    ult = df["Data Base"].max()
    d = df[df["Data Base"] == ult]
    taxas = {}
    for _, r in d.iterrows():
        nome = str(r["Tipo Titulo"]).replace("com Juros Semestrais", "c/ Juros Semestrais").strip()
        taxa = r["Taxa Compra Manha"] if r["Taxa Compra Manha"] else r["Taxa Venda Manha"]
        taxas[(nome.lower(), r["Data Vencimento"].year)] = float(taxa)
    novo, n = [], 0
    for nome, tipo, ano, taxa, sem in td_site:
        base = re.sub(r"\s+\d{4}$", "", nome).replace("RendA+", "Renda+").lower()
        achou = taxas.get((base, ano))
        if achou is None:  # nomes longos, como "Tesouro Renda+ Aposentadoria Extra"
            achou = next((v for (k, a), v in taxas.items() if a == ano and k.startswith(base) and "juros semestrais" not in k), None)
        if achou is not None and (achou > 0 or tipo == "S"):
            taxa, n = achou, n + 1
        novo.append([nome, tipo, ano, taxa, sem])
    m = D.setdefault("macro", {})
    m["td"] = novo
    m["dataTesouro"] = ult.strftime("%d/%m/%Y")
    LOG.append(f"Tesouro de {m['dataTesouro']}: {n} títulos atualizados")


# ---------------- Yahoo Finance ----------------
def historico(tk: str, periodo="5d"):
    import yfinance as yf
    h = yf.Ticker(tk).history(period=periodo, interval="1d")
    return [float(x) for x in h["Close"].dropna().tolist()]


def bloco_precos(D: dict, tickers: list[str]):
    import yfinance as yf
    dados = yf.download([t + ".SA" for t in tickers], period="5d", interval="1d", progress=False, threads=True)["Close"]
    precos = {}
    for t in tickers:
        s = dados[t + ".SA"].dropna() if t + ".SA" in dados else []
        if len(s):
            precos[t] = round(float(s.iloc[-1]), 2)
    if precos:
        D["precos"] = {**D.get("precos", {}), **precos}
    LOG.append(f"Preços de {len(precos)} ações")


def bloco_painel(D: dict, painel_site: list):
    painel = [list(x) for x in painel_site]
    pos = {semac(p[0]): i for i, p in enumerate(painel)}
    def troca(chave, valor, nota):
        i = pos.get(semac(chave))
        if i is not None:
            painel[i][1], painel[i][2] = valor, nota
    try:
        ib = historico("^BVSP")
        troca("Ibovespa", br(ib[-1], 0) + " pts", sinal((ib[-1] / ib[-2] - 1) * 100) + "% no dia")
    except Exception as e:
        LOG.append(f"Ibovespa falhou: {e}")
    try:
        us = historico("BRL=X")
        troca("Dólar", "R$ " + br(us[-1], 3), sinal((us[-1] / us[-2] - 1) * 100) + "% no dia")
    except Exception as e:
        LOG.append(f"Dólar falhou: {e}")
    i = pos.get(semac("DI jan/2029"))
    if i is not None and "subindo" in painel[i][2]:
        painel[i][2] = "referência de 03/11/2026"
    m = D.get("macro", {})
    if m.get("selic", {}).get("atual"):
        troca("Selic", br(m["selic"]["atual"]) + "%", "meta do Copom")
    ano = str(AGORA.year + 1)
    if m.get("ipcaAnual", {}).get(ano):
        troca(f"Focus IPCA {ano}", br(m["ipcaAnual"][ano]) + "%", f"Focus de {m.get('focusData', '')}")
    if m.get("selic", {}).get(ano):
        troca(f"Focus Selic {ano}", br(m["selic"][ano]) + "%", f"Focus de {m.get('focusData', '')}")
    opp = D.setdefault("opp", {})
    opp["painel"] = painel
    opp["data"] = AGORA.strftime("%d/%m/%Y")


def bloco_metais(D: dict):
    met = {}
    for k, tk in (("ouro", "GC=F"), ("prata", "SI=F"), ("cobre", "HG=F")):
        try:
            h = historico(tk, "13mo")
            if len(h) > 30:
                p = h[-1]
                m1 = (p / h[-22] - 1) * 100
                a1 = (p / h[-253] - 1) * 100 if len(h) > 253 else (p / h[0] - 1) * 100
                met[k] = {"p": round(p, 2), "m1": round(m1, 2), "a1": round(a1, 2)}
        except Exception as e:
            LOG.append(f"{k} falhou: {e}")
    if met:
        met["data"] = AGORA.strftime("%d/%m/%Y")
        D["metais"] = {**D.get("metais", {}), **met}
    LOG.append(f"Metais: {', '.join(k for k in met if k != 'data')}")


def semac(s: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


# ---------------- principal ----------------
def main():
    html = HTML.read_text(encoding="utf-8")
    m = re.search(r"DIARIO=(\{.*?\});?\n", html)
    if not m:
        sys.exit("Não achei o DIARIO no site.")
    D = json.loads(m.group(1))
    td_site = js_para_json(re.search(r"\btd:(\[\[.*?\]\])\s*\n\};", html, re.S).group(1))
    painel_site = js_para_json(re.search(r"\bpainel:(\[\[.*?\]\]),\s*\n", html).group(1))
    tickers = re.findall(r"^\s*\['([A-Z]{4}\d{1,2})',", html[html.index("acoes:["):], re.M)

    blocos = [("Banco Central", lambda: bloco_bc(D)), ("Focus", lambda: bloco_focus(D)),
              ("Tesouro", lambda: bloco_tesouro(D, D.get("macro", {}).get("td") or td_site)),
              ("Preços", lambda: bloco_precos(D, tickers)), ("Painel", lambda: bloco_painel(D, D.get("opp", {}).get("painel") or painel_site)),
              ("Metais", lambda: bloco_metais(D))]
    for nome, f in blocos:
        try:
            f()
        except Exception as e:
            LOG.append(f"{nome} falhou: {type(e).__name__}: {e}")

    D["data"] = AGORA.strftime("%d/%m/%Y")
    D["hora"] = AGORA.strftime("%H:%M")
    novo = "DIARIO=" + json.dumps(D, ensure_ascii=False, separators=(",", ":")) + ";\n"
    html = html[:m.start()] + novo + html[m.end():]
    HTML.write_text(html, encoding="utf-8")
    JSON_SAIDA.write_text(json.dumps({"data": D["data"], "hora": D["hora"]}), encoding="utf-8")
    print(f"Atualizado em {D['data']} {D['hora']}")
    print("\n".join(LOG))


if __name__ == "__main__":
    main()
