"""Dia a Dia no Mercado — versão Python (Streamlit) com dados ao vivo.

Para rodar:  streamlit run app.py
"""
from __future__ import annotations
import datetime as dt
import math
import time
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

import calculos as C
import dados as D

st.set_page_config(page_title="Dia a Dia no Mercado", page_icon="📈", layout="wide", initial_sidebar_state="collapsed")

SITE = "https://marciomedicinausp-cpu.github.io/DiaADiaNoMercado/"

st.markdown("""<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, .stApp, [data-testid="stMarkdownContainer"], [data-testid="stMetric"], button, input, select, textarea {font-family:'Inter',system-ui,sans-serif !important;}
.block-container {padding-top:2.2rem; padding-bottom:3rem; max-width:1280px;}
h1 {font-size:2rem !important; font-weight:700 !important; letter-spacing:-.02em; color:#12372A; margin-bottom:.2rem !important;}
h2 {font-size:1.35rem !important; font-weight:600 !important; color:#12372A; margin-top:1.6rem !important;}
h3 {font-size:1.12rem !important; font-weight:600 !important; color:#12372A; margin-top:1.3rem !important;}
[data-testid="stMetric"] {background:#FFFFFF; border:1px solid #E1E5DD; border-radius:12px; padding:12px 16px; box-shadow:0 1px 2px rgba(0,0,0,.03);}
[data-testid="stMetricLabel"] p {font-size:.8rem !important; color:#5B6660 !important; font-weight:500;}
[data-testid="stMetricValue"] {font-size:1.45rem !important; font-weight:600; color:#17201C;}
[data-testid="stDataFrame"], [data-testid="stTable"] {border:1px solid #E1E5DD; border-radius:10px; overflow:hidden; background:#fff;}
[data-testid="stSidebar"] {background:#12372A;}
[data-testid="stSidebar"] * {color:#E9F1EC !important;}
[data-testid="stSidebar"] h1 {font-size:1.25rem !important; color:#FFFFFF !important; margin:0 !important;}
[data-testid="stSidebar"] [role="radiogroup"] label {padding:7px 10px; border-radius:8px; margin:1px 0; width:100%;}
[data-testid="stSidebar"] [role="radiogroup"] label:hover {background:rgba(255,255,255,.08);}
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {background:rgba(255,255,255,.16); font-weight:600;}
[data-testid="stSidebar"] button {background:transparent !important; border:1px solid rgba(255,255,255,.35) !important;}
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {opacity:.8;}
.selo {display:inline-block; font-size:.75rem; font-weight:600; padding:3px 9px; border-radius:99px; margin-right:6px;}
.selo.vivo {background:#DDF3E6; color:#11794A;} .selo.fechado {background:#EEF0EC; color:#5B6660;}
#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stStatusWidget"] {visibility:hidden;}
</style>""", unsafe_allow_html=True)


def _ok(v):
    return v is not None and not (isinstance(v, float) and math.isnan(v))


NUM = lambda v, d=2: (f"{v:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")) if _ok(v) else "—"
TAXA = lambda v, d=2: NUM(v, d) + "%" if _ok(v) else "—"          # valor já em %, ex.: 15.19 -> 15,19%
BRL = lambda v: (("−" if v < 0 else "") + "R$ " + NUM(abs(v))) if _ok(v) else "—"
PCT = lambda v, d=1: (f"{v*100:+.{d}f}%").replace(".", ",") if _ok(v) else "—"   # fração, ex.: 0.05 -> +5,0%
DATA = lambda v: dt.date.fromisoformat(str(v)[:10]).strftime("%d/%m/%Y") if v else "—"
AVISO_LEGAL = ("Conteúdo educativo. Nada aqui é recomendação de compra ou venda de investimentos: os números são simulações com premissas "
               "simplificadas e dados públicos que podem estar atrasados ou incorretos. Rentabilidade passada não garante rentabilidade futura. "
               "Antes de investir, avalie seu perfil e, se precisar, procure um profissional certificado.")
AVISO = "Simulação educativa com premissas simplificadas. Não é recomendação de investimento."


def cor(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return ""
    a = min(abs(v) / 0.3, 1)
    return f"background-color: rgba({'17,121,74' if v >= 0 else '190,51,40'},{a*0.45:.2f})"


def grafico_resultado(xs, ys, S, titulo="Resultado no vencimento (R$)"):
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=xs, y=[max(y, 0) for y in ys], fill="tozeroy", mode="none", fillcolor="rgba(17,121,74,.25)", name="lucro"))
    fig.add_trace(go.Scatter(x=xs, y=[min(y, 0) for y in ys], fill="tozeroy", mode="none", fillcolor="rgba(190,51,40,.25)", name="prejuízo"))
    fig.add_trace(go.Scatter(x=xs, y=ys, mode="lines", line=dict(width=3, color="#2340C9"), name="resultado"))
    fig.add_vline(x=S, line_dash="dash", line_color="gray", annotation_text="hoje")
    fig.update_layout(height=320, margin=dict(l=10, r=10, t=30, b=10), title=titulo, showlegend=False,
                      xaxis_title="preço do ativo no vencimento", yaxis_title="R$")
    return fig


# ---------------- barra lateral ----------------
PAGINAS = ["Site completo (aulas e simuladores)", "Painel ao vivo", "Renda fixa e inflação", "Títulos públicos na corretora", "Simulador e melhores ativos",
           "Ações por fundamentos", "Estratégias com opções", "Quanto vale esta opção?", "Radar de opções"]
