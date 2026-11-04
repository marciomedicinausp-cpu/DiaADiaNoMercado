"""Busca de dados ao vivo, com reserva (snapshot) quando uma fonte não responde.

Fontes:
- Opções: opcoes.net.br (lista completa de opções por ativo, JSON público)
- Preço e fundamentos das ações: Yahoo Finance (biblioteca yfinance)
- Tesouro Direto: Tesouro Transparente (CSV oficial de preços e taxas)
- Boletim Focus: API de expectativas do Banco Central (Olinda)
- IPCA e Selic: SGS do Banco Central
"""
from __future__ import annotations
import datetime as dt
import io
import json
import re
from pathlib import Path

import pandas as pd
import requests
import streamlit as st

PASTA = Path(__file__).parent
SNAP = json.loads((PASTA / "snapshot.json").read_text(encoding="utf-8"))
HDR = {"User-Agent": "Mozilla/5.0 (EscolaTitulosOpcoes)", "Accept": "application/json,text/csv,*/*"}
TIMEOUT = 20

ATIVOS = list(SNAP["opcoes"].keys())
MESES_CALL = "ABCDEFGHIJKL"
MESES_PUT = "MNOPQRSTUVWX"


def _get(url, **kw):
    r = requests.get(url, headers=HDR, timeout=TIMEOUT, **kw)
    r.raise_for_status()
    return r


def terceira_sexta(ano: int, mes: int) -> dt.date:
    d = dt.date(ano, mes, 15)
    while d.weekday() != 4:
        d += dt.timedelta(days=1)
    return d


def proximos_vencimentos(hoje: dt.date | None = None, n=2):
    hoje = hoje or dt.date.today()
    out, a, m = [], hoje.year, hoje.month
    while len(out) < n:
        v = terceira_sexta(a, m)
        if v >= hoje:
            out.append(v)
        m += 1
        if m > 12:
            m, a = 1, a + 1
    return out


def dias_uteis(a: dt.date, b: dt.date) -> int:
    return max(1, int(pd.bdate_range(a, b).size) - 1)


# ---------------- preço das ações ----------------
@st.cache_data(ttl=900, show_spinner=False)
def preco(ativo: str):
    """Retorna (preço, origem)."""
    try:
        import yfinance as yf
        h = yf.Ticker(ativo + ".SA").history(period="5d")
        if len(h):
            return float(h["Close"].iloc[-1]), "ao vivo (Yahoo Finance)"
    except Exception:
        pass
    o = SNAP["opcoes"].get(ativo)
    return (o["spot"], f"reserva de {SNAP['data']}") if o else (None, "indisponível")


@st.cache_data(ttl=3600 * 6, show_spinner=False)
def fundamentos(ativo: str):
    try:
        import yfinance as yf
        i = yf.Ticker(ativo + ".SA").info
        roe = i.get("returnOnEquity")
        dy = i.get("dividendYield")
        if dy and dy > 1:  # algumas versões já devolvem em %
            dy = dy / 100
        return {"pl": i.get("trailingPE"), "pvp": i.get("priceToBook"), "roe": roe * 100 if roe else None,
                "dy": dy * 100 if dy else None, "divpl": (i.get("debtToEquity") or 0) / 100 or None, "origem": "ao vivo"}
    except Exception:
        return None


# ---------------- opções ----------------
def _parse_opcoes(js: dict):
    data = js.get("data", js)
    cols = data.get("columns") or []
    rows = data.get("cotacoesOpcoes") or []
    tit = [(c.get("title") or c.get("name") or "").lower() for c in cols]

    def idx(*keys, default=None):
        for k in keys:
            for i, t in enumerate(tit):
                if k in t:
                    return i
        return default

    i_tk, i_tipo, i_k, i_ult, i_neg, i_data = idx("ticker", default=0), idx("tipo", default=2), idx("strike", default=5), \
        idx("último", "ultimo", default=8), idx("negócios", "negocios", default=9), idx("data", default=11)
    calls, puts = [], []
    for r in rows:
        try:
            tk = str(r[i_tk]).split("_")[0]
            tipo = str(r[i_tipo]).upper()
            K = float(r[i_k])
            p = r[i_ult]
            if p is None:
                continue
            p = float(p)
            neg = r[i_neg] if i_neg is not None and i_neg < len(r) else None
            linha = [tk, K, p, neg, str(r[i_data])[:10] if i_data is not None and i_data < len(r) else ""]
            (calls if tipo.startswith("C") else puts).append(linha)
        except Exception:
            continue
    return calls, puts


