"""Cálculos: Black-Scholes, volatilidade implícita, resultados de estratégias e simulador de investimentos."""
from __future__ import annotations
import math
from dataclasses import dataclass, field

RR = math.log(1.14)  # juro contínuo aproximado para as opções


def ncdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def bs(tipo: str, S: float, K: float, T: float, r: float, v: float) -> dict:
    """Preço, delta e chance de terminar no dinheiro (tipo 'C' ou 'P')."""
    T = max(T, 1e-6)
    d1 = (math.log(S / K) + (r + v * v / 2) * T) / (v * math.sqrt(T))
    d2 = d1 - v * math.sqrt(T)
    if tipo == "C":
        p = S * ncdf(d1) - K * math.exp(-r * T) * ncdf(d2)
        return {"p": p, "delta": ncdf(d1), "itm": ncdf(d2)}
    p = K * math.exp(-r * T) * ncdf(-d2) - S * ncdf(-d1)
    return {"p": p, "delta": ncdf(d1) - 1, "itm": ncdf(-d2)}


def vol_implicita(tipo: str, S: float, K: float, T: float, r: float, preco: float):
    intr = max(S - K * math.exp(-r * T), 0) if tipo == "C" else max(K * math.exp(-r * T) - S, 0)
    if preco <= intr + 1e-6:
        return None
    lo, hi = 0.01, 4.0
    for _ in range(80):
        m = (lo + hi) / 2
        if bs(tipo, S, K, T, r, m)["p"] > preco:
            hi = m
        else:
            lo = m
    return (lo + hi) / 2


# ---------------- estratégias ----------------
@dataclass
class Perna:
    t: str          # 'C', 'P' ou 'S' (ação)
    s: int          # +1 compra, -1 venda
    p: float        # prêmio (ou preço da ação)
    K: float = 0.0
    tk: str = ""


def resultado(pernas: list[Perna], ST: float) -> float:
    tot = 0.0
    for l in pernas:
        if l.t == "S":
            tot += l.s * (ST - l.p)
        else:
            v = max(ST - l.K, 0) if l.t == "C" else max(l.K - ST, 0)
            tot += l.s * (v - l.p)
    return tot


def prob_lucro(pernas, S, T, v, n=400):
    from statistics import NormalDist
    nd = NormalDist()
    ok = 0
    for i in range(n):
        z = nd.inv_cdf((i + 0.5) / n)
        ST = S * math.exp(-v * v * T / 2 + v * math.sqrt(T) * z)
        if resultado(pernas, ST) > 0:
            ok += 1
    return ok / n


def extremos(pernas, S):
    ys = [resultado(pernas, S * i / 200) for i in range(401)]
    sobe = resultado(pernas, S * 3) - resultado(pernas, S * 2.9)
    return (math.inf if sobe > 1e-3 else max(ys)), min(ys)


def empates(pernas, S):
    out, prev = [], resultado(pernas, S * 0.5)
    for i in range(1, 401):
        x = S * (0.5 + i / 400)
        y = resultado(pernas, x)
        if (prev <= 0 < y) or (prev > 0 >= y):
            out.append(x)
        prev = y
    return out


def vol_da_serie(S, linhas, tipo, T):
    if not linhas:
        return 0.35
    tk, K, p = min(linhas, key=lambda r: abs(r[1] - S))[:3]
    v = vol_implicita(tipo, S, K, T, RR, p)
    return v if v and 0.05 < v < 2 else 0.35