AO_VIVO = {"Painel ao vivo", "Estratégias com opções", "Quanto vale esta opção?", "Radar de opções"}  # páginas com preços do pregão

st.sidebar.title("Dia a Dia no Mercado")
st.sidebar.caption("Conteúdo educativo. Não é recomendação de investimento.")
pagina = st.sidebar.radio("Páginas, do menor para o maior risco", PAGINAS)
pregao = D.em_pregao()
auto = st.sidebar.toggle("Atualizar a cada minuto no pregão", value=True)
if st.sidebar.button("Atualizar dados agora", use_container_width=True):
    st.cache_data.clear()
    st.rerun()
st.sidebar.caption(("Pregão aberto. " if pregao else "Pregão fechado. ") +
                   "Preços renovados a cada minuto; juros e inflação a cada poucas horas. "
                   "Se uma fonte não responde, o app usa a reserva de " + D.SNAP["data"] + ".")
selic, orig_selic = D.selic_atual()


def selo():
    h = D.agora().strftime("%d/%m %H:%M")
    if pregao:
        st.markdown(f'<span class="selo vivo">● Pregão aberto · {h}</span>', unsafe_allow_html=True)
    else:
        st.markdown(f'<span class="selo fechado">Pregão fechado · {h}</span>', unsafe_allow_html=True)


# ---------------- Início ----------------
if pagina == "Painel ao vivo":
    st.title("Painel do investidor")
    selo()
    foc, orig_foc = D.focus()
    ipca, orig_ipca = D.ipca_mensal()
    mk, hora_mk = D.mercado_agora()
    i12 = (ipca.tail(12)["valor"].div(100).add(1).prod() - 1) * 100
    anos_i = sorted(foc["IPCA"])
    anos_s = sorted(foc["Selic"])
    ano_s = anos_s[1] if len(anos_s) > 1 else anos_s[0]
    st.subheader("Mercado agora")
    c = st.columns(4)
    if "Ibovespa" in mk:
        c[0].metric("Ibovespa", NUM(mk["Ibovespa"][0], 0) + " pts", PCT(mk["Ibovespa"][1], 2) + " no dia")
    else:
        c[0].metric("Ibovespa", "—")
    if "Dólar" in mk:
        c[1].metric("Dólar", "R$ " + NUM(mk["Dólar"][0], 3), PCT(mk["Dólar"][1], 2) + " no dia", delta_color="inverse")
    else:
        c[1].metric("Dólar", "—")
    c[2].metric("Selic (meta)", TAXA(selic))
    c[3].metric("IPCA 12 meses", TAXA(i12), f"último mês {TAXA(ipca['valor'].iloc[-1])}", delta_color="off")
    st.caption(f"Ibovespa e dólar: Yahoo Finance às {hora_mk} (a B3 chega com até 15 minutos de atraso).")
    st.subheader("O que o mercado espera (Focus)")
    c = st.columns(4)
    c[0].metric(f"IPCA {anos_i[0]}", TAXA(foc["IPCA"][anos_i[0]]))
    c[1].metric(f"IPCA {anos_i[1]}" if len(anos_i) > 1 else "IPCA", TAXA(foc["IPCA"][anos_i[1]]) if len(anos_i) > 1 else "—")
    c[2].metric(f"Selic fim de {anos_s[0]}", TAXA(foc["Selic"][anos_s[0]]))
    c[3].metric(f"Selic fim de {ano_s}", TAXA(foc["Selic"][ano_s]))
    col1, col2 = st.columns([3, 2])
    with col1:
        st.subheader(f"Notícias de referência ({D.SNAP['data']})")
        for k, t in D.SNAP["noticias"]:
            st.markdown(f"**{k}:** {t}")
    with col2:
        st.subheader("De onde vêm os dados")
        st.dataframe(pd.DataFrame([["Selic", orig_selic], ["Focus", orig_foc], ["IPCA", orig_ipca], ["Tesouro", D.tesouro()[1]]],
                                  columns=["Dado", "Origem"]), hide_index=True, use_container_width=True)
    st.info("Use o menu à esquerda (seta no canto superior esquerdo). O **Site completo** traz as 35 lições e os simuladores.")
    st.caption(AVISO)