def _limpa(linhas, S, tipo):
    ok = []
    for tk, K, p, *resto in linhas:
        intr = max(S - K, 0) if tipo == "C" else max(K - S, 0)
        if p > 0 and intr - 0.02 <= p <= intr + 0.08 * S and 0.75 * S <= K <= 1.3 * S:
            ok.append([tk, K, p] + resto)
    return sorted(ok, key=lambda r: r[1])


@st.cache_data(ttl=900, show_spinner=False)
def opcoes(ativo: str):
    """Retorna dict com spot, vencimento, du, calls, puts, origem."""
    S, origem_preco = preco(ativo)
    for venc in proximos_vencimentos():
        for d in (venc, venc - dt.timedelta(days=1)):  # vencimento antecipado em feriado
            try:
                url = ("https://opcoes.net.br/listaopcoes/completa?idAcao=" + ativo +
                       "&listarVencimentos=false&cotacoes=true&vencimentos=" + d.isoformat())
                calls, puts = _parse_opcoes(_get(url).json())
                if S and (calls or puts):
                    c, p = _limpa(calls, S, "C"), _limpa(puts, S, "P")
                    if c or p:
                        return {"spot": S, "venc": d.strftime("%d/%m/%Y"), "du": dias_uteis(dt.date.today(), d),
                                "calls": c, "puts": p, "origem": f"ao vivo (opcoes.net.br; preço {origem_preco})"}
            except Exception:
                continue
    o = SNAP["opcoes"][ativo]
    return {"spot": o["spot"], "venc": o["venc"], "du": o["du"], "calls": o["C"], "puts": o["P"],
            "origem": f"reserva: OpLab, fechamento de {SNAP['data']}"}


# ---------------- Tesouro Direto ----------------
URL_TD = ("https://www.tesourotransparente.gov.br/ckan/dataset/df56aa42-484a-4a59-8184-7676580c81e3/"
          "resource/796d2059-14e9-44e3-80c9-2d9e30b405c1/download/PrecoTaxaTesouroDireto.csv")


@st.cache_data(ttl=3600 * 4, show_spinner=False)
def tesouro():
    try:
        df = pd.read_csv(io.BytesIO(_get(URL_TD).content), sep=";", decimal=",", encoding="latin-1")
        df["Data Base"] = pd.to_datetime(df["Data Base"], dayfirst=True)
        df["Data Vencimento"] = pd.to_datetime(df["Data Vencimento"], dayfirst=True)
        ult = df["Data Base"].max()
        d = df[df["Data Base"] == ult]
        d = d[d["Data Vencimento"] > ult]
        out = []
        for _, r in d.iterrows():
            tipo = r["Tipo Titulo"]
            k = "S" if "Selic" in tipo else "P" if "Prefixado" in tipo else "I"
            out.append({"titulo": f"{tipo} {r['Data Vencimento'].year}", "tipo": k, "venc": r["Data Vencimento"].date().isoformat(),
                        "taxa": float(r["Taxa Compra Manha"]) if r["Taxa Compra Manha"] else float(r["Taxa Venda Manha"]),
                        "pu": float(r["PU Compra Manha"] or r["PU Venda Manha"])})
        out = [o for o in out if o["taxa"] > 0]
        if out:
            return out, f"ao vivo (Tesouro Transparente, {ult:%d/%m/%Y})"
    except Exception:
        pass
    return SNAP["tesouro"], f"reserva de {SNAP['data']}"


# ---------------- Focus, IPCA e Selic ----------------
OLINDA = "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/"


@st.cache_data(ttl=3600 * 6, show_spinner=False)
def focus():
    try:
        res = {}
        for ind in ("IPCA", "Selic"):
            url = (OLINDA + "ExpectativasMercadoAnuais?$top=60&$format=json&$orderby=Data%20desc"
                   f"&$filter=Indicador%20eq%20'{ind}'%20and%20baseCalculo%20eq%200")
            v = _get(url).json()["value"]
            ult = v[0]["Data"]
            res[ind] = {int(x["DataReferencia"]): float(x["Mediana"]) for x in v if x["Data"] == ult}
            res["data"] = ult
        if res.get("IPCA"):
            return res, "ao vivo (Banco Central, Focus)"
    except Exception:
        pass
    m = SNAP["macro"]
    return {"IPCA": {int(k): v for k, v in m["ipca_anual"].items()}, "Selic": {int(k): v for k, v in m["selic_focus"].items()},
            "data": m["focus_data"]}, f"reserva de {SNAP['data']}"