ESTRATEGIAS = [  # do menor para o maior risco
    ("financiamento", "Financiamento coberto", "Compra a ação e vende CALL abaixo do preço: renda parecida com renda fixa, com risco da ação.", "Risco: o da ação", "Intermediário"),
    ("venda_coberta", "Venda coberta de CALL", "Recebe prêmio pela ação que já tem, aceitando vendê-la acima do preço de hoje.", "Risco: o da ação", "Iniciante"),
    ("venda_put", "Venda de PUT", "Recebe prêmio aceitando comprar a ação abaixo do preço de hoje.", "Risco: o da ação", "Iniciante"),
    ("trava_alta", "Trava de alta", "Compra uma CALL e vende outra de strike maior.", "Perda limitada", "Intermediário"),
    ("trava_baixa", "Trava de baixa", "Compra uma PUT e vende outra de strike menor.", "Perda limitada", "Intermediário"),
    ("straddle", "Straddle", "Ganha se a ação andar muito, para qualquer lado.", "Perda limitada", "Intermediário"),
    ("strangle", "Strangle", "Como o straddle, mais barato, mas precisa de mais movimento.", "Perda limitada", "Intermediário"),
    ("seca", "Compra seca", "Aposta numa direção pagando só o prêmio.", "Perda limitada", "Iniciante"),
]
NIVEL_RISCO_ESTR = {"financiamento": 3, "venda_coberta": 4, "venda_put": 4, "trava_alta": 4, "trava_baixa": 4, "straddle": 5, "strangle": 5, "seca": 5}