# ---------------- Quanto vale esta opção? ----------------
elif pagina == "Quanto vale esta opção?":
    st.title("Quanto vale esta opção?")
    selo()
    st.caption("Escolha a opção: o tipo, a ação, o preço de exercício, o vencimento, o prêmio e a volatilidade vêm sozinhos. "
               "Depois escolha um preço para a ação e uma data para ver quanto ela valeria e quanto você ganharia ou perderia.")
    FER = {dt.date(2026, 11, 20), dt.date(2026, 12, 24), dt.date(2026, 12, 25), dt.date(2026, 12, 31), dt.date(2027, 1, 1),
           dt.date(2027, 2, 8), dt.date(2027, 2, 9), dt.date(2027, 3, 26), dt.date(2027, 4, 21), dt.date(2027, 5, 1)}
    def pregoes(a, b):
        n, d = 0, a
        while d < b:
            d += dt.timedelta(days=1)
            n += d.weekday() < 5 and d not in FER
        return n
    c1, c2 = st.columns(2)
    ativo = c1.selectbox("Ação", D.ATIVOS)
    o = D.opcoes(ativo)
    lista = [("C", r) for r in o["calls"]] + [("P", r) for r in o["puts"]]
    if not lista:
        st.warning("Sem opções para esta ação agora.")
        st.stop()
    rotulo = {f"{r[0]} · {'CALL' if t == 'C' else 'PUT'} {r[1]:.2f}".replace(".", ","): (t, r) for t, r in lista}
    esc = c2.selectbox("Código da opção", list(rotulo))
    t, r = rotulo[esc]
    tk, K, premio = r[0], float(r[1]), float(r[2])
    S0 = float(o["spot"])
    venc = dt.datetime.strptime(o["venc"][:10], "%d/%m/%Y").date()
    hoje = dt.date.today()
    T0 = max(pregoes(hoje, venc), 1) / 252
    vol = C.vol_implicita(t, S0, K, T0, C.RR, premio) or 0.35
    st.markdown(f"**{'CALL' if t == 'C' else 'PUT'} {tk}**: o direito de **{'comprar' if t == 'C' else 'vender'}** {ativo} a **{BRL(K)}** até "
                f"**{venc:%d/%m/%Y}** ({pregoes(hoje, venc)} dias de bolsa). Ganha valor quando a ação {'sobe' if t == 'C' else 'cai'}.")
    m = st.columns(6)
    for col, (n, v) in zip(m, [(f"{ativo} hoje", BRL(S0)), ("Exercício", BRL(K)), ("Vencimento", f"{venc:%d/%m/%Y}"), ("Prêmio", BRL(premio)),
                               ("Volatilidade", f"{vol*100:.1f}%".replace(".", ",")), ("Juros", f"{(math.exp(C.RR)-1)*100:.2f}%".replace(".", ","))]):
        col.metric(n, v)
    st.caption(o["origem"])
    c1, c2, c3, c4 = st.columns(4)
    S = c1.slider(f"Preço de {ativo}", round(S0 * 0.7, 2), round(S0 * 1.3, 2), round(S0, 2), 0.01)
    dia = c2.date_input("Data", value=venc, min_value=hoje, max_value=venc, format="DD/MM/YYYY")
    lado = c3.radio("Você", ["Comprou", "Vendeu"], horizontal=True)
    pago = c4.number_input("Prêmio pago/recebido (R$)", 0.0, 1000.0, premio, 0.01)
    def valor(s, d, v=vol):
        intr = max(s - K, 0) if t == "C" else max(K - s, 0)
        n = pregoes(d, venc)
        return intr if n <= 0 else max(C.bs(t, s, K, n / 252, C.RR, v)["p"], 0.0)
    v = valor(S, dia)
    intr = max(S - K, 0) if t == "C" else max(K - S, 0)
    sg = 1 if lado == "Comprou" else -1
    res = sg * (v - pago)
    k = st.columns(4)
    k[0].metric(f"Em {dia:%d/%m}, a opção valeria", BRL(v), f"lote de 100: {BRL(v*100)}", delta_color="off")
    k[1].metric("Você " + ("ganharia" if res >= 0 else "perderia"), BRL(res), f"{res/pago*100:+.1f}% · lote: {BRL(res*100)}" if pago else None)
    k[2].metric("Já garante", BRL(intr))
    k[3].metric("Tempo que falta", BRL(max(v - intr, 0)))
    xs = [S0 * (0.75 + 0.5 * i / 80) for i in range(81)]
    fig = go.Figure()
    fig.add_scatter(x=xs, y=[valor(x, hoje) for x in xs], name="hoje", line=dict(dash="dash", color="#8a8a8a"))
    fig.add_scatter(x=xs, y=[valor(x, dia) for x in xs], name=f"em {dia:%d/%m}", line=dict(color="#2340C9", width=3))
    fig.add_scatter(x=xs, y=[valor(x, venc) for x in xs], name="no vencimento", line=dict(color="#c0392b"))
    fig.add_hline(y=pago, line_dash="dot", line_color="#d97706", annotation_text="prêmio")
    fig.add_vline(x=S, line_dash="dot", line_color="#666")
    fig.update_layout(height=340, xaxis_title=f"preço de {ativo}", yaxis_title="valor da opção (R$)", margin=dict(l=10, r=10, t=10, b=10))
    st.subheader(f"Quanto a opção vale em cada preço de {ativo}")
    st.plotly_chart(fig, use_container_width=True)
    dias = [hoje + dt.timedelta(days=i) for i in range((venc - hoje).days + 1)]
    dias = [d for d in dias if d == hoje or (d.weekday() < 5 and d not in FER)]
    st.subheader("O tempo come o valor")
    fig2 = go.Figure(go.Scatter(x=dias, y=[valor(S, d) for d in dias], line=dict(color="#2340C9", width=3)))
    fig2.update_layout(height=260, yaxis_title="valor (R$)", margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig2, use_container_width=True)
    st.subheader("A volatilidade")
    vv = st.columns(3)
    for col, x in zip(vv, [vol - 0.1, vol, vol + 0.1]):
        if x > 0.02:
            col.metric(f"{x*100:.1f}%".replace(".", ",") + (" (a de hoje)" if x == vol else ""), BRL(valor(S, dia, x)))
    be = K + pago if t == "C" else K - pago
    st.info(f"Empate no vencimento: **{BRL(be)}**. " + (f"Acima disso a CALL dá lucro para quem comprou." if t == "C" else "Abaixo disso a PUT dá lucro para quem comprou."))
    st.caption("Black-Scholes com dias de bolsa (feriados da B3 descontados) e volatilidade tirada do último prêmio. " + AVISO)