@st.cache_data(ttl=3600 * 6, show_spinner=False)
def ipca_mensal():
    try:
        v = _get("https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados/ultimos/24?formato=json").json()
        df = pd.DataFrame(v)
        df["data"] = pd.to_datetime(df["data"], dayfirst=True)
        df["valor"] = df["valor"].astype(float)
        return df, "ao vivo (Banco Central, SGS 433)"
    except Exception:
        df = pd.DataFrame(SNAP["macro"]["ipca_mensal"], columns=["mes", "valor"])
        df["data"] = pd.to_datetime(df["mes"] + "-01")
        return df[["data", "valor"]], f"reserva de {SNAP['data']}"


@st.cache_data(ttl=3600 * 6, show_spinner=False)
def selic_atual():
    try:
        v = _get("https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados/ultimos/1?formato=json").json()
        return float(v[-1]["valor"]), "ao vivo (Banco Central, SGS 432)"
    except Exception:
        return SNAP["macro"]["selic"], f"reserva de {SNAP['data']}"


# ---------------- Títulos públicos (ANBIMA, mercado secundário) ----------------
def _anbima_arquivo(dia: dt.date):
    url = f"https://www.anbima.com.br/informacoes/merc-sec/arqs/ms{dia:%y%m%d}.txt"
    txt = _get(url).content.decode("latin-1")
    rows = {}
    for linha in txt.splitlines():
        p = linha.split("@")
        if len(p) > 8 and p[0] in ("LTN", "NTN-F", "NTN-B", "NTN-C", "LFT"):
            venc = f"{p[4][:4]}-{p[4][4:6]}-{p[4][6:]}"
            rows[(p[0], venc)] = (float(p[7].replace(",", ".")), float(p[8].replace(",", ".")))
    if len(rows) < 30:
        raise ValueError("arquivo incompleto")
    return rows


@st.cache_data(ttl=3600 * 4, show_spinner=False)
def anbima():
    """Taxas indicativas do último dia disponível (a ANBIMA publica no fim do dia e guarda 5 dias úteis)."""
    hoje = dt.date.today()
    for k in range(0, 8):
        dia = hoje - dt.timedelta(days=k)
        if dia.weekday() >= 5:
            continue
        try:
            return _anbima_arquivo(dia), dia.strftime("%d/%m/%Y"), f"ao vivo (ANBIMA, {dia:%d/%m/%Y})"
        except Exception:
            continue
    return {}, None, "ANBIMA indisponível: usando as taxas da corretora de " + SNAP["data"]


@st.cache_data(ttl=3600 * 24 * 30, show_spinner=False)
def anbima_base():
    """Taxas da ANBIMA em 03/11/2026, o dia da lista da corretora (serve de ponto de partida)."""
    try:
        return _anbima_arquivo(dt.date(2026, 11, 3))
    except Exception:
        return {}


def _sgs(serie, n):
    return _get(f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados/ultimos/{n}?formato=json").json()


@st.cache_data(ttl=3600 * 6, show_spinner=False)
def indexadores():
    """Selic, CDI, IPCA e poupança acumulados em 12 meses (Banco Central)."""
    out = dict(SNAP["indexadores"])
    origem = f"reserva de {SNAP['data']}"
    try:
        def ac(serie):
            p = 1.0
            for x in _sgs(serie, 12):
                p *= 1 + float(x["valor"]) / 100
            return round((p - 1) * 100, 2)
        out["selic12"], out["cdi12"] = ac(4390), ac(4391)
        out["ipca12"] = float(_sgs(13522, 1)[-1]["valor"])
        ini = (dt.date.today().replace(day=1) - dt.timedelta(days=370)).strftime("%d/%m/%Y")
        v = [x for x in _get(f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.195/dados?formato=json&dataInicial={ini}").json() if x["data"].startswith("01/")][-12:]
        p = 1.0
        for x in v:
            p *= 1 + float(x["valor"]) / 100
        out["poup12"] = round((p - 1) * 100, 2)
        out["data"] = dt.date.today().strftime("%d/%m/%Y")
        origem = "ao vivo (Banco Central)"
    except Exception:
        pass
    return out, origem
