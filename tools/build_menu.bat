:: ─────────────────────────────────────────────────────────────────────────────
:: Service Control  |  Tools  |  build_menu.bat
:: Menu interativo — sincronizacao GitHub e build da GUI.
::
:: © Quallit — Projeto proprietário. Todos os direitos reservados.
:: ─────────────────────────────────────────────────────────────────────────────
@echo off
chcp 65001 > nul
cd /d "%~dp0.."

:MENU
cls
echo.
echo  ========================================================
echo   Service Control ^| Menu
echo  ========================================================
echo.
echo   --- SINCRONIZACAO ---
echo   1. Sync GitHub
echo      ^> commit + push (tools/git/github_sync.py)
echo.
echo   2. Sync GitHub ^(somente commit, sem push^)
echo      ^> commit local, sem enviar ao GitHub
echo.
echo   3. Verificar alteracoes ^(dry-run^)
echo      ^> mostra o que seria commitado, sem executar
echo.
echo   --- GUI ---
echo   4. Build GUI ^(sem sync^)
echo      ^> gera GUI\dist\ServiceControl.exe
echo.
echo   5. Build GUI + Sync GitHub
echo      ^> compila e envia ao GitHub
echo.
echo   0. Sair
echo.
echo  ========================================================
set /p ESCOLHA="  Opcao: "

if "%ESCOLHA%"=="1" goto SYNC
if "%ESCOLHA%"=="2" goto SYNC_NOPUSH
if "%ESCOLHA%"=="3" goto DRYRUN
if "%ESCOLHA%"=="4" goto BUILD_GUI
if "%ESCOLHA%"=="5" goto BUILD_SYNC
if "%ESCOLHA%"=="6" goto BUILD_INSTALL
if "%ESCOLHA%"=="7" goto BUILD_PORTABLE
if "%ESCOLHA%"=="0" goto FIM
echo  Opcao invalida. Tente novamente.
timeout /t 2 > nul
goto MENU

:SYNC
echo.
echo  Iniciando sincronizacao com GitHub...
echo.
python tools\git\github_sync.py
goto FIM

:SYNC_NOPUSH
echo.
echo  Commit local sem push...
echo.
python tools\git\github_sync.py --no-push
goto FIM

:DRYRUN
echo.
echo  Verificando alteracoes (dry-run)...
echo.
python tools\git\github_sync.py --dry-run
goto FIM

:BUILD_GUI
echo.
echo  Compilando ambas variantes (install + portable)...
echo.
python tools\build_release.py both
goto FIM

:BUILD_SYNC
echo.
echo  Compilando ambas variantes (install + portable)...
echo.
python tools\build_release.py both
if errorlevel 1 (
    echo.
    echo  Build falhou. Sync cancelado.
    goto FIM
)
echo.
echo  Iniciando sincronizacao com GitHub...
echo.
python tools\git\github_sync.py
goto FIM

:BUILD_INSTALL
echo.
echo  Compilando variante install...
echo.
python tools\build_release.py install
goto FIM

:BUILD_PORTABLE
echo.
echo  Compilando variante portable...
echo.
python tools\build_release.py portable
goto FIM

:FIM
echo.
pause