# ---------------- Radar ----------------
elif pagina == "Radar de opções":
    st.title("Radar de opções")
    selo()
    ativo = st.selectbox("Ativo", D.ATIVOS)
    with st.spinner("Buscando opções..."):
        o = D.opcoes(ativo)
    S, du = o["spot"], o["du"]
    T = du / 252
    st.caption(f"{ativo} a {BRL(S)} · vencimento {o['venc']} · {du} pregões · {o['origem']}")
    tipo = st.radio("Tipo", ["CALL", "PUT"], horizontal=True)
    linhas = o["calls"] if tipo == "CALL" else o["puts"]
    t = "C" if tipo == "CALL" else "P"
    so_po = st.checkbox("Só pozinhos (chance de terminar no dinheiro abaixo de 15%)")
    rows = []
    for r in linhas:
        tk, K, p = r[0], r[1], r[2]
        v = C.vol_implicita(t, S, K, T, C.RR, p)
        g = C.bs(t, S, K, T, C.RR, v) if v else None
        itm = g["itm"] if g else (1.0 if (S > K if t == "C" else S < K) else 0.0)
        S10 = S * (1.1 if t == "C" else 0.9)
        mult = (max(S10 - K, 0) if t == "C" else max(K - S10, 0)) / p
        emp = K + p if t == "C" else K - p
        rows.append({"Código": tk, "Strike": K, "Prêmio": p, "Vol. implícita": v * 100 if v else None, "Delta": g["delta"] if g else None,
                     "Empate": emp, "Precisa andar": emp / S - 1, "Chance no dinheiro": itm,
                     "R$ 1 vira (se andar 10%)": mult, "Pozinho": "sim" if itm < 0.15 else ""})
    df = pd.DataFrame(rows)
    if so_po and len(df):
        df = df[df["Pozinho"] == "sim"]
    st.dataframe(df.style.format({"Strike": BRL, "Prêmio": BRL, "Empate": BRL, "Vol. implícita": lambda v: TAXA(v, 0),
                                  "Delta": lambda v: NUM(v, 2), "Precisa andar": PCT, "Chance no dinheiro": lambda v: TAXA(v * 100, 0) if _ok(v) else "—",
                                  "R$ 1 vira (se andar 10%)": lambda v: NUM(v, 1) + "×" if _ok(v) else "—"}),
                 hide_index=True, use_container_width=True)
    st.subheader("Calculadora")
    if len(df):
        esc = st.selectbox("Opção", df["Código"].tolist())
        r = df[df["Código"] == esc].iloc[0]
        lado = st.radio("Operação", ["Comprar", "Vender"], horizontal=True)
        q = st.number_input("Quantidade", 100, 100000, 100, 100)
        pernas = [C.Perna(t, 1 if lado == "Comprar" else -1, float(r["Prêmio"]), float(r["Strike"]), esc)]
        xs = [S * (0.8 + 0.4 * i / 100) for i in range(101)]
        st.plotly_chart(grafico_resultado(xs, [C.resultado(pernas, x) * q for x in xs], S), use_container_width=True)
        st.write(f"{'Custo' if lado=='Comprar' else 'Crédito recebido'}: **{BRL(float(r['Prêmio'])*q)}** · empate em **{BRL(float(r['Empate']))}**")
    st.caption(AVISO)

# ---------------- Estratégias ----------------
elif pagina == "Estratégias com opções":
    st.title("Estratégias com opções: ideias de hoje")
    selo()
    st.write("Ideias geradas com regras explícitas a partir das opções reais das 20 ações mais negociadas. Venda de PUT, venda coberta e financiamento só aparecem quando o prêmio rende mais que a Selic no período.")
    ideias = {e[0]: [] for e in C.ESTRATEGIAS}
    with st.spinner("Lendo as opções das 20 ações..."):
        todas = D.opcoes_todas()
    for a in D.ATIVOS:
        o = todas[a]
        res = C.gerar_ideias(a, o["spot"], [r[:3] for r in o["calls"]], [r[:3] for r in o["puts"]], o["du"], selic)
        for k, v in res.items():
            for it in v:
                it["venc"] = o["venc"]
            ideias[k] += v
    cols = st.columns(4)
    for i, (eid, nome, desc, risco, nivel) in enumerate(C.ESTRATEGIAS):
        with cols[i % 4]:
            st.markdown(f"**{i+1:02d} · {nome}**  \n{desc}  \n`{risco}` `{nivel}`  \n**{len(ideias[eid])} ideias hoje**  \nRisco: {C.rotulo_risco(C.NIVEL_RISCO_ESTR[eid])}")
    escolha = st.selectbox("Ver ideias da estratégia", [e[1] for e in C.ESTRATEGIAS])
    eid = next(e[0] for e in C.ESTRATEGIAS if e[1] == escolha)
    lst = sorted(ideias[eid], key=lambda x: -x["prob"])
    if not lst:
        st.warning("Nenhuma ideia hoje para esta estratégia.")
    else:
        tab = pd.DataFrame([{"Ativo": x["ativo"], "Operação": x["texto"], "Custo(−)/crédito(+)": -x["custo"],
                             "Ganho máximo": x["max"], "Perda máxima": x["min"], "Empate": " / ".join(f"{b:.2f}" for b in x["empate"]),
                             "Prob. de lucro": x["prob"], "Vence": x["venc"]} for x in lst])
        st.dataframe(tab.style.format({"Custo(−)/crédito(+)": BRL, "Ganho máximo": BRL, "Perda máxima": BRL,
                                       "Prob. de lucro": lambda v: TAXA(v * 100, 0) if _ok(v) else "—"}), hide_index=True, use_container_width=True)
        idx = st.selectbox("Ver cenários da ideia", range(len(lst)), format_func=lambda i: f"{lst[i]['ativo']} · {lst[i]['texto'][:90]}")
        it = lst[idx]
        S = it["S"]
        movs = [-0.10, -0.05, -0.02, 0, 0.02, 0.05, 0.10]
        st.table(pd.DataFrame([{f"{m:+.0%}": BRL(C.resultado(it["pernas"], S * (1 + m)) * 100) for m in movs}], index=["Resultado (lote de 100)"]))
        xs = [S * (0.85 + 0.3 * i / 100) for i in range(101)]
        st.plotly_chart(grafico_resultado(xs, [C.resultado(it["pernas"], x) * 100 for x in xs], S), use_container_width=True)
    st.caption("Probabilidade aproximada (log-normal, volatilidade implícita da série). " + AVISO)

