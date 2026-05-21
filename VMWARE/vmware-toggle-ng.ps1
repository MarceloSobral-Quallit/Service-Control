<#
===============================================================================
 VMware Toggle NG
-------------------------------------------------------------------------------
 Controla completamente o VMware no Windows: servicos + adaptadores de rede.

 Mode Enable:
   1) Desbloqueia scripts da pasta (remove Zone.Identifier)
   2) Habilita adaptadores de rede VMnet
   3) Define servicos como "demand" (start manual)
   4) Inicia servicos VMware
   5) (se -OpenGUI) Abre VMware Player ou Workstation

 Mode Disable:
   1) Para servicos VMware (aguarda confirmacao real de Stopped)
   2) Define servicos como "disabled"
   3) Desabilita adaptadores de rede VMnet

 Parametros:
   -Mode Enable|Disable   (obrigatorio)
   -NoUSB                 Exclui VMUSBArbService
   -NoBridge              Exclui VMnetBridge
   -OpenGUI               Abre VMware apos Enable
   -LogDir                Pasta de logs (padrao: <scriptDir>\logs)

 Requer: Windows PowerShell 5.1+ ou PowerShell 7+
 Admin:  O script auto-eleva para Administrador via RunAs.
===============================================================================
#>

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Enable', 'Disable')]
    [string]$Mode,

    [switch]$NoUSB,
    [switch]$NoBridge,
    [switch]$OpenGUI,

    [string]$LogDir = ''
)

# -----------------------------------------------------------------------
# Caminho real do script (necessario antes de qualquer coisa)
# -----------------------------------------------------------------------
$scriptPath = $MyInvocation.MyCommand.Path
if (-not $scriptPath) { $scriptPath = $PSCommandPath }
$scriptDir  = if ($scriptPath) { Split-Path -Parent $scriptPath } else { Get-Location }

# -----------------------------------------------------------------------
# Auto-unblock: remove Zone.Identifier de todos os .ps1 da pasta
# Impede falhas silenciosas em scripts baixados da internet
# -----------------------------------------------------------------------
Get-ChildItem -Path $scriptDir -Filter '*.ps1' -ErrorAction SilentlyContinue | ForEach-Object {
    try { Unblock-File -LiteralPath $_.FullName -ErrorAction SilentlyContinue } catch {}
}

# -----------------------------------------------------------------------
# Auto-elevacao para Administrador
# Reconstroi parametros e relanca o proprio script com RunAs
# -----------------------------------------------------------------------
function Invoke-SelfElevated {
    param([string]$SelfPath, [hashtable]$BoundParams)

    $id = [Security.Principal.WindowsIdentity]::GetCurrent()
    $p  = [Security.Principal.WindowsPrincipal]::new($id)
    if ($p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) { return }

    $argsList = [System.Collections.Generic.List[string]]::new()
    $argsList.AddRange([string[]]@('-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', "`"$SelfPath`""))

    foreach ($kv in $BoundParams.GetEnumerator()) {
        if ($kv.Value -is [switch]) {
            if ($kv.Value.IsPresent) { $argsList.Add("-$($kv.Key)") }
        } elseif ($kv.Value -and $kv.Value -ne '') {
            $argsList.Add("-$($kv.Key)")
            $argsList.Add("`"$($kv.Value -replace '"', '\"')`"")
        }
    }

    Start-Process -FilePath 'powershell.exe' -ArgumentList $argsList -Verb RunAs
    exit
}
Invoke-SelfElevated -SelfPath $scriptPath -BoundParams $PSBoundParameters

# -----------------------------------------------------------------------
# Configuracao de log
# -----------------------------------------------------------------------
if (-not $LogDir) { $LogDir = Join-Path $scriptDir 'logs' }

try {
    if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
} catch {
    $LogDir = Join-Path $env:TEMP 'vmware_toggle_ng_logs'
    if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
}

$DailyLog = Join-Path $LogDir ('{0:yyyy-MM-dd}.txt'             -f (Get-Date))
$SessLog  = Join-Path $LogDir ('Session-{0:yyyyMMdd-HHmmss}.txt' -f (Get-Date))

try { Start-Transcript -Path $SessLog -Append -ErrorAction SilentlyContinue | Out-Null } catch {}

function Write-Log {
    param(
        [Parameter(Mandatory = $true)][string]$Msg,
        [ValidateSet('Gray', 'Green', 'Red', 'Yellow', 'Cyan', 'DarkGray', 'DarkYellow')]
        [string]$Color = 'Gray'
    )
    $ts   = (Get-Date).ToString('yyyy-MM-dd HH:mm:ss')
    $line = "[$ts] $Msg"
    try { Add-Content -LiteralPath $DailyLog -Value $line -Encoding UTF8 } catch {}
    try {
        $c       = [System.ConsoleColor]$Color
        $hostRaw = $Host.UI.RawUI
        if ($hostRaw) {
            $prev = $hostRaw.ForegroundColor
            $hostRaw.ForegroundColor = $c
            Write-Host $line
            $hostRaw.ForegroundColor = $prev
        } else {
            Write-Output $line
        }
    } catch { Write-Output $line }
}

