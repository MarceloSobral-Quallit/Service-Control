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
echo   4. Build Release - Ambas variantes + Assinar
echo      ^> ServiceControl_install.exe + _portable.exe com assinatura digital
echo.
echo   5. Build Release - Ambas variantes + Assinar + Sync GitHub
echo.
echo   6. Build Dev     - Ambas variantes ^(sem assinatura^)
echo      ^> para testes / desenvolvimento
echo.
echo   7. Build Release - Somente install + Assinar
echo      ^> ServiceControl_install.exe ^(runtime fixo em ProgramData^)
echo.
echo   8. Build Release - Somente portable + Assinar
echo      ^> ServiceControl_portable.exe ^(extracao em %%TEMP%%^)
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
if "%ESCOLHA%"=="6" goto BUILD_NOTSIGN
if "%ESCOLHA%"=="7" goto BUILD_INSTALL
if "%ESCOLHA%"=="8" goto BUILD_PORTABLE
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
echo  Compilando ambas variantes + assinatura...
echo.
python tools\build_release.py both
goto FIM

:BUILD_SYNC
echo.
echo  Compilando ambas variantes + assinatura...
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

:BUILD_NOTSIGN
echo.
echo  Compilando ambas variantes sem assinatura (modo dev)...
echo.
python tools\build_release.py both --no-sign
goto FIM

:BUILD_INSTALL
echo.
echo  Compilando variante install + assinatura...
echo.
python tools\build_release.py install
goto FIM

:BUILD_PORTABLE
echo.
echo  Compilando variante portable + assinatura...
echo.
python tools\build_release.py portable
goto FIM

:FIM
echo.
pause