# ---------------- Simulador ----------------
elif pagina == "Simulador e melhores ativos":
    st.title("Simulador de investimentos e melhores ativos agora")
    preset = st.selectbox("Cenário", list(C.CENARIOS.keys()), index=1)
    base = dict(C.CENARIOS[preset])
    c1, c2, c3, c4 = st.columns(4)
    valor = c1.number_input("Valor em cada produto (R$)", 100.0, 1e8, 10000.0, 1000.0)
    meses = c2.slider("Prazo (meses)", 1, 60, 12)
    base["se"] = c3.slider("Selic daqui a 12 meses", 6.0, 20.0, float(base["se"]), 0.25)
    base["inf"] = c4.slider("Inflação ao ano", 1.0, 12.0, float(base["inf"]), 0.25)
    c5, c6, c7, c8 = st.columns(4)
    base["dp"] = c5.slider("Juros longos (mudança, p.p.)", -4.0, 4.0, float(base["dp"]), 0.25)
    base["ib"] = c6.slider("Bolsa ao ano (%)", -40, 50, int(base["ib"]))
    base["fx"] = c7.slider("Dólar ao ano (%)", -25, 40, int(base["fx"]))
    base["spx"] = c8.slider("S&P 500 ao ano (%)", -30, 40, int(base["spx"]))
    base["gold"] = st.slider("Ouro em dólar ao ano (%)", -20, 40, int(base["gold"]))
    base["cred"] = 1 if st.checkbox("Calote em crédito privado (desconto de 3%)", value=bool(base["cred"])) else 0
    st.markdown("**Taxas dos produtos** (edite com a oferta que você encontrou)")
    taxas_df = pd.DataFrame([{"Produto": p[1], "Taxa": p[4], "Unidade": p[5]} for p in C.PRODUTOS])
    taxas_df = st.data_editor(taxas_df, hide_index=True, disabled=["Produto", "Unidade"], use_container_width=True, key="taxas")
    taxas = dict(zip(taxas_df["Produto"], taxas_df["Taxa"]))
    res = []
    for p in C.PRODUTOS:
        g = C.fator(p, taxas[p[1]], base, meses, selic)
        n = C.liquido(p, g, meses)
        res.append({"Risco": C.rotulo_risco(C.NIVEL_RISCO[p[0]]), "Produto": p[1], "Grupo": p[2], "Vale no fim": valor * n, "Ganho/perda": valor * (n - 1), "Líquido": n - 1, "Garantia": p[8]})
    out = pd.DataFrame(res)  # já em ordem de risco, do menor para o maior
    st.dataframe(out.style.format({"Vale no fim": BRL, "Ganho/perda": BRL, "Líquido": lambda v: PCT(v)}).map(cor, subset=["Líquido"]),
                 hide_index=True, use_container_width=True)
    sel = st.multiselect("Produtos no gráfico", [p[1] for p in C.PRODUTOS], default=["Tesouro Selic", "CDB de banco médio (2 anos)", "LCI/LCA pós-fixada", "Debênture incentivada", "BOVA11 (Ibovespa)", "Dólar (ETF/fundo cambial)"])
    fig = go.Figure()
    for p in C.PRODUTOS:
        if p[1] in sel:
            fig.add_trace(go.Scatter(x=list(range(meses + 1)), y=[valor * C.liquido(p, C.fator(p, taxas[p[1]], base, k, selic), k) for k in range(meses + 1)], name=p[1]))
    fig.update_layout(height=360, xaxis_title="meses", yaxis_title="R$ (líquido)", margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)

    st.header("Melhores para investir agora (já sem imposto)")
    rk = []
    for p in C.PRODUTOS:
        v = {k: C.liquido(p, C.fator(p, taxas[p[1]], c, meses, selic), meses) - 1 for k, c in C.CENARIOS.items()}
        esp = sum(C.PESOS[k] * x for k, x in v.items())
        rk.append({"nivel": C.NIVEL_RISCO[p[0]], "Risco": C.rotulo_risco(C.NIVEL_RISCO[p[0]]), "Produto": p[1], "Esperado (líquido)": esp, "Em R$": esp * valor, "Pior cenário": min(v.values()),
                   "Melhor cenário": max(v.values()), "nota": esp + 0.5 * min(min(v.values()), 0), "Garantia": p[8]})
    rk = pd.DataFrame(rk).sort_values(["nivel", "nota"], ascending=[True, False])
    melhores = rk.sort_values("nota", ascending=False)["Produto"].tolist()
    rk["Melhor do nível"] = ~rk["nivel"].duplicated()
    rk["Melhor do nível"] = rk["Melhor do nível"].map({True: "★", False: ""})
    rk = rk.drop(columns=["nivel", "nota"])
    st.dataframe(rk.style.format({"Esperado (líquido)": PCT, "Pior cenário": PCT, "Melhor cenário": PCT, "Em R$": BRL}).map(cor, subset=["Esperado (líquido)", "Pior cenário"]),
                 hide_index=True, use_container_width=True)
    st.caption("Em ordem de risco, do menor para o maior. Dentro de cada nível, ★ marca o de melhor retorno esperado (base 40% + os outros quatro cenários 15% cada, punindo quem perde muito no pior cenário).")
    st.subheader("Se os juros subirem ou caírem")
    b0 = C.CENARIOS["Base (Focus)"]
    ds = [-3, -2, -1, 0, 1, 2, 3]
    sens = {}
    for p in C.PRODUTOS:
        sens[p[1]] = [C.liquido(p, C.fator(p, taxas[p[1]], {**b0, "dp": d, "se": b0["se"] + 0.8 * d, "ib": b0["ib"] - 4 * d, "fx": b0["fx"] + 2 * d}, meses, selic), meses) - 1 for d in ds]
    sdf = pd.DataFrame(sens, index=[f"Juros {d:+d} p.p." for d in ds]).T.loc[rk["Produto"]]
    st.dataframe(sdf.style.format(PCT).map(cor), use_container_width=True)
    fig2 = go.Figure()
    for nome in melhores[:8]:
        fig2.add_trace(go.Scatter(x=ds, y=[v * 100 for v in sens[nome]], name=nome))
    fig2.update_layout(height=360, xaxis_title="mudança nos juros (p.p.)", yaxis_title="rendimento líquido (%)", margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig2, use_container_width=True)
    st.caption(AVISO)

