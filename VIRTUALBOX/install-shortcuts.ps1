<#
===============================================================================
 VirtualBox Toggle - Instalador de Atalhos
-------------------------------------------------------------------------------
 Cria atalhos no Menu Iniciar (Service Control) que chamam virtualbox-toggle.ps1.

 Parametros:
   -DisableAllNow   Para e desabilita todos os servicos VirtualBox imediatamente.
                    Recomendado na PRIMEIRA execucao.

 Uso:
   powershell.exe -NoProfile -ExecutionPolicy Bypass `
       -File ".\install-shortcuts.ps1" -DisableAllNow
===============================================================================
#>

param(
    [switch]$DisableAllNow
)

# -----------------------------------------------------------------------
# Verificacao de privilegios Admin
# -----------------------------------------------------------------------
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$p  = [Security.Principal.WindowsPrincipal]::new($id)
if (-not $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Host 'ERRO: Este script requer privilegios de Administrador.' -ForegroundColor Red
    Write-Host 'Execute com: Start-Process powershell -Verb RunAs' -ForegroundColor Yellow
    exit 1
}

# -----------------------------------------------------------------------
# Caminhos base
# -----------------------------------------------------------------------
$scriptDir   = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $scriptDir) { $scriptDir = $PSScriptRoot }
$progDataDir = 'C:\ProgramData\ServiceControl\VIRTUALBOX'
$togglePs1   = Join-Path $progDataDir 'virtualbox-toggle.ps1'
$logsDir     = Join-Path $progDataDir 'logs'

# -----------------------------------------------------------------------
# Auto-unblock
# -----------------------------------------------------------------------
Write-Host "Desbloqueando scripts em: $scriptDir" -ForegroundColor Cyan
Get-ChildItem -Path $scriptDir -Filter '*.ps1' -ErrorAction SilentlyContinue | ForEach-Object {
    try {
        Unblock-File -LiteralPath $_.FullName -ErrorAction SilentlyContinue
        Write-Host "  OK: $($_.Name)" -ForegroundColor DarkGray
    } catch {
        Write-Host "  Aviso (nao bloqueado): $($_.Name) - $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

# -----------------------------------------------------------------------
# Copia scripts para ProgramData (instalacao portavel)
# -----------------------------------------------------------------------
Write-Host "`nCopiando scripts para: $progDataDir" -ForegroundColor Cyan
try {
    if (-not (Test-Path $progDataDir)) {
        New-Item -ItemType Directory -Path $progDataDir -Force -ErrorAction Stop | Out-Null
    }
    if (-not (Test-Path $logsDir)) {
        New-Item -ItemType Directory -Path $logsDir -Force -ErrorAction Stop | Out-Null
    }
    Get-ChildItem -Path $scriptDir -Filter '*.ps1' -ErrorAction SilentlyContinue | ForEach-Object {
        Copy-Item -LiteralPath $_.FullName -Destination $progDataDir -Force -ErrorAction Stop
        Write-Host "  Copiado: $($_.Name)" -ForegroundColor DarkGray
    }
    Get-ChildItem -Path $progDataDir -Filter '*.ps1' -ErrorAction SilentlyContinue | ForEach-Object {
        try { Unblock-File -LiteralPath $_.FullName -ErrorAction SilentlyContinue } catch {}
    }
} catch {
    Write-Host "ERRO ao copiar para ProgramData: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# -----------------------------------------------------------------------
# Verifica script principal
# -----------------------------------------------------------------------
if (-not (Test-Path $togglePs1)) {
    Write-Host "ERRO: Arquivo nao encontrado: $togglePs1" -ForegroundColor Red
    Write-Host 'Certifique-se de que virtualbox-toggle.ps1 esta na mesma pasta.' -ForegroundColor Yellow
    exit 1
}

# -----------------------------------------------------------------------
# Pasta de destino dos atalhos (Service Control - sem subpastas por servico)
# -----------------------------------------------------------------------
$startMenu    = [Environment]::GetFolderPath('StartMenu')
$targetFolder = Join-Path $startMenu 'Programs\Service Control'

try {
    New-Item -ItemType Directory -Path $targetFolder -Force -ErrorAction Stop | Out-Null
    Write-Host "Pasta de atalhos: $targetFolder" -ForegroundColor DarkGray
} catch {
    Write-Host "ERRO ao criar pasta de atalhos: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

# -----------------------------------------------------------------------
# Funcao de criacao de atalho
# -----------------------------------------------------------------------
function New-Shortcut {
    param(
        [string]$LnkPath,
        [string]$Target,
        [string]$Arguments = '',
        [string]$IconPath  = 'imageres.dll,77',
        [string]$Desc      = ''
    )
    try {
        $shell = New-Object -ComObject WScript.Shell
        $sc    = $shell.CreateShortcut($LnkPath)
        $sc.TargetPath       = $Target
        if ($Arguments) { $sc.Arguments = $Arguments }
        $sc.WorkingDirectory = $progDataDir
        $sc.IconLocation     = $IconPath
        if ($Desc) { $sc.Description = $Desc }
        $sc.Save()
        Write-Host "  + $(Split-Path -Leaf $LnkPath)" -ForegroundColor Green
    } catch {
        Write-Host "  ERRO ao criar '$(Split-Path -Leaf $LnkPath)': $($_.Exception.Message)" -ForegroundColor Red
    }
}

# -----------------------------------------------------------------------
# Atalhos ENABLE
# -----------------------------------------------------------------------
Write-Host "`nCriando atalhos Enable..." -ForegroundColor Cyan

New-Shortcut `
    -LnkPath   (Join-Path $targetFolder 'VirtualBox - Enable.lnk') `
    -Target    'powershell.exe' `
    -Arguments "-NoProfile -ExecutionPolicy Bypass -File `"$togglePs1`" -Mode Enable -OpenGUI" `
    -Desc      'Habilita servicos e adaptadores VirtualBox e abre interface'

New-Shortcut `
    -LnkPath   (Join-Path $targetFolder 'VirtualBox - Enable (sem abrir GUI).lnk') `
    -Target    'powershell.exe' `
    -Arguments "-NoProfile -ExecutionPolicy Bypass -File `"$togglePs1`" -Mode Enable" `
    -Desc      'Habilita servicos e adaptadores VirtualBox sem abrir interface'

# -----------------------------------------------------------------------
# Atalho DISABLE
# -----------------------------------------------------------------------
Write-Host "`nCriando atalho Disable..." -ForegroundColor Cyan

New-Shortcut `
    -LnkPath   (Join-Path $targetFolder 'VirtualBox - Disable.lnk') `
    -Target    'powershell.exe' `
    -Arguments "-NoProfile -ExecutionPolicy Bypass -File `"$togglePs1`" -Mode Disable" `
    -Desc      'Para e desabilita todos os servicos e adaptadores VirtualBox'

# -----------------------------------------------------------------------
# Atalhos utilitarios
# -----------------------------------------------------------------------
Write-Host "`nCriando atalhos utilitarios..." -ForegroundColor Cyan

if (-not (Test-Path $logsDir)) {
    New-Item -ItemType Directory -Path $logsDir -Force | Out-Null
}

New-Shortcut `
    -LnkPath   (Join-Path $targetFolder 'VirtualBox - Abrir pasta de logs.lnk') `
    -Target    'explorer.exe' `
    -Arguments "`"$logsDir`"" `
    -IconPath  'imageres.dll,3' `
    -Desc      'Abre pasta de logs do VirtualBox Toggle'

# -----------------------------------------------------------------------
# Salva copias dos atalhos em link\ (referencia / redistribuicao)
# -----------------------------------------------------------------------
$linkDir = Join-Path $scriptDir 'link'
if (-not (Test-Path $linkDir)) { New-Item -ItemType Directory -Path $linkDir -Force | Out-Null }
Write-Host "`nSalvando copias em: $linkDir" -ForegroundColor DarkGray
Get-ChildItem -Path $targetFolder -Filter 'VirtualBox - *.lnk' -ErrorAction SilentlyContinue | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $linkDir -Force
    Write-Host "  Link: $($_.Name)" -ForegroundColor DarkGray
}

Write-Host "`nAtalhos criados em:" -ForegroundColor Green
Write-Host "  $targetFolder" -ForegroundColor Green

# -----------------------------------------------------------------------
# Desativa tudo imediatamente (opcao -DisableAllNow)
# -----------------------------------------------------------------------
if ($DisableAllNow) {

    $svcNames = @('vboxdrv', 'VBoxSDS', 'vboxnetflt', 'vboxnetadp')
    $present  = @()
    foreach ($n in $svcNames) {
        $svc = Get-Service -Name $n -ErrorAction SilentlyContinue
        if ($svc) { $present += $svc.Name }
    }

    # Fallback dinamico
    $extra = Get-Service -ErrorAction SilentlyContinue |
             Where-Object { $_.DisplayName -like '*VirtualBox*' -and $present -notcontains $_.Name }
    foreach ($svc in $extra) { $present += $svc.Name }

    # -----------------------------------------------------------------------
    # Desabilita adaptadores ANTES de parar servicos
    # (vboxnetadp nao pode ser parado enquanto o adaptador Host-Only esta ativo)
    # -----------------------------------------------------------------------
    Write-Host "`n--- Desabilitando adaptadores de rede VirtualBox agora... ---" -ForegroundColor Yellow
    $adapters = Get-NetAdapter -IncludeHidden -ErrorAction SilentlyContinue |
                Where-Object { $_.InterfaceDescription -like '*VirtualBox*' -or $_.Name -like '*VirtualBox*' }

    if (-not $adapters) {
        Write-Host "  Nenhum adaptador VirtualBox encontrado." -ForegroundColor DarkGray
    } else {
        foreach ($a in $adapters) {
            if ($a.Status -eq 'Disabled') {
                Write-Host "  Ja desabilitado: $($a.Name) [$($a.InterfaceDescription)]" -ForegroundColor DarkGray
            } else {
                try {
                    Disable-NetAdapter -Name $a.Name -Confirm:$false -ErrorAction Stop
                    Write-Host "  Desabilitado   : $($a.Name) [$($a.InterfaceDescription)]" -ForegroundColor Green
                } catch {
                    Write-Host "  Falha adapter  : $($a.Name) - $($_.Exception.Message)" -ForegroundColor Red
                }
            }
        }
    }

    # Aguarda o driver liberar apos desabilitar os adaptadores
    Start-Sleep -Seconds 2

    if ($present.Count -eq 0) {
        Write-Host "Nenhum servico VirtualBox encontrado para desativar." -ForegroundColor DarkYellow
    } else {
        Write-Host "`n--- Desativando todos os servicos VirtualBox agora... ---" -ForegroundColor Yellow
        # Para na ordem reversa (driver por ultimo)
        [Array]::Reverse($present)
        foreach ($s in $present) {
            $svc = Get-Service -Name $s -ErrorAction SilentlyContinue
            if ($svc -and $svc.Status -ne 'Stopped') {
                try {
                    Stop-Service -Name $s -Force -ErrorAction Stop
                    Write-Host "  Parado    : $s" -ForegroundColor Green
                } catch {
                    Write-Host "  Falha stop: $s - $($_.Exception.Message)" -ForegroundColor Red
                }
            } else {
                Write-Host "  Ja parado : $s" -ForegroundColor DarkGray
            }
            Start-Sleep -Seconds 1
            $out = & sc.exe config $s start= disabled 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  Disabled  : $s" -ForegroundColor Green
            } else {
                Write-Host "  Aviso sc.exe $s : $out" -ForegroundColor Yellow
            }
        }
        Write-Host "Processados: $($present -join ', ')" -ForegroundColor Gray
    }

    Write-Host "`nPronto. Use o atalho 'Enable' quando precisar do VirtualBox." -ForegroundColor Green
}
