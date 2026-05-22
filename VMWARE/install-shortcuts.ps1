<#
===============================================================================
 VMware Toggle - Instalador de Atalhos
-------------------------------------------------------------------------------
 Cria atalhos no Menu Iniciar (Service Control) que chamam vmware-toggle.ps1.

 Parametros:
   -DisableAllNow   Para e desabilita todos os servicos VMware imediatamente.
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
$progDataDir = 'C:\ProgramData\ServiceControl\VMWARE'
$togglePs1   = Join-Path $progDataDir 'vmware-toggle.ps1'
$logsDir     = Join-Path $progDataDir 'logs'

# -----------------------------------------------------------------------
# Auto-unblock: remove Zone.Identifier de todos os .ps1
# Essencial para scripts copiados/baixados da internet
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
    Write-Host 'Certifique-se de que vmware-toggle.ps1 esta na mesma pasta.' -ForegroundColor Yellow
    exit 1
}

# -----------------------------------------------------------------------
# Pasta de destino dos atalhos
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
# Atalho ENABLE
# -----------------------------------------------------------------------
Write-Host "`nCriando atalho Enable..." -ForegroundColor Cyan

New-Shortcut `
    -LnkPath   (Join-Path $targetFolder 'VMware - Enable.lnk') `
    -Target    'powershell.exe' `
    -Arguments "-NoProfile -ExecutionPolicy Bypass -File `"$togglePs1`" -Mode Enable -OpenGUI" `
    -Desc      'Habilita VMware completo e abre interface'

# -----------------------------------------------------------------------
# Atalho DISABLE
# -----------------------------------------------------------------------
Write-Host "`nCriando atalho Disable..." -ForegroundColor Cyan

New-Shortcut `
    -LnkPath   (Join-Path $targetFolder 'VMware - Disable.lnk') `
    -Target    'powershell.exe' `
    -Arguments "-NoProfile -ExecutionPolicy Bypass -File `"$togglePs1`" -Mode Disable" `
    -Desc      'Para e desabilita todos os servicos e adaptadores VMware'

# -----------------------------------------------------------------------
# Salva copias dos atalhos em link\ (referencia / redistribuicao)
# -----------------------------------------------------------------------
$linkDir = Join-Path $scriptDir 'link'
if (-not (Test-Path $linkDir)) { New-Item -ItemType Directory -Path $linkDir -Force | Out-Null }
Write-Host "`nSalvando copias em: $linkDir" -ForegroundColor DarkGray
Get-ChildItem -Path $targetFolder -Filter 'VMware - *.lnk' -ErrorAction SilentlyContinue | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $linkDir -Force
    Write-Host "  Link: $($_.Name)" -ForegroundColor DarkGray
}

Write-Host "`nTodos os atalhos criados em:" -ForegroundColor Green
Write-Host "  $targetFolder" -ForegroundColor Green

# -----------------------------------------------------------------------
# Desativa tudo imediatamente (opcao -DisableAllNow)
# Recomendado na primeira execucao para garantir estado limpo
# -----------------------------------------------------------------------
if ($DisableAllNow) {

    Write-Host "`n--- Desativando todos os servicos VMware agora... ---" -ForegroundColor Yellow

    # Mesma logica de deteccao de NAT do toggle principal
    $natSvc = Get-Service -Name 'vmnat'    -ErrorAction SilentlyContinue
    if (-not $natSvc) { $natSvc = Get-Service -Name 'VMnetNat' -ErrorAction SilentlyContinue }
    if (-not $natSvc) {
        $natSvc = Get-Service -ErrorAction SilentlyContinue |
                  Where-Object { $_.DisplayName -eq 'VMware NAT Service' } |
                  Select-Object -First 1
    }

    $svcNames = [System.Collections.Generic.List[string]]::new()
    $svcNames.AddRange([string[]]@('VMAuthdService', 'VMnetDHCP', 'VMUSBArbService', 'VMnetBridge'))
    if ($natSvc) { $svcNames.Add($natSvc.Name) }

    $present = @()
    foreach ($n in $svcNames) {
        $svc = Get-Service -Name $n -ErrorAction SilentlyContinue
        if ($svc) { $present += $svc.Name }
    }

    if ($present.Count -eq 0) {
        Write-Host "Nenhum servico VMware encontrado para desativar." -ForegroundColor DarkYellow
    } else {
        foreach ($s in ($present | Sort-Object -Descending)) {
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
            Start-Sleep -Milliseconds 500
        }
        Write-Host "Processados: $($present -join ', ')" -ForegroundColor Gray
    }

    Write-Host "`n--- Desabilitando adaptadores de rede VMware agora... ---" -ForegroundColor Yellow
    $adapters = Get-NetAdapter -ErrorAction SilentlyContinue |
                Where-Object { $_.InterfaceDescription -like '*VMware*' -or $_.Name -like 'VMnet*' }

    if (-not $adapters) {
        Write-Host "  Nenhum adaptador VMware encontrado." -ForegroundColor DarkGray
    } else {
        foreach ($a in $adapters) {
            if ($a.Status -eq 'Disabled') {
                Write-Host "  Ja desabilitado: $($a.Name)" -ForegroundColor DarkGray
            } else {
                try {
                    Disable-NetAdapter -Name $a.Name -Confirm:$false -ErrorAction Stop
                    Write-Host "  Desabilitado   : $($a.Name)" -ForegroundColor Green
                } catch {
                    Write-Host "  Falha adapter  : $($a.Name) - $($_.Exception.Message)" -ForegroundColor Red
                }
            }
        }
    }

    Write-Host "`nPronto. Use os atalhos 'Enable' quando precisar do VMware." -ForegroundColor Green
}