# ---------------- Renda fixa e inflação ----------------
elif pagina == "Renda fixa e inflação":
    st.title("Renda fixa e inflação")
    tes, orig_t = D.tesouro()
    foc, orig_foc = D.focus()
    ipca, orig_ipca = D.ipca_mensal()
    st.caption(f"Tesouro: {orig_t} · Focus: {orig_foc} · IPCA: {orig_ipca}")
    td = pd.DataFrame(tes)
    hoje = dt.date.today()
    td["Anos até vencer"] = td["venc"].apply(lambda v: (dt.date.fromisoformat(v) - hoje).days / 365.25)
    td["nivel"] = [C.risco_tesouro(t, a) for t, a in zip(td["tipo"], td["Anos até vencer"])]
    td["Risco"] = td["nivel"].apply(C.rotulo_risco)
    td["_s"] = (td["tipo"] != "S").astype(int)
    td["_p"] = (td["tipo"] != "P").astype(int)
    td = td.sort_values(["_s", "venc", "_p"]).reset_index(drop=True)  # do menor para o maior risco
    st.subheader("Taxas do Tesouro Direto (do menor para o maior risco)")
    tipo_nome = {"S": "Selic (pós)", "P": "Prefixado", "I": "Inflação (IPCA+)"}
    vis = pd.DataFrame({"Risco": td["Risco"], "Título": td["titulo"], "Tipo": td["tipo"].map(tipo_nome), "Vencimento": td["venc"].map(DATA),
                        "Taxa": [("Selic + " if t == "S" else "IPCA + " if t == "I" else "") + TAXA(x) for t, x in zip(td["tipo"], td["taxa"])]})
    st.dataframe(vis, hide_index=True, use_container_width=True, height=420)
    pre = td[(td["tipo"] == "P") & (~td["titulo"].str.contains("Semestrais"))].sort_values("venc")
    ip = td[(td["tipo"] == "I") & (td["titulo"].str.startswith("Tesouro IPCA+ 2")) | (td["titulo"].str.contains("IPCA\\+ 20"))]
    if len(pre) and len(ip):
        p0 = pre.iloc[-1]
        i0 = ip.iloc[(ip["venc"].apply(lambda v: abs((dt.date.fromisoformat(v) - dt.date.fromisoformat(p0["venc"])).days))).argmin()]
        impl = ((1 + p0["taxa"] / 100) / (1 + i0["taxa"] / 100) - 1) * 100
        st.info(f"Inflação implícita ({p0['titulo']} × {i0['titulo']}): **{impl:.2f}% ao ano**. Focus: {', '.join(f'{a}: {v:.2f}%' for a, v in sorted(foc['IPCA'].items()))}.".replace(".", ","))
    st.subheader("Retorno em 12 meses por cenário (antes do IR)")
    linhas = []
    for _, r in td[td["tipo"].isin(["P", "I"]) & (~td["titulo"].str.contains("Semestrais"))].iterrows():
        if r["Anos até vencer"] > 1:
            linhas.append({"Risco": r["Risco"], "Título": r["titulo"], **{k: C.tesouro_retorno(r["tipo"], r["taxa"], r["Anos até vencer"], c) for k, c in C.CENARIOS.items()}})
    if linhas:
        st.dataframe(pd.DataFrame(linhas).style.format({k: PCT for k in C.CENARIOS}).map(cor, subset=list(C.CENARIOS)), hide_index=True, use_container_width=True)
    st.subheader("IPCA mês a mês")
    fig = go.Figure(go.Bar(x=ipca["data"], y=ipca["valor"], marker_color=["#11794A" if v < 0 else "#2340C9" for v in ipca["valor"]]))
    fig.update_layout(height=300, yaxis_title="% no mês", margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)
    st.subheader("Projeções do Focus")
    fdf = pd.DataFrame({"IPCA": foc["IPCA"], "Selic no fim do ano": foc["Selic"]}).sort_index()
    fdf.index = fdf.index.map(str)
    st.dataframe(fdf.style.format(TAXA), use_container_width=True)
    st.caption(AVISO)

