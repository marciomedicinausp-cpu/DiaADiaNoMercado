#!/bin/bash
cd "$(dirname "$0")"
echo "Instalando/atualizando pacotes (so demora na primeira vez)..."
python3 -m pip install -r requirements.txt
python3 -m streamlit run app.py