Write-Log "==== VMWARE $Mode ====" 'Cyan'
Write-Log "Script : $scriptPath"   'DarkGray'
Write-Log "LogDir : $LogDir"       'DarkGray'
Write-Log "Diario : $DailyLog"     'DarkGray'
Write-Log "Sessao : $SessLog"      'DarkGray'
if ($NoUSB)    { Write-Log '-NoUSB    : VMUSBArbService excluido' 'DarkYellow' }
if ($NoBridge) { Write-Log '-NoBridge : VMnetBridge excluido'     'DarkYellow' }

# -----------------------------------------------------------------------
# Deteccao dinamica de servicos VMware
# -----------------------------------------------------------------------
# Ordem importa: Bridge/USB primeiro (dependentes) -> DHCP -> NAT -> Authd

$candidates = [System.Collections.Generic.List[string]]::new()
$candidates.AddRange([string[]]@('VMAuthdService', 'VMnetDHCP', 'VMUSBArbService', 'VMnetBridge'))

# NAT service: o nome varia entre versoes do VMware
# Tenta vmnat, depois VMnetNat, depois busca por DisplayName
$natSvc = Get-Service -Name 'vmnat'    -ErrorAction SilentlyContinue
if (-not $natSvc) { $natSvc = Get-Service -Name 'VMnetNat' -ErrorAction SilentlyContinue }
if (-not $natSvc) {
    $natSvc = Get-Service -ErrorAction SilentlyContinue |
              Where-Object { $_.DisplayName -eq 'VMware NAT Service' } |
              Select-Object -First 1
}
if ($natSvc)   { $candidates.Add($natSvc.Name) }
else           { Write-Log 'NAT service nao encontrado (vmnat / VMnetNat / VMware NAT Service).' 'DarkYellow' }

if ($NoUSB)    { [void]$candidates.Remove('VMUSBArbService') }
if ($NoBridge) { [void]$candidates.Remove('VMnetBridge') }

$present = [System.Collections.Generic.List[string]]::new()
$missing = [System.Collections.Generic.List[string]]::new()
foreach ($n in $candidates) {
    $svc = Get-Service -Name $n -ErrorAction SilentlyContinue
    if ($svc) { $present.Add($svc.Name) } else { $missing.Add($n) }
}

if ($missing.Count -gt 0) {
    Write-Log "Nao encontrados nesta maquina: $($missing -join ', ')" 'DarkYellow'
}
if ($present.Count -eq 0) {
    Write-Log 'Nenhum servico VMware encontrado. Verifique se o VMware esta instalado.' 'Red'
    try { Stop-Transcript | Out-Null } catch {}
    exit 1
}
Write-Log "Servicos detectados: $($present -join ', ')" 'Gray'

# -----------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------

# Aguarda o servico atingir o status desejado (polling real, nao apenas confia no cmdlet)
function Wait-ServiceState {
    param(
        [string]$Name,
        [string]$TargetStatus,
        [int]$TimeoutSec = 15
    )
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    do {
        Start-Sleep -Milliseconds 500
        $s = Get-Service -Name $Name -ErrorAction SilentlyContinue
        if ($s -and ($s.Status -eq $TargetStatus)) { return $true }
    } while ((Get-Date) -lt $deadline)
    return $false
}

# Configura tipo de inicializacao do servico via sc.exe; captura e loga erros
function Set-ServiceStartType {
    param([string]$Name, [string]$StartType)   # StartType: 'demand' ou 'disabled'
    $out = & sc.exe config $Name start= $StartType 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Log "sc.exe config $Name start=$StartType falhou (exit $LASTEXITCODE): $out" 'Yellow'
    }
}

# Habilita ou desabilita adaptadores de rede VMware com try/catch individual
function Toggle-VMwareAdapters {
    param([ValidateSet('Enable', 'Disable')][string]$Action)

    $adapters = Get-NetAdapter -IncludeHidden -ErrorAction SilentlyContinue |
                Where-Object { $_.InterfaceDescription -like '*VMware*' -or $_.Name -like 'VMnet*' }

    if (-not $adapters) {
        Write-Log 'Nenhum adaptador VMware encontrado (normal se VMware nao esta instalado).' 'DarkGray'
        return
    }

    foreach ($a in $adapters) {
        try {
            if ($Action -eq 'Disable' -and $a.Status -ne 'Disabled') {
                Disable-NetAdapter -Name $a.Name -Confirm:$false -ErrorAction Stop
                Write-Log "Adaptador desabilitado : $($a.Name)" 'Green'
            } elseif ($Action -eq 'Enable' -and $a.Status -ne 'Up') {
                if ($a.Status -in 'Not Present', 'NotPresent') {
                    # Enable-NetAdapter nao funciona para 'Not Present'; usa Enable-PnpDevice
                    $pnp = Get-PnpDevice -ErrorAction SilentlyContinue |
                           Where-Object { $_.FriendlyName -eq $a.Name } |
                           Select-Object -First 1
                    if ($pnp) {
                        Enable-PnpDevice -InstanceId $pnp.InstanceId -Confirm:$false -ErrorAction Stop
                        Write-Log "Adaptador habilitado (PnP): $($a.Name)" 'Green'
                    } else {
                        Write-Log "Adaptador PnP nao encontrado: $($a.Name) [$($a.Status)]" 'Yellow'
                    }
                } else {
                    Enable-NetAdapter -Name $a.Name -Confirm:$false -ErrorAction Stop
                    Write-Log "Adaptador habilitado   : $($a.Name)" 'Green'
                }
            } else {
                Write-Log "Adaptador ja OK        : $($a.Name) [$($a.Status)]" 'DarkGray'
            }
        } catch {
            Write-Log "Falha ao $($Action.ToLower()) adaptador '$($a.Name)': $($_.Exception.Message)" 'Red'
        }
    }
}