def gerar_ideias(ativo, S, calls, puts, du, selic):
    """calls/puts: listas [ticker, strike, preço]. Retorna dict estratégia -> lista de ideias."""
    T = du / 252
    out = {e[0]: [] for e in ESTRATEGIAS}
    C = sorted(calls, key=lambda r: r[1])
    P = sorted(puts, key=lambda r: r[1])

    def add(eid, pernas, txt, extra=None):
        mx, mn = extremos(pernas, S)
        v = vol_da_serie(S, C or P, "C" if C else "P", T)
        item = {"ativo": ativo, "S": S, "du": du, "texto": txt, "pernas": pernas,
                "custo": sum(l.s * l.p for l in pernas) * 100, "max": mx * 100, "min": mn * 100,
                "empate": empates(pernas, S), "prob": prob_lucro(pernas, S, T, v), "vol": v}
        if extra:
            item.update(extra)
        out[eid].append(item)

    alvo_c = [r for r in C if S * 1.005 <= r[1] <= S * 1.05]
    if alvo_c:
        r = min(alvo_c, key=lambda r: abs(r[1] - S * 1.025))
        add("seca", [Perna("C", 1, r[2], r[1], r[0])], f"Comprar CALL {r[0]} (strike {r[1]:.2f}) por {r[2]:.2f}")
    alvo_p = [r for r in P if S * 0.95 <= r[1] <= S * 0.995]
    if alvo_p:
        r = min(alvo_p, key=lambda r: abs(r[1] - S * 0.975))
        add("seca", [Perna("P", 1, r[2], r[1], r[0])], f"Comprar PUT {r[0]} (strike {r[1]:.2f}) por {r[2]:.2f}")
    for b in [r for r in C if S * 0.98 <= r[1] <= S * 1.02][:2]:
        cand = [r for r in C if b[1] + S * 0.025 <= r[1] <= b[1] + S * 0.07 and r[2] < b[2]]
        if cand:
            s_ = cand[0]
            deb, w = b[2] - s_[2], s_[1] - b[1]
            if 0.05 * w < deb < 0.7 * w:
                add("trava_alta", [Perna("C", 1, b[2], b[1], b[0]), Perna("C", -1, s_[2], s_[1], s_[0])],
                    f"Comprar {b[0]} ({b[1]:.2f}) e vender {s_[0]} ({s_[1]:.2f}) · custo {deb:.2f}")
    for b in [r for r in P if S * 0.98 <= r[1] <= S * 1.02][:2]:
        cand = [r for r in reversed(P) if b[1] - S * 0.07 <= r[1] <= b[1] - S * 0.025 and r[2] < b[2]]
        if cand:
            s_ = cand[0]
            deb, w = b[2] - s_[2], b[1] - s_[1]
            if 0.05 * w < deb < 0.7 * w:
                add("trava_baixa", [Perna("P", 1, b[2], b[1], b[0]), Perna("P", -1, s_[2], s_[1], s_[0])],
                    f"Comprar {b[0]} ({b[1]:.2f}) e vender {s_[0]} ({s_[1]:.2f}) · custo {deb:.2f}")
    for r in sorted([r for r in P if S * 0.93 <= r[1] <= S * 0.985 and (r[2] / r[1]) / T >= selic / 100], key=lambda r: -r[1])[:2]:
        add("venda_put", [Perna("P", -1, r[2], r[1], r[0])], f"Vender {r[0]} (strike {r[1]:.2f}) por {r[2]:.2f} · reservar R$ {r[1]*100:,.0f}",
            {"rende": r[2] / r[1]})
    for r in [r for r in C if S * 1.01 <= r[1] <= S * 1.07 and (r[2] / S) / T >= selic / 100][:2]:
        add("venda_coberta", [Perna("S", 1, S), Perna("C", -1, r[2], r[1], r[0])],
            f"Com 100 ações a {S:.2f}, vender {r[0]} (strike {r[1]:.2f}) por {r[2]:.2f}", {"rende": r[2] / S})
    pares = [(c, next(p for p in P if abs(p[1] - c[1]) < 1e-3)) for c in C if any(abs(p[1] - c[1]) < 1e-3 for p in P) and abs(c[1] - S) <= S * 0.02]
    if pares:
        c, p = min(pares, key=lambda cp: abs(cp[0][1] - S))
        add("straddle", [Perna("C", 1, c[2], c[1], c[0]), Perna("P", 1, p[2], p[1], p[0])],
            f"Comprar {c[0]} e {p[0]} (strike {c[1]:.2f}) · custo {c[2]+p[2]:.2f}")
    cc = [r for r in C if S * 1.02 <= r[1] <= S * 1.06]
    pp = [r for r in P if S * 0.94 <= r[1] <= S * 0.98]
    if cc and pp:
        c, p = cc[0], pp[-1]
        add("strangle", [Perna("C", 1, c[2], c[1], c[0]), Perna("P", 1, p[2], p[1], p[0])],
            f"Comprar {c[0]} ({c[1]:.2f}) e {p[0]} ({p[1]:.2f}) · custo {c[2]+p[2]:.2f}")
    fin = []
    for r in C:
        if S * 0.9 <= r[1] < S * 0.995:
            net = S - r[2]
            ret = r[1] / net - 1
            if ret > 0 and ret / T >= selic / 100:
                fin.append((ret, r, net))
    for ret, r, net in sorted(fin, reverse=True)[:2]:
        add("financiamento", [Perna("S", 1, S), Perna("C", -1, r[2], r[1], r[0])],
            f"Comprar 100 ações a {S:.2f} e vender {r[0]} (strike {r[1]:.2f}) por {r[2]:.2f} · custo líquido {net:.2f}", {"rende": ret})
    return out


