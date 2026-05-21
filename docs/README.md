# Service Control — Manual de Uso

**Mantenedor:** Quallit Dev Team — desenv@quallit.com.br  
**Versão:** 1.01.05.26  
**Plataforma:** Windows 10 / 11 x64

---

## Sumário

- [O que é](#o-que-é)
- [Pré-requisitos](#pré-requisitos)
- [Instalação — Primeira Execução](#instalação--primeira-execução)
  - [Opção 1 — Interface Gráfica (ServiceControl.exe)](#opção-1--interface-gráfica-servicecontrolexe)
  - [Opção 2 — Menu PowerShell (menu.ps1)](#opção-2--menu-powershell-menups1)
  - [Opção 3 — Script direto por serviço](#opção-3--script-direto-por-serviço)
- [Uso Diário — Atalhos no Menu Iniciar](#uso-diário--atalhos-no-menu-iniciar)
- [Parâmetros avançados](#parâmetros-avançados)
- [Logs](#logs)
- [Verificação e limpeza de atalhos](#verificação-e-limpeza-de-atalhos)
- [Desinstalação](#desinstalação)
- [Solução de Problemas](#solução-de-problemas)

---

## O que é

Service Control gerencia os serviços do Windows e os adaptadores de rede virtuais de quatro ferramentas:

| Serviço    | O que controla                                    |
|------------|---------------------------------------------------|
| VMware     | Serviços VMware + adaptadores VMnet               |
| Fortinet   | Serviços FortiClient/FortiSSL + adaptadores Fortinet |
| VirtualBox | Serviços VirtualBox + adaptadores VBoxNet         |
| OpenVPN    | Serviço OpenVPN + adaptadores TAP                 |

Cada serviço pode ser **habilitado** (inicia serviços + adaptadores) ou **desabilitado** (para serviços + adaptadores e define como `Disabled`). O estado `Disabled` garante que os serviços não consumam recursos na inicialização do Windows.

---

## Pré-requisitos

- Windows 10 ou 11 (x64)
- PowerShell 5.1 ou superior (incluso no Windows 10/11)
- Conta com privilégios de Administrador (o script solicita elevação automaticamente via UAC)
- A ferramenta correspondente instalada no Windows (VMware, Fortinet, VirtualBox, OpenVPN)

---

## Instalação — Primeira Execução

A instalação cria atalhos em `Menu Iniciar > Programs > Service Control` e copia os scripts de controle para `C:\ProgramData\ServiceControl\<SERVIÇO>\`. Após isso, o uso é feito exclusivamente pelos atalhos.

### Opção 1 — Interface Gráfica (ServiceControl.exe)

Recomendada para distribuição para outros usuários. O `.exe` é autossuficiente — não precisa de nenhum arquivo externo.

1. Execute `ServiceControl.exe` como Administrador (ou aceite o UAC ao abrir normalmente)
2. Marque os serviços desejados
3. Marque **"Desativar serviços imediatamente após instalar"** na primeira execução
4. Clique em **Instalar Selecionados**
5. Acompanhe o log na parte inferior da janela

### Opção 2 — Menu PowerShell (menu.ps1)

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\menu.ps1"
```

No menu interativo:

| Opção | Ação |
|---|---|
| 1–4 | Instalar atalhos de um serviço específico |
| 5 | Instalar atalhos de todos os serviços |
| **6–10** | **Instalar + desativar imediatamente (recomendado na 1ª execução)** |
| 11–15 | Desinstalar atalhos |
| 20 | Remover pasta MateWeb (legado) |
| 21 | Verificar atalhos quebrados ou com caminhos antigos |

### Opção 3 — Script direto por serviço

Execute como Administrador, a partir da pasta do serviço:

```powershell
# VMware
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\VMWARE\install-shortcuts-ng.ps1" -DisableAllNow

# Fortinet
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\FORTINET\install-shortcuts.ps1" -DisableAllNow

# VirtualBox
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\VIRTUALBOX\install-shortcuts.ps1" -DisableAllNow

# OpenVPN
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\OPENVPN\install-shortcuts.ps1" -DisableAllNow
```

O parâmetro `-DisableAllNow` para e desabilita todos os serviços imediatamente. Recomendado na primeira execução para partir de um estado limpo.

---

## Uso Diário — Atalhos no Menu Iniciar

Após a instalação, os atalhos ficam em:

```
Menu Iniciar > Programs > Service Control
```

| Atalho | Ação |
|---|---|
| `VMware - Enable (USB+Bridge)` | Habilita VMware completo (USB + Bridge) e abre a interface |
| `VMware - Enable (No USB)` | Habilita VMware sem VMUSBArbService e abre a interface |
| `VMware - Enable (No Bridge)` | Habilita VMware sem VMnetBridge e abre a interface |
| `VMware - Disable` | Para e desabilita todos os serviços e adaptadores VMware |
| `VMware - Abrir pasta de logs` | Abre `C:\ProgramData\ServiceControl\VMWARE\logs\` |
| `Fortinet - Enable` | Habilita FortiClient e abre a interface |
| `Fortinet - Disable` | Para e desabilita todos os serviços Fortinet |
| `VirtualBox - Enable` | Habilita VirtualBox e abre a interface |
| `VirtualBox - Disable` | Para e desabilita todos os serviços VirtualBox |
| `OpenVPN - Enable` | Habilita OpenVPN e abre a interface |
| `OpenVPN - Disable` | Para e desabilita todos os serviços OpenVPN |

> Os atalhos solicitam elevação via UAC automaticamente. Não é necessário abrir o PowerShell como Administrador manualmente.

---

## Parâmetros avançados

Os scripts de toggle aceitam parâmetros adicionais para uso direto (PowerShell Admin):

### VMware (`vmware-toggle-ng.ps1`)

```powershell
.\vmware-toggle-ng.ps1 -Mode Enable
.\vmware-toggle-ng.ps1 -Mode Enable -OpenGUI           # Abre VMware após habilitar
.\vmware-toggle-ng.ps1 -Mode Enable -OpenGUI -NoUSB    # Exclui VMUSBArbService
.\vmware-toggle-ng.ps1 -Mode Enable -OpenGUI -NoBridge # Exclui VMnetBridge
.\vmware-toggle-ng.ps1 -Mode Disable
.\vmware-toggle-ng.ps1 -Mode Disable -LogDir "D:\meus-logs"
```

| Parâmetro | Descrição |
|---|---|
| `-Mode Enable\|Disable` | Obrigatório |
| `-OpenGUI` | Abre VMware Player ou Workstation após habilitar |
| `-NoUSB` | Não gerencia `VMUSBArbService` (driver USB) |
| `-NoBridge` | Não gerencia `VMnetBridge` (rede bridge) |
| `-LogDir <pasta>` | Pasta de logs alternativa |

### VirtualBox (`virtualbox-toggle.ps1`)

```powershell
.\virtualbox-toggle.ps1 -Mode Enable
.\virtualbox-toggle.ps1 -Mode Enable -OpenGUI   # Abre VirtualBox após habilitar
.\virtualbox-toggle.ps1 -Mode Disable
```

### Fortinet (`fortinet-toggle.ps1`) e OpenVPN (`openvpn-toggle.ps1`)

```powershell
.\fortinet-toggle.ps1 -Mode Enable
.\fortinet-toggle.ps1 -Mode Disable

.\openvpn-toggle.ps1 -Mode Enable
.\openvpn-toggle.ps1 -Mode Disable
```

---

## Logs

Os scripts geram dois arquivos de log por execução, em `C:\ProgramData\ServiceControl\<SERVIÇO>\logs\`:

| Arquivo | Conteúdo |
|---|---|
| `YYYY-MM-DD.txt` | Log diário acumulado — útil para histórico |
| `Session-YYYYMMDD-HHMMSS.txt` | Transcript completo de cada execução |

Se a pasta padrão não puder ser criada por falta de permissão, os logs vão automaticamente para `%TEMP%\<serviço>_logs\`.

---

## Verificação e limpeza de atalhos

### Atalhos legados (MateWeb)

Versões anteriores instalavam os atalhos em `Menu Iniciar > Programs > MateWeb`. Para remover:

- **Via menu.ps1:** opção `[20] Remover pasta MateWeb (legado)`
- **Via GUI:** botão **Limpar Legado**

### Atalhos quebrados ou com caminhos antigos

Se os scripts foram movidos de local, os atalhos podem apontar para caminhos inexistentes:

- **Via menu.ps1:** opção `[21] Verificar e limpar atalhos quebrados / caminhos antigos`
- **Via GUI:** botão **Limpar Legado** (verifica ambos automaticamente)

---

## Desinstalação

### Remover atalhos do Menu Iniciar

- **Via menu.ps1:** opções 11–15
- **Via GUI:** selecione os serviços e clique em **Desinstalar Selecionados**
- **Manual:** delete a pasta `%AppData%\Microsoft\Windows\Start Menu\Programs\Service Control`

### Remover scripts instalados (ProgramData)

Os scripts de controle são copiados para `C:\ProgramData\ServiceControl\`. Para remover completamente:

```powershell
Remove-Item -Recurse -Force "C:\ProgramData\ServiceControl"
```

---

## Solução de Problemas

| Sintoma | Causa provável | Solução |
|---|---|---|
| UAC não aparece ao clicar no atalho | Atalho com caminho quebrado | Execute `menu.ps1` opção 21 ou reinstale |
| "Script bloqueado" / execução recusada | `Zone.Identifier` presente | Os scripts executam `Unblock-File` automaticamente; se persistir, execute manualmente: `Unblock-File .\*.ps1` |
| Serviço não inicia após Enable | Serviço desinstalado ou com nome diferente | Verifique o log em `C:\ProgramData\ServiceControl\<SERVIÇO>\logs\` |
| Adaptador de rede não habilita | Driver desinstalado | Reinstale o software (VMware, VirtualBox, etc.) |
| Atalho aponta para caminho antigo (DESENV) | Scripts foram movidos | Use opção 21 do menu.ps1 ou botão Limpar Legado na GUI |
| GUI não abre / fecha imediatamente | Falta de privilégios | Clique com o botão direito no `.exe` > "Executar como administrador" |
