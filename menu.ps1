<#
===============================================================================
 Service Control - Menu Principal
-------------------------------------------------------------------------------
 Gerencia a instalacao e remocao dos atalhos do Menu Iniciar para todos os
 servicos controlados: VMware, Fortinet, VirtualBox e OpenVPN.

 Acoes disponiveis por servico:
   - Instalar atalhos no Menu Iniciar (Programs\Service Control)
   - Instalar atalhos + desativar servico imediatamente (primeira execucao)
   - Desinstalar atalhos do Menu Iniciar

 Uso:
   powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\menu.ps1"

 Requer: Administrador (auto-elevacao via RunAs)
===============================================================================
#>

# -----------------------------------------------------------------------
# Caminho real do script
# -----------------------------------------------------------------------
$scriptPath = $MyInvocation.MyCommand.Path
if (-not $scriptPath) { $scriptPath = $PSCommandPath }
$rootDir = if ($scriptPath) { Split-Path -Parent $scriptPath } else { Get-Location }

# -----------------------------------------------------------------------
# Auto-elevacao para Administrador
# -----------------------------------------------------------------------
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$p  = [Security.Principal.WindowsPrincipal]::new($id)
if (-not $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    $args = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$scriptPath`"")
    Start-Process -FilePath 'powershell.exe' -ArgumentList $args -Verb RunAs
    exit
}

# -----------------------------------------------------------------------
# Definicao dos servicos gerenciados
# Cada entrada: Nome exibido, pasta relativa, arquivo install-shortcuts
# -----------------------------------------------------------------------
$services = @(
    @{ Label = 'VMware';     Dir = 'VMWARE';     Script = 'install-shortcuts-ng.ps1' }
    @{ Label = 'Fortinet';   Dir = 'FORTINET';   Script = 'install-shortcuts.ps1'    }
    @{ Label = 'VirtualBox'; Dir = 'VIRTUALBOX'; Script = 'install-shortcuts.ps1'    }
    @{ Label = 'OpenVPN';    Dir = 'OPENVPN';    Script = 'install-shortcuts.ps1'    }
)

$startMenuFolder = Join-Path ([Environment]::GetFolderPath('StartMenu')) 'Programs\Service Control'

# -----------------------------------------------------------------------
# Helpers de exibicao
# -----------------------------------------------------------------------
function Write-Color {
    param([string]$Text, [System.ConsoleColor]$Color = [System.ConsoleColor]::Gray)
    $prev = $Host.UI.RawUI.ForegroundColor
    $Host.UI.RawUI.ForegroundColor = $Color
    Write-Host $Text
    $Host.UI.RawUI.ForegroundColor = $prev
}

function Show-Header {
    Clear-Host
    Write-Color '===============================================================================' Cyan
    Write-Color '  SERVICE CONTROL - Gerenciador de Atalhos' Cyan
    Write-Color '===============================================================================' Cyan
    Write-Color "  Pasta Menu Iniciar : $startMenuFolder" DarkGray
    Write-Color '' Gray
}

function Show-ShortcutStatus {
    # Mostra quantos atalhos de cada servico existem instalados
    foreach ($svc in $services) {
        $count = 0
        if (Test-Path $startMenuFolder) {
            $count = @(Get-ChildItem -Path $startMenuFolder -Filter "$($svc.Label) - *.lnk" -ErrorAction SilentlyContinue).Count
        }
        $status = if ($count -gt 0) { "[OK] $count atalho(s)" } else { '[ ] nenhum' }
        $color  = if ($count -gt 0) { [System.ConsoleColor]::Green } else { [System.ConsoleColor]::DarkGray }
        $prev = $Host.UI.RawUI.ForegroundColor
        $Host.UI.RawUI.ForegroundColor = $color
        Write-Host ("  {0,-12} : {1}" -f $svc.Label, $status)
        $Host.UI.RawUI.ForegroundColor = $prev
    }
    Write-Host ''
}

function Invoke-InstallScript {
    param([hashtable]$Svc, [switch]$DisableNow)

    $scriptFile = Join-Path $rootDir (Join-Path $Svc.Dir $Svc.Script)

    if (-not (Test-Path $scriptFile)) {
        Write-Color "  ERRO: Script nao encontrado: $scriptFile" Red
        return
    }

    $argsList = @('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$scriptFile`"")
    if ($DisableNow) { $argsList += '-DisableAllNow' }

    Write-Color "  Executando: $scriptFile" DarkGray
    try {
        $proc = Start-Process -FilePath 'powershell.exe' -ArgumentList $argsList `
                              -Verb RunAs -Wait -PassThru -ErrorAction Stop
        if ($proc.ExitCode -eq 0) {
            Write-Color "  Concluido com sucesso." Green
        } else {
            Write-Color "  Concluido com codigo de saida: $($proc.ExitCode)" Yellow
        }
    } catch {
        Write-Color "  Falha ao executar: $($_.Exception.Message)" Red
    }
}

function Remove-ServiceShortcuts {
    param([string]$ServiceLabel)

    if (-not (Test-Path $startMenuFolder)) {
        Write-Color "  Pasta nao existe: $startMenuFolder" DarkGray
        return
    }

    $files = Get-ChildItem -Path $startMenuFolder -Filter "$ServiceLabel - *.lnk" -ErrorAction SilentlyContinue
    if (-not $files -or $files.Count -eq 0) {
        Write-Color "  Nenhum atalho '$ServiceLabel' encontrado para remover." DarkGray
        return
    }

    foreach ($f in $files) {
        try {
            Remove-Item -LiteralPath $f.FullName -Force -ErrorAction Stop
            Write-Color "  Removido: $($f.Name)" Green
        } catch {
            Write-Color "  Falha ao remover '$($f.Name)': $($_.Exception.Message)" Red
        }
    }
}

function Remove-AllShortcuts {
    foreach ($svc in $services) {
        Remove-ServiceShortcuts -ServiceLabel $svc.Label
    }
    # Remove a pasta se ficou vazia
    if (Test-Path $startMenuFolder) {
        $remaining = Get-ChildItem -Path $startMenuFolder -ErrorAction SilentlyContinue
        if (-not $remaining -or $remaining.Count -eq 0) {
            try {
                Remove-Item -LiteralPath $startMenuFolder -Force -ErrorAction Stop
                Write-Color "  Pasta 'Service Control' removida (estava vazia)." DarkGray
            } catch {}
        }
    }
}

function Remove-LegacyMateWeb {
    $startMenu = [Environment]::GetFolderPath('StartMenu')
    $matewebFolder = Join-Path $startMenu 'Programs\MateWeb'

    if (-not (Test-Path $matewebFolder)) {
        Write-Color '  Pasta MateWeb nao encontrada (nenhuma acao necessaria).' DarkGray
        return
    }

    $lnks = @(Get-ChildItem -Path $matewebFolder -Filter '*.lnk' -Recurse -ErrorAction SilentlyContinue)
    Write-Color "  Encontrados $($lnks.Count) atalho(s) em: $matewebFolder" Yellow
    foreach ($f in $lnks) {
        Write-Color "    $($f.Name)" DarkGray
    }
    Write-Host ''
    Write-Color '  Remover toda a pasta MateWeb? [S para confirmar]' Yellow
    $resp = (Read-Host '  ').Trim().ToUpper()
    if ($resp -eq 'S') {
        try {
            Remove-Item -LiteralPath $matewebFolder -Recurse -Force -ErrorAction Stop
            Write-Color '  Pasta MateWeb removida com sucesso.' Green
        } catch {
            Write-Color "  Erro ao remover: $($_.Exception.Message)" Red
        }
    } else {
        Write-Color '  Operacao cancelada.' DarkGray
    }
}

function Test-BrokenShortcuts {
    if (-not (Test-Path $startMenuFolder)) {
        Write-Color '  Pasta Service Control nao existe no Menu Iniciar.' DarkGray
        return
    }

    $oldPaths = @('C:\DESENV\_SCRIPTS', 'C:\DESENV\PROJECT_DESENV')
    $shell    = New-Object -ComObject WScript.Shell
    $broken   = @()
    $oldPath  = @()

    Get-ChildItem -Path $startMenuFolder -Filter '*.lnk' -ErrorAction SilentlyContinue | ForEach-Object {
        $sc     = $shell.CreateShortcut($_.FullName)
        $target = $sc.TargetPath
        $args   = $sc.Arguments
        $isBroken  = $false
        $isOldPath = $false

        if ($target -and -not (Test-Path $target)) { $isBroken = $true }
        foreach ($op in $oldPaths) {
            if ($args -like "*$op*") { $isOldPath = $true }
        }

        if ($isBroken)  { $broken  += $_.FullName }
        if ($isOldPath) { $oldPath += $_.FullName }
    }

    if ($broken.Count -eq 0 -and $oldPath.Count -eq 0) {
        Write-Color '  Nenhum atalho quebrado ou com caminho antigo encontrado.' Green
        return
    }

    if ($broken.Count -gt 0) {
        Write-Color "  $($broken.Count) atalho(s) com alvo inexistente:" Red
        foreach ($f in $broken) { Write-Color "    $(Split-Path -Leaf $f)" DarkGray }
        Write-Host ''
    }
    if ($oldPath.Count -gt 0) {
        Write-Color "  $($oldPath.Count) atalho(s) com caminho legado (DESENV):" Yellow
        foreach ($f in $oldPath) { Write-Color "    $(Split-Path -Leaf $f)" DarkGray }
        Write-Host ''
    }

    $toRemove = ($broken + $oldPath | Select-Object -Unique)
    Write-Color "  Remover os $($toRemove.Count) atalho(s) listados? [S para confirmar]" Yellow
    $resp = (Read-Host '  ').Trim().ToUpper()
    if ($resp -eq 'S') {
        foreach ($f in $toRemove) {
            try {
                Remove-Item -LiteralPath $f -Force -ErrorAction Stop
                Write-Color "  Removido: $(Split-Path -Leaf $f)" Green
            } catch {
                Write-Color "  Erro: $(Split-Path -Leaf $f) - $($_.Exception.Message)" Red
            }
        }
    } else {
        Write-Color '  Operacao cancelada.' DarkGray
    }
}

function Pause-Menu {
    Write-Host ''
    Write-Color '  Pressione qualquer tecla para continuar...' DarkGray
    $null = $Host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')
}

# -----------------------------------------------------------------------
# Loop principal do menu
# -----------------------------------------------------------------------
do {
    Show-Header
    Show-ShortcutStatus

    Write-Color '  --- INSTALAR atalhos ---' Cyan
    Write-Host  '  [1]  VMware      - Instalar atalhos'
    Write-Host  '  [2]  Fortinet    - Instalar atalhos'
    Write-Host  '  [3]  VirtualBox  - Instalar atalhos'
    Write-Host  '  [4]  OpenVPN     - Instalar atalhos'
    Write-Host  '  [5]  INSTALAR TODOS'
    Write-Host  ''
    Write-Color '  --- INSTALAR + DESATIVAR AGORA (1a execucao) ---' Yellow
    Write-Host  '  [6]  VMware      - Instalar + Desativar agora'
    Write-Host  '  [7]  Fortinet    - Instalar + Desativar agora'
    Write-Host  '  [8]  VirtualBox  - Instalar + Desativar agora'
    Write-Host  '  [9]  OpenVPN     - Instalar + Desativar agora'
    Write-Host  '  [10] INSTALAR TODOS + Desativar agora'
    Write-Host  ''
    Write-Color '  --- DESINSTALAR atalhos ---' DarkYellow
    Write-Host  '  [11] VMware      - Desinstalar atalhos'
    Write-Host  '  [12] Fortinet    - Desinstalar atalhos'
    Write-Host  '  [13] VirtualBox  - Desinstalar atalhos'
    Write-Host  '  [14] OpenVPN     - Desinstalar atalhos'
    Write-Host  '  [15] DESINSTALAR TODOS'
    Write-Host  ''
    Write-Color '  --- LIMPEZA / MANUTENCAO ---' Magenta
    Write-Host  '  [20] Remover pasta MateWeb (legado)'
    Write-Host  '  [21] Verificar e limpar atalhos quebrados / caminhos antigos'
    Write-Host  ''
    Write-Color '  [0]  Sair' DarkGray
    Write-Color '-------------------------------------------------------------------------------' DarkGray

    $choice = (Read-Host '  Opcao').Trim()

    Show-Header

    switch ($choice) {
        '1'  { Write-Color '  >> Instalando atalhos: VMware...'     Cyan; Invoke-InstallScript $services[0] }
        '2'  { Write-Color '  >> Instalando atalhos: Fortinet...'   Cyan; Invoke-InstallScript $services[1] }
        '3'  { Write-Color '  >> Instalando atalhos: VirtualBox...' Cyan; Invoke-InstallScript $services[2] }
        '4'  { Write-Color '  >> Instalando atalhos: OpenVPN...'    Cyan; Invoke-InstallScript $services[3] }
        '5'  {
            Write-Color '  >> Instalando atalhos de TODOS os servicos...' Cyan
            foreach ($svc in $services) {
                Write-Color "  -- $($svc.Label) --" Cyan
                Invoke-InstallScript $svc
            }
        }
        '6'  { Write-Color '  >> Instalando + Desativando: VMware...'     Yellow; Invoke-InstallScript $services[0] -DisableNow }
        '7'  { Write-Color '  >> Instalando + Desativando: Fortinet...'   Yellow; Invoke-InstallScript $services[1] -DisableNow }
        '8'  { Write-Color '  >> Instalando + Desativando: VirtualBox...' Yellow; Invoke-InstallScript $services[2] -DisableNow }
        '9'  { Write-Color '  >> Instalando + Desativando: OpenVPN...'    Yellow; Invoke-InstallScript $services[3] -DisableNow }
        '10' {
            Write-Color '  >> Instalando TODOS + Desativando agora...' Yellow
            foreach ($svc in $services) {
                Write-Color "  -- $($svc.Label) --" Yellow
                Invoke-InstallScript $svc -DisableNow
            }
        }
        '11' { Write-Color '  >> Desinstalando atalhos: VMware...'     DarkYellow; Remove-ServiceShortcuts 'VMware'     }
        '12' { Write-Color '  >> Desinstalando atalhos: Fortinet...'   DarkYellow; Remove-ServiceShortcuts 'Fortinet'   }
        '13' { Write-Color '  >> Desinstalando atalhos: VirtualBox...' DarkYellow; Remove-ServiceShortcuts 'VirtualBox' }
        '14' { Write-Color '  >> Desinstalando atalhos: OpenVPN...'    DarkYellow; Remove-ServiceShortcuts 'OpenVPN'    }
        '15' { Write-Color '  >> Desinstalando TODOS os atalhos...'    DarkYellow; Remove-AllShortcuts }
        '20' { Write-Color '  >> Removendo pasta MateWeb (legado)...'         Magenta; Remove-LegacyMateWeb     }
        '21' { Write-Color '  >> Verificando atalhos quebrados / caminhos antigos...' Magenta; Test-BrokenShortcuts }
        '0'  { break }
        default {
            Write-Color '  Opcao invalida.' Red
        }
    }

    if ($choice -ne '0') { Pause-Menu }

} while ($choice -ne '0')

Write-Color '  Service Control encerrado.' DarkGray
