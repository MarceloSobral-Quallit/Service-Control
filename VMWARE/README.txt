VMware Toggle NG
================================================================================
Controla completamente o VMware no Windows (servicos + adaptadores de rede).
Versao consolidada com todas as melhorias identificadas nas versoes anteriores.

ARQUIVOS
--------
  vmware-toggle-ng.ps1        Script principal (Enable / Disable)
  install-shortcuts-ng.ps1    Instalador de atalhos no Menu Iniciar
  logs\                       Criada automaticamente na primeira execucao

================================================================================
INSTALACAO (primeira vez)
================================================================================

PASSO 1 - Certifique-se de que os dois scripts estao na mesma pasta.
          Exemplo: C:\DESENV\_SCRIPTS\VMWARE\DISABLE_VMWARE_NG\

PASSO 2 - Abra o PowerShell como Administrador:
          [Iniciar] > PowerShell > clique com botao direito > "Executar como administrador"

PASSO 3 - Execute:

    powershell.exe -NoProfile -ExecutionPolicy Bypass `
        -File "<caminho>\VMWARE\install-shortcuts-ng.ps1" `
        -DisableAllNow

          O parametro -DisableAllNow para e desabilita todos os servicos VMware
          imediatamente. Recomendado na PRIMEIRA execucao para partir de um
          estado limpo.

PASSO 4 - Atalhos criados em:
          Menu Iniciar > Programs > Service Control

================================================================================
USO VIA ATALHOS (uso diario)
================================================================================

  VMware - Enable (USB+Bridge)    Habilita tudo + abre VMware Player/Workstation
  VMware - Enable (No USB)        Habilita sem VMUSBArbService + abre VMware
  VMware - Enable (No Bridge)     Habilita sem VMnetBridge + abre VMware
  VMware - Disable                Para e desabilita todos os servicos e adaptadores
  VMware - Abrir pasta de logs    Abre a pasta de logs desta sessao
  VMware - Abrir pasta de scripts Abre a pasta de instalacao

  Os atalhos disparam UAC automaticamente (o script se auto-eleva internamente).

================================================================================
USO DIRETO (PowerShell Admin)
================================================================================

  .\vmware-toggle-ng.ps1 -Mode Enable
  .\vmware-toggle-ng.ps1 -Mode Enable -OpenGUI
  .\vmware-toggle-ng.ps1 -Mode Enable -OpenGUI -NoUSB
  .\vmware-toggle-ng.ps1 -Mode Enable -OpenGUI -NoBridge
  .\vmware-toggle-ng.ps1 -Mode Disable
  .\vmware-toggle-ng.ps1 -Mode Disable -LogDir "D:\meus-logs"

  Parametros:
    -Mode Enable|Disable   Obrigatorio.
    -OpenGUI               Abre o VMware depois de habilitar.
    -NoUSB                 Nao gerencia VMUSBArbService (driver USB).
    -NoBridge              Nao gerencia VMnetBridge (rede bridge).
    -LogDir <pasta>        Pasta de logs customizada.

================================================================================
LOGS
================================================================================

  <scriptDir>\logs\YYYY-MM-DD.txt               Log diario acumulado
  <scriptDir>\logs\Session-YYYYMMDD-HHMMSS.txt  Log completo de cada execucao

  Se a pasta padrao falhar (permissao), os logs vao automaticamente para:
    %TEMP%\vmware_toggle_ng_logs\

================================================================================
MELHORIAS EM RELACAO AS VERSOES ANTERIORES
================================================================================

  [+] ATALHOS COM -File:
      As versoes anteriores usavam -Command com escaping multi-camada para
      abrir a GUI apos o Enable. Isso causava falhas silenciosas se o caminho
      contivesse caracteres especiais. A NG usa -File com o switch -OpenGUI,
      eliminando o problema por completo.

  [+] AUTO-UNBLOCK AUTOMATICO:
      Scripts copiados/baixados da internet recebem um Zone.Identifier que
      faz o Windows bloquea-los mesmo com -ExecutionPolicy Bypass. O script
      executa Unblock-File em todos os .ps1 da pasta antes de qualquer acao.

  [+] DETECCAO DO SERVICO NAT:
      O nome do servico NAT varia entre versoes do VMware:
        - vmnat        (VMware Workstation antigo)
        - VMnetNat     (versoes mais recentes)
      O script testa os dois nomes e usa o DisplayName como fallback final.

  [+] CONTROLE DE ADAPTADORES VMnet:
      Habilita/desabilita as placas de rede virtuais (VMnet*) alem dos servicos.
      Cada adaptador e tratado individualmente com try/catch.

  [+] WAIT-SERVICESTATE (polling real):
      As versoes anteriores confiavam que Stop-Service/Start-Service eram
      sincronos. Na pratica nao sao. A NG aguarda ate 15s confirmando o
      status real do servico antes de prosseguir.

  [+] TRY/CATCH EM TODAS AS OPERACOES:
      Cada Start-Service, Stop-Service e sc.exe tem tratamento de erro
      individual com log detalhado. Uma falha em um servico nao aborta os demais.

  [+] SC.EXE COM CAPTURA DE ERROS:
      Versoes anteriores jogavam a saida do sc.exe para Out-Null. A NG captura
      e loga qualquer erro retornado.

  [+] BUSCA DA GUI EM 4 CAMINHOS:
      Procura vmware.exe e vmplayer.exe tanto em Program Files quanto em
      Program Files (x86), cobrindo instalacoes 32 e 64 bits.

  [+] LOG TRIPLO:
      - Diario (YYYY-MM-DD.txt): acumulado, util para historico
      - Sessao (Session-*.txt): transcript completo da execucao
      - Fallback: se a pasta de logs falhar, usa %TEMP%

  [+] AUTO-ELEVACAO COM FORWARDING CORRETO:
      Switches (-OpenGUI, -NoUSB, -NoBridge) sao repassados corretamente
      ao relancar o proceso elevado.

================================================================================
OBSERVACOES
================================================================================

  - Nenhum servico VMware fica em modo "Automatic". Tudo permanece "Disabled"
    quando nao em uso, e muda para "demand" apenas ao executar Enable.
    Isso garante que o VMware nao consome recursos no boot.

  - Para desinstalar os atalhos, delete a pasta:
    %AppData%\Microsoft\Windows\Start Menu\Programs\Service Control

  - Compativel com VMware Workstation Pro, Workstation Player e versoes
    mais antigas. Testado no Windows 10 e Windows 11.
================================================================================
