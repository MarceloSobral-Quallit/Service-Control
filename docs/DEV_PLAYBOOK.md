# Service Control — DEV Playbook

**Mantenedor:** Quallit Dev Team — desenv@quallit.com.br  
**Versão:** 1.28.05.26

---

## Sumário

- [Arquitetura](#arquitetura)
- [Estrutura de pastas e responsabilidades](#estrutura-de-pastas-e-responsabilidades)
- [Fluxo de instalação e ProgramData](#fluxo-de-instalação-e-programdata)
- [GUI — Detalhes técnicos](#gui--detalhes-técnicos)
- [Build do executável](#build-do-executável)
- [Versionamento](#versionamento)
- [Convenções PowerShell](#convenções-powershell)
- [Como adicionar um novo serviço](#como-adicionar-um-novo-serviço)
- [Decisões de design](#decisões-de-design)

---

## Arquitetura

O projeto é composto por três camadas independentes que podem ser usadas separadamente:

```
┌─────────────────────────────────────────────────────┐
│  Camada 1 — Toggle scripts (PS1)                    │
│  vmware-toggle.ps1, fortinet-toggle.ps1, etc.      │
│  Responsabilidade: controlar serviços + adaptadores │
└───────────────────────┬─────────────────────────────┘
                        │ chamado por
┌───────────────────────▼─────────────────────────────┐
│  Camada 2 — Install scripts (PS1)                   │
│  install-shortcuts.ps1                              │
│  Responsabilidade: copiar toggle para ProgramData   │
│  e criar atalhos no Menu Iniciar                    │
└────────────┬─────────────────────────┬──────────────┘
             │ chamado por             │ chamado por
┌────────────▼──────────┐  ┌──────────▼──────────────┐
│  menu.ps1             │  │  GUI/main.py             │
│  Menu interativo CLI  │  │  Interface Tkinter       │
└───────────────────────┘  └─────────────────────────┘
```

**Ponto-chave:** os atalhos do Menu Iniciar apontam para os scripts em `C:\ProgramData\ServiceControl\<SERVIÇO>\`, não para o local de origem. Isso torna a solução portável — após a instalação, o local original dos scripts (ou do `.exe`) não importa mais.

---

## Estrutura de pastas e responsabilidades

```
Service-Control/
│
├── menu.ps1                    # Orquestra chamadas aos install-shortcuts.ps1
│                               # Gerencia desinstalação e limpeza de legado
│
├── VMWARE/
│   ├── vmware-toggle.ps1       # Lógica de enable/disable: serviços + VMnet
│   ├── install-shortcuts.ps1   # Copia scripts → ProgramData; cria .lnk
│   └── link/                   # Atalhos .lnk de referência (não usados pelo install)
│
├── FORTINET/ | VIRTUALBOX/ | OPENVPN/
│   ├── *-toggle.ps1            # Mesma estrutura de toggle
│   └── install-shortcuts.ps1   # Mesmo padrão de install
│
├── GUI/
│   ├── main.py                 # Entrypoint Tkinter; chama install-shortcuts.ps1
│   ├── requirements.txt        # Dependências Python (pyinstaller>=6.0)
│   └── version_info.txt        # Fonte de verdade da versão da GUI
│
└── tools/
    ├── build_release.py        # Pipeline de build PyInstaller
    ├── build_release.bat       # Wrapper de entrada para o build
    ├── certs/                  # Certificados de assinatura (não versionados)
    └── git/
        └── github_sync.py      # Sincronização com GitHub
```

---

## Fluxo de instalação e ProgramData

O install-script de cada serviço executa sempre os mesmos 5 passos:

1. **Unblock-File** — Remove `Zone.Identifier` de todos os `.ps1` da pasta de origem (scripts baixados da internet são bloqueados pelo Windows por padrão)
2. **Copia para ProgramData** — `Get-ChildItem *.ps1` → `Copy-Item` para `C:\ProgramData\ServiceControl\<SERVIÇO>\`
3. **Cria pasta de atalhos** — `Menu Iniciar > Programs > Service Control`
4. **Cria atalhos `.lnk`** — usando `WScript.Shell.CreateShortcut`, apontando para `powershell.exe -File "<ProgramData>\toggle.ps1" -Mode Enable|Disable`
5. **Registra tarefa de boot** — `Register-ScheduledTask -TaskPath '\ServiceControl\'` com trigger `AtStartup`, Principal `SYSTEM` (RunLevel Highest). Executa `toggle.ps1 -Mode Disable -NoWait` a cada inicialização, garantindo que serviços e adaptadores voltem ao estado `Disabled` após qualquer reboot. O parâmetro `-NoWait` suprime a pausa interativa de 15 s, necessária apenas em execuções manuais.

Os atalhos apontam **sempre** para `ProgramData`, não para a origem. Isso permite que:
- O `.exe` / pasta de scripts seja movido ou deletado após a instalação
- Os atalhos funcionem indefinidamente enquanto o Windows existir

---

## GUI — Detalhes técnicos

### Detecção de caminho (frozen vs. script)

```python
if getattr(sys, "frozen", False):
    # PyInstaller onefile: scripts embarcados extraídos em sys._MEIPASS
    _ROOT_DIR = Path(sys._MEIPASS)
    _EXE_DIR  = Path(sys.executable).resolve().parent   # pasta real do .exe
else:
    # Execução direta: main.py está em GUI/, scripts em ../
    _ROOT_DIR = Path(__file__).resolve().parent.parent
    _EXE_DIR  = _ROOT_DIR

_GUI_LOG_FILE = _EXE_DIR / "ServiceControl_log.txt"
```

`_ROOT_DIR` aponta para os scripts embarcados (leitura); `_EXE_DIR` aponta para onde o `.exe` está em disco (escrita do log). Separação necessária porque `sys._MEIPASS` é um diretório temporário descartado após a execução.

### Como a GUI chama os scripts

```python
script = _ROOT_DIR / svc["dir"] / svc["script"]
# Exemplo (frozen): sys._MEIPASS / "VMWARE" / "install-shortcuts.ps1"

# Força UTF-8 na saída para evitar garbling de mensagens do sistema Windows
ps_call = f'[Console]::OutputEncoding=[System.Text.Encoding]::UTF8; & "{script}"'
if extra_args:
    ps_call += " " + " ".join(extra_args)

cmd = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
       "-Command", ps_call]
proc = subprocess.Popen(cmd, stdout=PIPE, stderr=STDOUT, ...)
```

O wrapper `[Console]::OutputEncoding=UTF8` antes do `&` garante que mensagens do sistema (Stop-Service, sc.exe, etc.) — que saím em CP1252/OEM por padrão — sejam recebidas corretamente pelo Python.

### Gerenciamento de processos

Todos os `Popen` ativos são rastreados em `self._procs: list[subprocess.Popen]`. O método `_on_close()` chama `proc.terminate()` em cada um antes de destruir a janela, evitando processos PowerShell órfãos. O mesmo handler é registrado no `WM_DELETE_WINDOW` (botão `×` da barra de título).

### Versão exibida na saída

Ao iniciar, a GUI escreve `Service Control  v{APP_VERSION}` como primeira linha da área de log (tag `info`). Isso permite identificar a versão exata ao analisar capturas de tela ou logs trazidos pelo usuário.

### Status de instalação

`get_status(svc)` verifica dois critérios:

1. O arquivo toggle existe em `C:\ProgramData\ServiceControl\<SERVIÇO>\`? → scripts copiados
2. Algum `.lnk` do serviço existe em `Menu Iniciar > Service Control`? → atalhos criados

Retorna: `"Instalado"` / `"Parcial (sem atalhos)"` / `"Não instalado"`

---

## Build do executável

### Pré-requisitos

```powershell
cd GUI
pip install -r requirements.txt   # pyinstaller>=6.0
cd ..
```

### Executar o build

```powershell
# A partir da raiz do projeto (Service-Control/)
python tools\build_release.py           # padrão: ambas variantes
python tools\build_release.py both      # explícito — install + portable
python tools\build_release.py install   # somente _install
python tools\build_release.py portable  # somente _portable
# ou via menu interativo:
.\tools\build_menu.bat
```

### O que o pipeline faz (limpeza + Etapa 0 + 3 etapas + limpeza final)

**Limpeza inicial**

Antes de qualquer etapa, remove `GUI/dist/` e `GUI/build/` para garantir que o build parte de um estado limpo, sem artefatos de execuções anteriores.

**Etapa 0 — Verificação de encoding**

Percorre todos os `.ps1` do projeto e avisa (sem bloquear o build) sobre arquivos com caracteres não-ASCII salvos sem UTF-8 BOM — que o PowerShell 5.1 leria incorretamente.

**Etapa 1 — Versão e sync de documentação**

1. Lê a versão atual de `GUI/version_info.txt`
2. Incrementa `Minor` e atualiza `MM/YY` para a data atual
3. Grava nova versão em `GUI/version_info.txt`
4. Sincroniza a versão em todos os arquivos que a referenciam via `re.sub`:

| Arquivo | Padrão atualizado |
|---|---|
| `GUI/main.py` | `APP_VERSION = "x.xx.xx.xx"` |
| `README.md` | badge `versão-x.xx.xx.xx-blue` |
| `docs/README.md` | `**Versão:** x.xx.xx.xx` |
| `docs/DEV_PLAYBOOK.md` | `**Versão:** x.xx.xx.xx` |
| `docs/INDEX.md` | `**Versão:** x.xx.xx.xx` |

**Etapa 2 — PyInstaller (por variante)**

Antes de cada compilação, gera `GUI/exe_version_info.txt` no formato VSVersionInfo com os metadados
visíveis em **Propriedades → Detalhes** do `.exe` no Windows Explorer
(empresa, produto, versão, direitos autorais, idioma). O campo `OriginalFilename` varia por variante.

O pipeline compila duas variantes:

| Variante | Exe gerado | Extra flag |
|---|---|---|
| `install` | `ServiceControl_install.exe` | `--runtime-tmpdir C:\ProgramData\ServiceControl\runtime` |
| `portable` | `ServiceControl_portable.exe` | *(nenhuma — extrai em `%TEMP%` a cada run)* |

Flags comuns a ambas:
- `--onefile --windowed` — executável único sem console
- `--version-file GUI/exe_version_info.txt` — embute metadados no .exe
- `--add-data VMWARE:VMWARE` (e idem para FORTINET, VIRTUALBOX, OPENVPN) — embarca os PS1
- Saída: `GUI/dist/<nome_variante>.exe`

Após cada compilação, o pipeline tenta **assinar** o executável:

| Pré-requisito | Localização |
|---|---|
| Certificado `.pfx` | `tools/certs/quallit_codesign.pfx` (ou `QUALLIT_SIGN_PFX`) |
| Senha do certificado | Variável de ambiente `QUALLIT_SIGN_PASSWORD` |
| URL de timestamp | Variável de ambiente `QUALLIT_SIGN_TIMESTAMP` (padrão: DigiCert) |
| `signtool.exe` | Windows SDK (`C:\Program Files (x86)\Windows Kits\10\bin\...`) ou PATH |

Se qualquer pré-requisito estiver ausente, a assinatura é pulada com aviso e o build continua.
O log de assinatura é gravado em `tools/build_log/signtool/sign.log`.

**Etapa 2.5 — README_TECNICO.md**

Após o executável ser gerado, gera `GUI/dist/README_TECNICO.md` com os metadados do build:

| Campo | Conteúdo |
|---|---|
| Aplicativo | Service Control |
| Versão | sincronizada com `version_info.txt` |
| Empresa | Quallit |
| Data do Build | timestamp da compilação |
| Python | versão do interpretador usado |
| PyInstaller | versão do compilador |
| Plataforma alvo | Windows 10/11 x64 |

Por variante gerada: tipo (`install`/`portable`) + runtime de extração + status de assinatura (CN e Thumbprint se assinado).

Incluído obrigatoriamente em **todos os ZIPs** (RELEASE e BACKUP). Deletado na limpeza final.

**Etapa 3 — ZIPs**

| ZIP | Destino | Conteúdo |
|---|---|---|
| RELEASE | `C:\DESENV\PROJECT_RELEASE\ServiceControl_RELEASE-{ver}-{data}.zip` | `ServiceControl_install.exe` + `ServiceControl_portable.exe` + `README.md` (manual) + `README_TECNICO.md` |
| BACKUP | `C:\DESENV\PROJECT_BACKUP\ServiceControl_BACKUP-{ver}-{data}.zip` | Código-fonte completo (sem artefatos) + `README_TECNICO.md` |

Arquivos excluídos do BACKUP: `dist/`, `build/`, `__pycache__/`, `.git/`, `.specstory/`, `temp/`, `.pyc`, `.spec`, `.pfx`, `tools/git/github_sync.ini`.
O `README_TECNICO.md` está em `dist/` (excluído do rglob), por isso é adicionado explicitamente ao BACKUP.

**Limpeza final**

Após os ZIPs, remove:
- `GUI/build/` — arquivos temporários do PyInstaller
- `GUI/exe_version_info.txt` — arquivo VSVersionInfo gerado para `--version-file`
- `GUI/dist/README_TECNICO.md` — arquivo de metadados do build

`GUI/dist/` é mantida com o executável gerado.

### Scripts embarcados

Os 4 diretórios de serviço são copiados para dentro do `.exe` via `--add-data`. Em tempo de execução, o PyInstaller extrai tudo para `sys._MEIPASS`. A estrutura interna após extração é:

```
sys._MEIPASS/
├── VMWARE/
│   ├── vmware-toggle.ps1
│   └── install-shortcuts.ps1
├── FORTINET/
│   └── ...
├── VIRTUALBOX/
│   └── ...
└── OPENVPN/
    └── ...
```

### Ícone personalizado

Se existir `GUI/assets/icon.ico`, ele é incluído automaticamente no build. Caso contrário, o build prossegue sem ícone.

### Ordem de desativação no VirtualBox (`-DisableAllNow`)

O driver `vboxnetadp` (NDIS miniport) não pode ser parado enquanto o adaptador Host-Only está ativo. Por isso o bloco `-DisableAllNow` de `install-shortcuts.ps1` executa na seguinte ordem:

1. **Desabilita adaptadores** (`Disable-NetAdapter`) com `-IncludeHidden`
2. `Start-Sleep -Seconds 2` — aguarda o kernel liberar o binding
3. **Para e desabilita serviços** (incluindo `vboxnetadp`)

Sem essa ordem, `Stop-Service vboxnetadp` falha com erro de permissão.

### Desabilitação de adaptadores com estado `Not Present`

Quando o modo Disable é chamado (incluindo pela tarefa de boot), os adaptadores virtuais podem estar no estado `Not Present` — o driver de kernel já carregou o device node, mas o serviço user-mode ainda não iniciou (ou foi parado).

`Disable-NetAdapter` não funciona para dispositivos `Not Present`. Por isso os scripts fazem fallback para `Disable-PnpDevice`:

```powershell
if ($a.Status -in 'Not Present', 'NotPresent') {
    $pnp = Get-PnpDevice -ErrorAction SilentlyContinue |
           Where-Object { $_.FriendlyName -eq $a.Name } |
           Select-Object -First 1
    if ($pnp) {
        Disable-PnpDevice -InstanceId $pnp.InstanceId -Confirm:$false -ErrorAction Stop
    }
} else {
    Disable-NetAdapter -Name $a.Name -Confirm:$false -ErrorAction Stop
}
```

`Disable-PnpDevice` grava o estado `Disabled` diretamente no device node do registro, garantindo que o adaptador permaneça desabilitado mesmo após o driver recarregar.

### VMware — Habilitação de adaptadores (Enable)

As NICs virtuais VMnet1 e VMnet8 são criadas pelos serviços VMware. Após iniciar os serviços,
os adaptadores podem demorar vários segundos para sair do estado `Not Present` — tempo
insuficiente para um `Start-Sleep` fixo.

O modo Enable usa polling real (função `Wait-VMwareAdaptersPresent`) com timeout de 30 segundos:

```powershell
function Wait-VMwareAdaptersPresent {
    param([int]$TimeoutSec = 30)
    $deadline = (Get-Date).AddSeconds($TimeoutSec)
    do {
        $still = Get-NetAdapter -IncludeHidden | Where-Object {
            ($_.InterfaceDescription -like '*VMware*' -or $_.Name -like 'VMnet*') -and
            $_.Status -in 'Not Present', 'NotPresent'
        }
        if (-not $still) { return $true }
        Start-Sleep -Seconds 1
    } while ((Get-Date) -lt $deadline)
    return $false
}
```

Ordem do Enable:
1. **Inicia serviços** (VMAuthdService, VMnetDHCP, VMUSBArbService, VMnetBridge, VMware NAT Service)
2. **Aguarda** adaptadores saírem de `Not Present` (polling até 30 s)
3. **Habilita adaptadores** VMnet1 / VMnet8 via `Enable-NetAdapter`

---

## Versionamento

**Formato:** `MAJOR.MINOR.MM.YY`

| Campo | Significado | Exemplo |
|---|---|---|
| `MAJOR` | Versão principal (manual) | `1` |
| `MINOR` | Incrementado a cada build | `00`, `01`, `02`... |
| `MM` | Mês do build (2 dígitos) | `05` |
| `YY` | Ano do build (2 dígitos) | `26` |

**Fonte de verdade:** `GUI/version_info.txt`

A cada build, `build_release.py` propaga a nova versão automaticamente para:

| Arquivo | Campo / padrão |
|---|---|
| `GUI/version_info.txt` | `Versao: x.xx.xx.xx` (fonte primária) |
| `GUI/main.py` | `APP_VERSION = "x.xx.xx.xx"` |
| `README.md` | badge shields.io |
| `docs/README.md` | `**Versão:**` no cabeçalho |
| `docs/DEV_PLAYBOOK.md` | `**Versão:**` no cabeçalho |
| `docs/INDEX.md` | `**Versão:**` no cabeçalho |

O `version_info.txt` da raiz (`Service-Control/version_info.txt`) é atualizado **automaticamente** a cada build — mantido em sincronia com `GUI/version_info.txt` pelo `build_release.py` para que o `github_sync.py` sempre leia a versão correta.

---

## Convenções PowerShell

### Auto-elevação

Todo toggle e install-script implementa auto-elevação no topo:

```powershell
$id = [Security.Principal.WindowsIdentity]::GetCurrent()
$p  = [Security.Principal.WindowsPrincipal]::new($id)
if (-not $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    # Reconstrói argumentos e relança com RunAs
}
```

### Auto-unblock

```powershell
Get-ChildItem -Path $scriptDir -Filter '*.ps1' | ForEach-Object {
    try { Unblock-File -LiteralPath $_.FullName } catch {}
}
```

Executado antes de qualquer outra ação. Essencial para scripts baixados/copiados da internet.

### Aguardar estado real do serviço

Os toggles aguardam confirmação real antes de prosseguir (não confiam que `Stop-Service` é síncrono):

```powershell
# Polling com timeout de ~15 s
for ($i = 0; $i -lt 30; $i++) {
    if ((Get-Service $svc).Status -eq 'Stopped') { break }
    Start-Sleep -Milliseconds 500
}
```

### Criação de atalhos

Todos os atalhos usam `-File` em vez de `-Command`:

```powershell
# CORRETO — sem escaping multi-camada
-Arguments "-NoProfile -ExecutionPolicy Bypass -File `"$togglePs1`" -Mode Enable"

# EVITAR — escaping frágil com caminhos especiais
-Arguments "-Command & { . '$togglePs1' -Mode Enable }"
```

---

## Como adicionar um novo serviço

### 1. Criar a pasta do serviço

```
NOVOSERVICO/
├── novoservico-toggle.ps1
└── install-shortcuts.ps1
```

Copie `install-shortcuts.ps1` de um serviço existente (ex: OPENVPN) e ajuste:
- `$progDataDir` → `'C:\ProgramData\ServiceControl\NOVOSERVICO'`
- `$togglePs1` → `Join-Path $progDataDir 'novoservico-toggle.ps1'`
- Atalhos criados com `New-Shortcut`
- `$bootTaskName` → `'ServiceControl_NovoServico_DisableAdaptersOnBoot'` (deve corresponder ao `boot_task` registrado na GUI)

> **Nota:** `menu.ps1` (opções 11–15) remove apenas os atalhos do Menu Iniciar. A remoção da tarefa de boot é responsabilidade exclusiva da GUI. Certifique-se de que o novo serviço seja registrado na GUI para que a desinstalação funcione corretamente.

### 2. Registrar no `menu.ps1`

```powershell
$services = @(
    # ... entradas existentes ...
    @{ Label = 'NovoServico'; Dir = 'NOVOSERVICO'; Script = 'install-shortcuts.ps1' }
)
```

### 3. Registrar na GUI (`GUI/main.py`)

```python
SERVICES = [
    # ... entradas existentes ...
    {
        "label":     "NovoServico",
        "dir":       "NOVOSERVICO",
        "script":    "install-shortcuts.ps1",
        "toggle":    "novoservico-toggle.ps1",
        "shortcuts": ["NovoServico - Enable.lnk", "NovoServico - Disable.lnk"],
        "boot_task": "ServiceControl_NovoServico_DisableAdaptersOnBoot",
    },
]
```

O campo `boot_task` deve corresponder ao `$bootTaskName` definido no `install-shortcuts.ps1` do serviço. A GUI usa esse valor para remover a tarefa agendada no fluxo de desinstalação.

### 4. Registrar no build (`tools/build_release.py`)

```python
_SERVICE_DIRS = ["VMWARE", "FORTINET", "VIRTUALBOX", "OPENVPN", "NOVOSERVICO"]
```

---

## Decisões de design

### Por que usar Scheduled Task para garantir o estado após reboot?

Quando `Enable` é executado, dois estados são gravados no registro do Windows:
- `StartType = Manual` nos serviços (via `sc.exe config start= demand`)
- Adaptador PnP habilitado (via `Enable-NetAdapter` / `Enable-PnpDevice`)

Após um reboot, os serviços não iniciam (`Manual` não é auto-start), mas o estado PnP do adaptador permanece "habilitado" no registro. Se os serviços fossem iniciados manualmente, os adaptadores voltariam como `Up` imediatamente.

A tarefa de boot resolve isso executando `toggle.ps1 -Mode Disable -NoWait` como `SYSTEM` antes do logon, que:
1. Confirma que os serviços estão `Stopped` e define `StartType = Disabled`
2. Chama `Disable-PnpDevice` nos adaptadores `Not Present` (adaptadores TAP e virtuais cujo driver já carregou) — gravando o estado `Disabled` no registro PnP

Com isso, mesmo após `Enable` + reboot, o estado é previsível: serviços `Disabled`, adaptadores `Disabled` (ou `Not Present` sem possibilidade de iniciar). A re-ativação só é possível executando `Enable` explicitamente.

### Por que copiar scripts para ProgramData?

Os atalhos do Menu Iniciar precisam apontar para um caminho fixo e permanente. Se apontassem diretamente para o local de origem (ex: pasta do projeto ou do `.exe`), mover qualquer arquivo quebraria todos os atalhos. `C:\ProgramData\ServiceControl\` é um caminho estável, independente de onde o instalador foi executado.

### Por que `-File` em vez de `-Command` nos atalhos?

`-Command` exige escaping multi-camada quando o caminho contém espaços ou caracteres especiais, e falha silenciosamente em muitos casos. `-File` recebe o caminho como argumento direto e os parâmetros separados — sem ambiguidade.

### Por que `--onefile` e não `--onedir`?

O usuário final recebe um único `.exe` e não precisa gerenciar uma pasta com dezenas de DLLs. O tempo de extração na primeira execução é desprezível para uso ocasional.

### Por que PyInstaller e não Nuitka?

PyInstaller é mais simples de configurar e mantido ativamente. Nuitka oferece melhor performance, mas este é um instalador de uso ocasional — performance não é um requisito. PyInstaller é suficiente e produz executáveis menores para este caso de uso.