# ---------------- Títulos públicos na corretora ----------------
elif pagina == "Títulos públicos na corretora":
    st.title("Títulos públicos na corretora (38)")
    st.caption("LFT = Tesouro Selic · LTN = Prefixado · NTN-F = Prefixado com juros semestrais · NTN-B = IPCA+ com juros semestrais · "
               "Principal = paga tudo no vencimento · NTN-C = IGP-M + juros. Em ordem de risco (nota da corretora, de 0 a 100).")
    idx, orig_idx = D.indexadores()
    c = st.columns(4)
    for col, (k, nome) in zip(c, [("selic12", "Selic"), ("cdi12", "CDI"), ("ipca12", "IPCA"), ("poup12", "Poupança")]):
        col.metric(nome + " (12 meses)", f"{idx[k]:.2f}%".replace(".", ","))
    anb, dia_anb, orig_anb = D.anbima()
    base = D.anbima_base()
    st.caption(f"Indexadores: {orig_idx} · Taxas: {orig_anb}" + (" · taxa de hoje = taxa da corretora em 03/11 + variação na ANBIMA desde então" if anb and base else ""))
    c1, c2, c3 = st.columns(3)
    valor = c1.number_input("Valor em cada título (R$)", 100.0, 10_000_000.0, 10_000.0, 1000.0)
    dj = c2.slider("Se os juros mudarem (p.p.)", -3.0, 3.0, 1.0, 0.25)
    hz = c3.slider("Vendendo depois de (anos)", 0.5, 5.0, 1.0, 0.5)
    filtro = st.radio("Mostrar", ["Todos", "Pós-fixado (LFT)", "Prefixado", "Inflação", "Só os que pagam no vencimento"], horizontal=True)
    hoje = dt.date.today()
    foc, _ = D.focus()
    infl_lp = sum(foc["IPCA"].values()) / len(foc["IPCA"])
    sel_lp = sum(foc["Selic"].values()) / len(foc["Selic"])
    linhas = []
    for nome, tipo, venc, ix, taxa03, _ir, juros, nota, minimo in D.SNAP["corretora"]:
        chave = (tipo.replace(" Principal", ""), venc)
        taxa = taxa03 + (anb[chave][0] - base[chave][0]) if chave in anb and chave in base else taxa03
        anos = (dt.date.fromisoformat(venc) - hoje).days / 365.25
        if anos <= 0:
            continue
        fl = C.fluxo_titulo(tipo, anos)
        dur = 0.02 if ix == "SELIC" else C.duration_titulo(fl, taxa)
        sel_m = (selic + sel_lp) / 2
        an = (1 + sel_m / 100) * (1 + taxa / 100) - 1 if ix == "SELIC" else taxa / 100 if ix == "PRE" else (1 + taxa / 100) * (1 + infl_lp / 100) - 1
        ir = C.ir_prazo(anos)
        liq = ((1 + an) ** anos - 1) * (1 - ir)
        g = C.retorno_titulo(tipo, ix, taxa, anos, 0 if ix == "SELIC" else dj, hz, sel_m, infl_lp)
        g = g * (1 - C.ir_prazo(hz)) if g > 0 else g
        gm = C.retorno_titulo(tipo, ix, taxa, anos, -1, hz, sel_m, infl_lp)
        gp = C.retorno_titulo(tipo, ix, taxa, anos, 1, hz, sel_m, infl_lp)
        linhas.append({"_n": nota, "_d": dur, "Risco": C.rotulo_risco(C.nivel_titulo(nota)) + f" (nota {nota})", "Título": nome, "É o mesmo que": C.NOME_TITULO[tipo],
                       "Vence": venc, "Taxa hoje": taxa, "Taxa 03/11": taxa03, "Indexador": ix, "Juros": juros or "No vencimento",
                       "Mínimo (R$)": minimo * math.exp(-dur * (taxa - taxa03) / 100), "IR no vencimento": ir,
                       "Vira no vencimento (R$, líquido)": valor * (1 + liq), "Líquido ao ano": (1 + liq) ** (1 / anos) - 1,
                       f"Vendendo em {hz:g} ano(s), juros {dj:+g} p.p. (R$)": valor * g, "Juros −1 p.p.": gm, "Juros +1 p.p.": gp})
    df = pd.DataFrame(linhas).sort_values(["_n", "_d"]).drop(columns=["_n", "_d"])
    if filtro == "Pós-fixado (LFT)":
        df = df[df["Indexador"] == "SELIC"]
    elif filtro == "Prefixado":
        df = df[df["Indexador"] == "PRE"]
    elif filtro == "Inflação":
        df = df[df["Indexador"].isin(["IPCA", "IGPM"])]
    elif filtro == "Só os que pagam no vencimento":
        df = df[df["Juros"] == "No vencimento"]
    df["Vence"] = df["Vence"].map(DATA)
    col_v = f"Vendendo em {hz:g} ano(s), juros {dj:+g} p.p. (R$)"
    st.dataframe(df.style.format({"Taxa hoje": lambda v: TAXA(v, 3), "Taxa 03/11": lambda v: TAXA(v, 3), "Mínimo (R$)": BRL, "IR no vencimento": lambda v: TAXA(v * 100, 1),
                                  "Vira no vencimento (R$, líquido)": BRL, "Líquido ao ano": PCT, col_v: lambda v: ("+" if v >= 0 else "") + BRL(v),
                                  "Juros −1 p.p.": PCT, "Juros +1 p.p.": PCT}), hide_index=True, use_container_width=True, height=520)
    st.caption("LFT: a taxa é o ágio/deságio sobre a Selic. IGP-M considerado igual ao IPCA projetado. Cupons reinvestidos na Selic. " + AVISO)