# ---------------- simulador de investimentos ----------------
PRODUTOS = [  # em ordem de risco, do menor para o maior
    # id, nome, grupo, tipo, taxa padrão, unidade, imposto, sensibilidade, risco
    ("tsel", "Tesouro Selic", "Renda fixa", "cdi+", 0.1057, "% + Selic", "rf", 0, "Governo; liquidez diária"),
    ("cdb100", "CDB liquidez diária", "Renda fixa", "cdi", 100, "% do CDI", "rf", 0, "FGC até R$ 250 mil"),
    ("fdi", "Fundo DI (taxa 0,3%)", "Renda fixa", "cdi", 99.7, "% do CDI", "rf", 0, "Sem FGC, risco baixo; come-cotas"),
    ("poup", "Poupança", "Renda fixa", "pre", 7.5, "% a.a.", "isento", 0, "FGC; rende menos que a Selic"),
    ("lci", "LCI/LCA pós-fixada", "Renda fixa isenta", "cdi", 93, "% do CDI", "isento", 0, "FGC; carência mínima"),
    ("lcd", "LCD (banco de desenvolvimento)", "Renda fixa isenta", "cdi", 90, "% do CDI", "isento", 0, "FGC; prazo mínimo 12 meses"),
    ("cdb2a", "CDB de banco médio (2 anos)", "Renda fixa", "cdi", 115, "% do CDI", "rf", 0, "FGC; preso até o vencimento"),
    ("cdbpre", "CDB prefixado (3 anos)", "Renda fixa", "pre", 15.0, "% a.a.", "rf", 0, "FGC; preso até o vencimento"),
    ("lciipca", "LCI/LCA IPCA+", "Renda fixa isenta", "ipca", 7.0, "IPCA + % a.a.", "isento", 0, "FGC; preso até o vencimento"),
    ("cdbipca", "CDB IPCA+ (3 anos)", "Renda fixa", "ipca", 7.5, "IPCA + % a.a.", "rf", 0, "FGC; preso até o vencimento"),
    ("lig", "LIG IPCA+", "Renda fixa isenta", "ipca", 6.6, "IPCA + % a.a.", "isento", 0, "Sem FGC, dupla garantia"),
    ("fidc", "FIDC (cota sênior)", "Crédito privado", "cdi+", 3.0, "% + CDI", "rf", 0, "SEM FGC; protegido pela cota subordinada"),
    ("cra", "CRI/CRA pós-fixado", "Crédito privado", "cdi+", 2.5, "% + CDI", "isento", 0, "SEM FGC: risco de calote; liquidez baixa"),
    ("fiinfra", "FI-Infra (debêntures incentivadas)", "Crédito privado", "ipca", 7.5, "IPCA + % a.a.", "isento", 3, "SEM FGC; oscila com os juros"),
    ("deb", "Debênture incentivada", "Crédito privado", "ipca", 8.5, "IPCA + % a.a.", "isento", 4, "SEM FGC: risco de calote; oscila com os juros"),
    ("fiipapel", "FII de papel (CRI)", "Fundos imobiliários", "fii", 14, "% a.a. de dividendos", "fii", -2, "Cotas oscilam; risco dos CRIs"),
    ("fiitijolo", "FII de tijolo", "Fundos imobiliários", "fii", 10, "% a.a. de dividendos", "fii", -5, "Cotas muito sensíveis aos juros"),
    ("divs", "Carteira de dividendos", "Renda variável", "divs", 8, "% a.a. de dividendos", "rv", 0, "Beta 0,7"),
    ("usd", "Dólar (ETF/fundo cambial)", "Exterior", "usd", 0, "—", "rv", 0, "Proteção contra crise no Brasil"),
    ("ouro", "Ouro (ETF GOLD11)", "Exterior", "ouro", 0, "—", "rv", 0, "Proteção em crises; não paga juros"),
    ("ivvb", "IVVB11 (S&P 500 em reais)", "Exterior", "ivvb", 1.3, "% a.a. de dividendos", "rv", 0, "Bolsa americana + dólar"),
    ("bova", "BOVA11 (Ibovespa)", "Renda variável", "bolsa", 3, "% a.a. de dividendos", "rv", 0, "Oscila com a bolsa"),
]

# Nível de risco (1 = menor): garantia, chance de calote e quanto o valor oscila no caminho
NIVEL_RISCO = {"tsel": 1, "cdb100": 1, "fdi": 1, "poup": 1, "lci": 2, "lcd": 2, "cdb2a": 2, "cdbpre": 2, "lciipca": 2, "cdbipca": 2, "lig": 2, "fidc": 3, "cra": 3, "fiinfra": 3, "deb": 3, "fiipapel": 3, "fiitijolo": 4, "divs": 4, "usd": 4, "ouro": 4, "ivvb": 4, "bova": 5}
ROTULO_RISCO = ["", "Muito baixo", "Baixo", "Moderado", "Alto", "Muito alto"]


