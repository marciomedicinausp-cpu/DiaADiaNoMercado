# Dia a Dia no Mercado — versão em Python

Aplicativo que roda no seu computador e **busca os dados ao vivo** (opções, Tesouro Direto, taxas dos títulos públicos na ANBIMA, Focus, IPCA, Selic, CDI, poupança, cotações). O menu está do menor para o maior risco. Se alguma fonte estiver fora do ar, ele usa os dados de reserva de 03/11/2026 (arquivo `snapshot.json`) e avisa na tela qual dado é ao vivo e qual é de reserva.

## Como instalar (uma vez só)

1. Instale o Python 3.10 ou mais novo: https://www.python.org/downloads/  
   No Windows, marque a caixa **"Add Python to PATH"** na primeira tela do instalador.
2. Descompacte esta pasta em qualquer lugar (por exemplo, Documentos).

## Como abrir

- **Windows:** dê dois cliques em `iniciar.bat`.
- **Mac:** clique com o botão direito em `iniciar.command` → Abrir. (Na primeira vez o Mac pode pedir confirmação.)
- **Pelo terminal (qualquer sistema):**
  ```
  pip install -r requirements.txt
  streamlit run app.py
  ```

O navegador abre sozinho em `http://localhost:8501`. Para fechar, feche a janela preta do terminal.

## O que tem dentro

| Página | O que faz |
|---|---|
| Início | Selic, Focus e IPCA do dia, com a origem de cada dado |
| Quanto vale esta opção? | Escolha a opção pelo código e veja quanto ela valeria em cada preço da ação e em cada data até o vencimento, o efeito do tempo e da volatilidade, e o empate |
| Radar de opções | CALLs e PUTs das 20 ações com opções mais negociadas, com volatilidade implícita e probabilidade |
| Estratégias com opções | 8 estratégias (financiamento, venda coberta, venda de PUT, travas, straddle, strangle, compra seca), **do menor para o maior risco**, com ideias geradas a partir dos preços do dia |
| Simulador e melhores ativos | 22 produtos (Tesouro, CDB, LCI/LCA, LCD, LIG, FIDC, CRI/CRA, debêntures, FIIs, ações, dólar, ouro, S&P), **em ordem de risco**, já com IR descontado, em 5 cenários e com a variação se os juros subirem ou caírem |
| Títulos públicos na corretora | Os 38 títulos (LFT, LTN, NTN-F, NTN-B, NTN-C) da sua corretora, em ordem de risco, com a taxa de hoje estimada pela ANBIMA, quanto rendem até o vencimento (já sem IR) e quanto oscilam se os juros mudarem |
| Renda fixa e inflação | Taxas do Tesouro **do menor para o maior risco**, inflação implícita, IPCA mês a mês e projeções do Focus |
| Ações por fundamentos | Triagem por múltiplos **da ação que menos oscila para a que mais oscila**, e a aba "Quem ganha com inflação e juros" por setor |
| Aulas | O site completo com as 35 lições e simuladores |

## Arquivos

- `app.py` — as telas
- `calculos.py` — Black-Scholes, volatilidade implícita, estratégias, produtos, cenários e imposto
- `dados.py` — busca de dados (opcoes.net.br, Yahoo Finance, Tesouro Transparente, Banco Central) com reserva
- `snapshot.json`, `setores.json` — dados de reserva
- `site/escola.html` — o site com as aulas

**Aviso:** é uma ferramenta de estudo, não recomendação de investimento. Confira preços e taxas na sua corretora antes de operar.
