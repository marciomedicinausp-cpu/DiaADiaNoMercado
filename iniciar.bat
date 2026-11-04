@echo off
cd /d "%~dp0"
echo Instalando/atualizando pacotes (so demora na primeira vez)...
python -m pip install -r requirements.txt
python -m streamlit run app.py
pause