def rotulo_risco(n):
    return f"{n} · {ROTULO_RISCO[n]} " + "●" * n + "○" * (5 - n)


# Risco das ações: beta (quanto oscila junto com a bolsa) + acréscimo para dívida acima de 1x o patrimônio
BETA_ACOES = {"PETR4": 1.1, "VALE3": 1.0, "ITUB4": 0.9, "BBDC4": 1.1, "BBAS3": 1.2, "BBSE3": 0.6, "CXSE3": 0.6, "TAEE11": 0.5,
              "ISAE4": 0.6, "CMIG4": 0.8, "B3SA3": 1.1, "WEGE3": 0.8, "SUZB3": 0.6, "PRIO3": 1.0, "GGBR4": 1.0, "ABEV3": 0.6,
              "VIVT3": 0.6, "ITSA4": 0.85, "EGIE3": 0.6, "SAPR11": 0.7}


def risco_acao(ticker, divpl=None):
    """Pontuação de risco (menor = menos arriscada) e nível de 1 a 5 na mesma escala dos produtos."""
    v = BETA_ACOES.get(ticker, 1.0) + (0.2 if divpl is not None and divpl > 1 else 0)
    return v, (3 if v <= 0.65 else 4 if v <= 0.95 else 5)


def risco_tesouro(tipo, anos):
    """Tesouro Selic quase não oscila; quanto mais longo, mais o preço oscila antes do vencimento."""
    if tipo == "S":
        return 1
    return 2 if anos <= 3.5 else 3 if anos <= 7 else 4 if anos <= 15 else 5

CENARIOS = {
    "Base (Focus)": dict(se=12.5, inf=4.8, dp=-1, ib=10, fx=-3, spx=8, gold=5, cred=0),
    "Pânico fiscal": dict(se=15.5, inf=6.5, dp=3, ib=-20, fx=20, spx=-10, gold=15, cred=1),
    "Alívio fiscal": dict(se=11, inf=4.2, dp=-3, ib=25, fx=-10, spx=10, gold=0, cred=0),
    "Inflação alta": dict(se=15, inf=7, dp=2, ib=-8, fx=8, spx=0, gold=10, cred=0),
    "Recessão": dict(se=10.5, inf=3.8, dp=-2.5, ib=-12, fx=5, spx=-5, gold=8, cred=1),
}
PESOS = {"Base (Focus)": 0.4, "Pânico fiscal": 0.15, "Alívio fiscal": 0.15, "Inflação alta": 0.15, "Recessão": 0.15}


def fator(prod, taxa, c, meses, selic_atual):
    pid, _, _, k, _, _, _, sens, _ = prod
    sel = 1.0
    for i in range(meses):
        s = selic_atual + (c["se"] - selic_atual) * min(1, (i + 0.5) / 12)
        sel *= (1 + s / 100) ** (1 / 12)
    y = meses / 12
    f = min(1, y)
    inf = (1 + c["inf"] / 100) ** y
    an = lambda x: (1 + x / 100) ** y
    if k == "pre":
        return an(taxa)
    if k == "cdi":
        return 1 + (sel - 1) * taxa / 100
    if k == "cdi+":
        return sel * an(taxa) * (1 - 0.03 * f if pid in ("cra", "fidc") and c.get("cred") else 1)
    if k == "ipca":
        v = inf * an(taxa)
        if sens and meses < 60:
            v *= 1 - sens * (c["dp"] * 0.6) / 100 * f
        if pid in ("deb", "fiinfra") and c.get("cred"):
            v *= 1 - 0.03 * f
        return v
    if k == "fii":
        v = (1 + taxa / 100 * y) * (1 + sens * c["dp"] / 100 * f + (0.5 * (inf - 1) if pid == "fiitijolo" else 0))
        if pid == "fiipapel" and c.get("cred"):
            v *= 1 - 0.03 * f
        return v
    if k == "bolsa":
        return an(c["ib"]) * (1 + taxa / 100 * y)
    if k == "divs":
        return (1 + 0.7 * c["ib"] / 100 - 0.03 * c["dp"]) ** y * (1 + taxa / 100 * y)
    if k == "ivvb":
        return an(c["spx"]) * an(c["fx"]) * (1 + taxa / 100 * y)
    if k == "usd":
        return an(c["fx"])
    if k == "ouro":
        return an(c["gold"]) * an(c["fx"])
    return 1.0


