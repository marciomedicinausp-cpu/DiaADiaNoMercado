# Dia a Dia no Mercado

Aplicativo educativo sobre Tesouro Direto, títulos públicos, renda fixa, ações, ETFs e opções no Brasil, com dados públicos buscados ao vivo
(Banco Central, ANBIMA, Tesouro Transparente, opcoes.net.br e Yahoo Finance) e dados de reserva quando alguma fonte não responde.

**Conteúdo educativo. Não é recomendação de investimento.**

## Rodar no computador
```
pip install -r requirements.txt
streamlit run app.py
```

## Publicar no Streamlit Community Cloud
1. Suba estes arquivos para um repositório no GitHub (o `app.py` precisa ficar na raiz).
2. Em https://share.streamlit.io, clique em "Create app", escolha o repositório, a branch `main` e o arquivo `app.py`.
3. Em "Advanced settings", escolha Python 3.12 e clique em "Deploy".
