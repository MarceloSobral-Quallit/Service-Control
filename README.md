<h1 align="center">Service Control</h1>
<p align="center">Gerenciador de serviços e atalhos para VMware, Fortinet, VirtualBox e OpenVPN no Windows.</p>
<p align="center">
  <img src="https://img.shields.io/badge/versão-1.26.05.26-blue" />
  <img src="https://img.shields.io/badge/plataforma-Windows%2010%2F11%20x64-lightgrey" />
  <img src="https://img.shields.io/badge/PowerShell-5.1%2B-blueviolet" />
  <img src="https://img.shields.io/badge/Python-3.x%20(GUI%20opcional)-yellow" />
  <img src="https://img.shields.io/badge/licença-proprietária-red" />
</p>

> **Aviso:** Este é um projeto proprietário de uso interno da Quallit. Não é permitido copiar, distribuir, modificar ou utilizar este software sem autorização expressa por escrito. Consulte [Licença](#licença).

---

## Sumário

- [O que é](#o-que-é)
- [Funcionalidades](#funcionalidades)
- [Requisitos](#requisitos)
- [Uso rápido](#uso-rápido)
- [Documentação](#documentação)
- [Licença](#licença)
- [Dev Team / Contato](#dev-team--contato)

---

## O que é

Service Control é um conjunto de scripts PowerShell com interface gráfica opcional (Python/Tkinter) para **habilitar e desabilitar completamente** serviços de virtualização e VPN no Windows — VMware, Fortinet, VirtualBox e OpenVPN.

Cada serviço é controlado pelo seu próprio script toggle, que gerencia serviços do Windows e adaptadores de rede virtuais. Os atalhos são instalados em `Menu Iniciar > Programs > Service Control` para uso diário sem precisar abrir o Gerenciador de Serviços.

---

## Funcionalidades

- **Interface gráfica** (`ServiceControl.exe`) — instalador visual com status em tempo real, distribuível como único arquivo standalone
- **Menu PowerShell** (`menu.ps1`) — instala, desinstala e faz manutenção de atalhos via console interativo
- Controla 4 serviços: **VMware**, **Fortinet**, **VirtualBox** e **OpenVPN**
- Gerencia serviços do Windows **e** adaptadores de rede virtuais de cada ferramenta
- Auto-elevação para Administrador (UAC), auto-unblock de scripts, logs por sessão e diários
- Atalhos instalados em `Menu Iniciar > Programs > Service Control` para uso diário sem linha de comando

---

## Requisitos

| Componente           | Versão mínima                   |
|----------------------|---------------------------------|
| Windows              | 10 ou 11 (x64)                  |
| PowerShell           | 5.1 (incluso no Windows 10/11)  |
| Privilégios          | Administrador (auto-elevação)   |
| Python *(GUI build)* | 3.x + `pip install -r requirements.txt` |

---

## Uso rápido

**Interface gráfica:** execute `ServiceControl.exe` como Administrador, selecione os serviços desejados e clique em **Instalar Selecionados**.

**Menu PowerShell:**

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\menu.ps1"
```

Após instalar, os atalhos ficam em `Menu Iniciar > Programs > Service Control`.

> Para instruções completas, parâmetros avançados e solução de problemas, consulte o [Manual de Uso](docs/README.md).

---

## Documentação

| Documento | Conteúdo |
|---|---|
| [docs/README.md](docs/README.md) | Manual de uso: instalação, atalhos, parâmetros, logs, solução de problemas |
| [docs/DEV_PLAYBOOK.md](docs/DEV_PLAYBOOK.md) | Guia técnico: arquitetura, build, convenções, como adicionar serviços |
| [docs/INDEX.md](docs/INDEX.md) | Índice geral da documentação |

---

## Licença

Copyright © 2026 Quallit. Todos os direitos reservados.  
Consulte o arquivo [LICENSE](LICENSE) para os termos completos.

---

## Dev Team / Contato

| Assunto                | Contato                   |
|------------------------|---------------------------|
| Dúvidas técnicas       | desenv@quallit.com.br     |
| Vulnerabilidades       | desenv@quallit.com.br     |
| Autorização de uso     | desenv@quallit.com.br     |