# -----------------------------------------------------------------------
# MODE: ENABLE
# -----------------------------------------------------------------------
if ($Mode -eq 'Enable') {

    Write-Log '--- [1/3] Iniciando servicos VMware ---' 'Cyan'
    foreach ($s in $present) {
        Set-ServiceStartType -Name $s -StartType 'demand'
        Start-Sleep -Milliseconds 500

        $svc = Get-Service -Name $s -ErrorAction SilentlyContinue
        if (-not $svc) {
            Write-Log "Servico nao encontrado apos config: $s" 'Red'
            continue
        }
        if ($svc.Status -eq 'Running') {
            Write-Log "Ja em execucao: $s" 'DarkGray'
            continue
        }

        try {
            Start-Service -Name $s -ErrorAction Stop
            if (Wait-ServiceState -Name $s -TargetStatus 'Running' -TimeoutSec 15) {
                Write-Log "Iniciado OK: $s" 'Green'
            } else {
                Write-Log "Timeout aguardando Running: $s (pode ainda estar iniciando)" 'Yellow'
            }
        } catch {
            Write-Log "Falha ao iniciar $s : $($_.Exception.Message)" 'Red'
        }
        Start-Sleep -Milliseconds 500
    }

    Write-Log '--- [2/3] Habilitando adaptadores VMware ---' 'Cyan'
    Start-Sleep -Seconds 2  # aguarda servicos inicializarem os dispositivos virtuais
    Toggle-VMwareAdapters -Action Enable

    Write-Log '--- [3/3] VMware habilitado. ---' 'Green'

    if ($OpenGUI) {
        $guiPaths = @(
            'C:\Program Files (x86)\VMware\VMware Workstation\vmware.exe',
            'C:\Program Files\VMware\VMware Workstation\vmware.exe',
            'C:\Program Files (x86)\VMware\VMware Player\vmplayer.exe',
            'C:\Program Files\VMware\VMware Player\vmplayer.exe'
        )
        $gui = $guiPaths | Where-Object { Test-Path $_ } | Select-Object -First 1
        if ($gui) {
            Write-Log "Abrindo VMware: $gui" 'Cyan'
            try { Start-Process -FilePath $gui -ErrorAction Stop }
            catch { Write-Log "Falha ao abrir VMware GUI: $($_.Exception.Message)" 'Red' }
        } else {
            Write-Log 'VMware GUI nao encontrada nos caminhos padrao (Player/Workstation x86/x64).' 'Yellow'
        }
    }
}

# -----------------------------------------------------------------------
# MODE: DISABLE
# -----------------------------------------------------------------------
else {

    Write-Log '--- [1/2] Parando e desabilitando servicos VMware ---' 'Cyan'
    foreach ($s in ($present | Sort-Object -Descending)) {
        $svc = Get-Service -Name $s -ErrorAction SilentlyContinue
        if (-not $svc) {
            Write-Log "Servico nao encontrado: $s" 'DarkYellow'
        } elseif ($svc.Status -eq 'Stopped') {
            Write-Log "Ja parado: $s" 'DarkGray'
        } else {
            try {
                Stop-Service -Name $s -Force -ErrorAction Stop
                if (Wait-ServiceState -Name $s -TargetStatus 'Stopped' -TimeoutSec 15) {
                    Write-Log "Parado OK: $s" 'Green'
                } else {
                    Write-Log "Timeout aguardando Stopped: $s" 'Yellow'
                }
            } catch {
                Write-Log "Falha ao parar $s : $($_.Exception.Message)" 'Red'
            }
        }
        Set-ServiceStartType -Name $s -StartType 'disabled'
        Start-Sleep -Milliseconds 500
    }

    Write-Log '--- [2/2] Desabilitando adaptadores VMware ---' 'Cyan'
    Toggle-VMwareAdapters -Action Disable

    Write-Log '--- VMware desativado. ---' 'Green'
}

Write-Log 'Encerrando em 15 segundos...' 'DarkGray'
Start-Sleep -Seconds 15
try { Stop-Transcript | Out-Null } catch {}