# ---------------- Ações ----------------
elif pagina == "Ações por fundamentos":
    st.title("Ações: fundamentos, setor, ciclo e notícias")
    aba1, aba2 = st.tabs(["Triagem por fundamentos", "Quem ganha com inflação e juros"])
    with aba2:
        import json
        SET = json.loads((Path(__file__).parent / "setores.json").read_text(encoding="utf-8"))
        nomes = dict(SET["cenarios"])
        cen = st.radio("Cenário", list(nomes), format_func=lambda k: nomes[k], horizontal=True, index=1)
        simb = {2: "▲▲ ganha muito", 1: "▲ tende a ganhar", 0: "• neutro", -1: "▼ tende a perder", -2: "▼▼ perde muito"}
        g, p_ = st.columns(2)
        with g:
            st.subheader("Tendem a ganhar")
            for nome, ex, ef in sorted(SET["setores"], key=lambda s: -s[2][cen][0]):
                if ef[cen][0] > 0:
                    st.markdown(f"**{nome}** ({simb[ef[cen][0]]})  \n_{ex}_  \n{ef[cen][1]}")
        with p_:
            st.subheader("Tendem a perder")
            for nome, ex, ef in sorted(SET["setores"], key=lambda s: s[2][cen][0]):
                if ef[cen][0] < 0:
                    st.markdown(f"**{nome}** ({simb[ef[cen][0]]})  \n_{ex}_  \n{ef[cen][1]}")
        mapa = pd.DataFrame({nomes[k]: [s[2][k][0] for s in SET["setores"]] for k in nomes}, index=[s[0] for s in SET["setores"]])
        st.subheader("Mapa setor × cenário")
        st.dataframe(mapa.style.format(lambda v: {2: "▲▲", 1: "▲", 0: "•", -1: "▼", -2: "▼▼"}[v]).map(lambda v: cor(v * 0.1)), use_container_width=True)
        st.caption("Tendências históricas, não regras. " + AVISO)
    with aba1:
        ao_vivo = st.toggle("Buscar fundamentos ao vivo (Yahoo Finance; leva alguns segundos)", value=False)
        rows = []
        for a in D.SNAP["acoes"]:
            tk, nome, setor, pl, pvp, dy, roe, divpl, ciclo, noticia, risco = a
            origem = f"reserva {D.SNAP['data']}"
            if ao_vivo:
                f = D.fundamentos(tk)
                if f and f.get("pl"):
                    pl, pvp, dy, roe = f["pl"], f["pvp"] or pvp, f["dy"] if f["dy"] is not None else dy, f["roe"] or roe
                    origem = "ao vivo"
            s = 0
            if pl and 0 < pl <= 8: s += 2
            elif pl and 0 < pl <= 13: s += 1
            if pvp and pvp < 1: s += 1
            if roe and roe >= 20: s += 2
            elif roe and roe >= 13: s += 1
            if divpl is None or divpl <= 0.8: s += 1
            elif divpl > 1.2: s -= 1
            if dy and dy >= 8: s += 1
            s += 2 if ciclo > 0 else 0
            rv, nv = C.risco_acao(tk, divpl)
            rows.append({"_r": rv, "Risco": C.rotulo_risco(nv), "Ação": tk, "Empresa": nome, "Setor": setor, "Nota": s, "P/L": pl, "P/VP": pvp, "ROE %": roe, "DY %": dy,
                         "Dív.L/PL": divpl, "Ciclo": "favorável" if ciclo > 0 else "neutro", "Notícia": noticia, "Ponto de atenção": risco, "Origem": origem})
        st.caption("Em ordem de risco, da ação que menos oscila para a que mais oscila (beta + dívida). Clique numa coluna para reordenar.")
        tab = pd.DataFrame(rows).sort_values(["_r", "Nota"], ascending=[True, False]).drop(columns="_r")
        st.dataframe(tab.style.format({"P/L": lambda v: NUM(v, 1), "P/VP": lambda v: NUM(v, 2), "ROE %": lambda v: TAXA(v, 1), "DY %": lambda v: TAXA(v, 1),
                                       "Dív.L/PL": lambda v: NUM(v, 2)}), hide_index=True, use_container_width=True, height=560)
        st.caption("Nota de 0 a 12: valuation, rentabilidade, dívida, dividendos e setor no ciclo (juros altos e dólar forte favorecem exportadoras, seguradoras e elétricas). " + AVISO)

# ---------------- Site completo: a página principal, em tela cheia ----------------
else:
    st.markdown("""<style>
    .block-container {padding:0 !important; max-width:100% !important;}
    [data-testid="stMain"] iframe {height:100vh !important; width:100% !important; border:0; display:block;}
    header[data-testid="stHeader"] {background:transparent; height:0;}
    [data-testid="stMain"] [data-testid="stVerticalBlock"] {gap:0;}
    </style>""", unsafe_allow_html=True)
    components.iframe(SITE, height=900, scrolling=True)
    st.stop()  # sem rodapé: o site já tem o aviso

# ---------------- aviso em todas as páginas ----------------
st.divider()
st.caption(AVISO_LEGAL)

# ---------------- atualização automática no pregão ----------------
if auto and pregao and pagina in AO_VIVO:
    aviso = st.empty()
    for falta in range(60, 0, -1):
        aviso.caption(f"Próxima atualização dos preços em {falta} s.")
        time.sleep(1)
    st.rerun()