def liquido(prod, g, meses):
    imposto = prod[6]
    d = meses * 30.4
    if g <= 1 or imposto in ("isento", "fii"):
        return g
    if imposto == "rf":
        ir = 0.225 if d <= 180 else 0.2 if d <= 360 else 0.175 if d <= 720 else 0.15
        return 1 + (g - 1) * (1 - ir)
    return 1 + (g - 1) * 0.85


def tesouro_retorno(tipo, taxa, anos_ate_venc, c, horizonte=1.0):
    """Retorno bruto vendendo após 'horizonte' anos. tipo: 'P' prefixado, 'I' IPCA+."""
    n = anos_ate_venc
    if tipo == "P":
        return (1 + taxa / 100) ** n / (1 + (taxa + c["dp"]) / 100) ** (n - horizonte) - 1
    dr = c["dp"] * 0.5
    return (1 + c["inf"] / 100) ** horizonte * (1 + taxa / 100) ** n / (1 + (taxa + dr) / 100) ** (n - horizonte) - 1


# ---------------- Títulos públicos ----------------
NOME_TITULO = {"LTN": "Tesouro Prefixado", "NTN-F": "Tesouro Prefixado com Juros Semestrais", "NTN-F Principal": "Prefixado que paga tudo no vencimento",
               "NTN-B": "Tesouro IPCA+ com Juros Semestrais", "NTN-B Principal": "Tesouro IPCA+", "NTN-C": "IGP-M + juros (fora do Tesouro Direto)", "LFT": "Tesouro Selic"}


def nivel_titulo(nota):
    return 1 if nota <= 2 else 2 if nota <= 10 else 3 if nota <= 20 else 4 if nota <= 30 else 5


def fluxo_titulo(tipo, anos):
    cup = {"NTN-F": 1.10 ** 0.5 - 1, "NTN-B": 1.06 ** 0.5 - 1, "NTN-C": 1.12 ** 0.5 - 1}.get(tipo, 0)
    fl, t = [], anos
    if cup:
        while t > 0.001:
            fl.append((t, cup * 100))
            t -= 0.5
    fl.append((anos, 100.0))
    return fl


def preco_titulo(fl, r, desde=0.0):
    return sum(c / (1 + r / 100) ** (t - desde) for t, c in fl if t > desde + 1e-9)


def duration_titulo(fl, r):
    P = preco_titulo(fl, r)
    return sum(t * c / (1 + r / 100) ** t for t, c in fl) / P / (1 + r / 100)


def retorno_titulo(tipo, idx, taxa, anos, d, h, selic_media, infl):
    """Retorno bruto em h anos se a taxa mudar d p.p. (cupons reinvestidos na Selic)."""
    sel = selic_media / 100
    inf = infl / 100 if idx in ("IPCA", "IGPM") else 0
    if idx == "SELIC":
        return (1 + sel) ** h * (1 + taxa / 100) ** min(h, anos) - 1
    fl = fluxo_titulo(tipo, anos)
    P0 = preco_titulo(fl, taxa)
    v = sum(c * (1 + sel) ** (h - t) / (1 + inf) ** (h - t) for t, c in fl if t <= h + 1e-9)
    if anos > h + 1e-9:
        v += preco_titulo(fl, taxa + d, h)
    return v / P0 * (1 + inf) ** h - 1


def ir_prazo(anos):
    return 0.15 if anos > 2 else 0.175 if anos > 1 else 0.20 if anos > 0.5 else 0.225
