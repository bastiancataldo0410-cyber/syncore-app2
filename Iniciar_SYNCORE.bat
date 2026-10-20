@echo off
title SYNCORE - P6 Subsystem Control
echo Iniciando servidor ejecutivo SYNCORE...
cd /d "%~dp0"
python -m streamlit run app.py
pause