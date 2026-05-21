:: ─────────────────────────────────────────────────────────────────────────────
:: Service Control  |  Tools  |  build_release.bat
:: Wrapper de entrada para o pipeline de build — executa build_release.py.
::
:: © Quallit — Projeto proprietário. Todos os direitos reservados.
:: ─────────────────────────────────────────────────────────────────────────────
@echo off
cd /d "%~dp0"
python build_release.py
pause
