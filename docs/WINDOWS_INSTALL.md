# VOXEL Router Desktop — build, instalação e teste no Windows

Este procedimento gera um **pacote Windows x64 com os executáveis `VOXELRouterService.exe` e `VOXELRouterDicomTest.exe`**, instala o Router como serviço Windows e executa uma verificação de C-ECHO e C-STORE com um objeto DICOM exclusivamente sintético.

> O teste confirma o funcionamento técnico local do receptor. Ele **não** substitui a homologação DICOM Conformance de cada modalidade/fabricante nem autoriza uso clínico em produção.

| Item | Valor padrão | Finalidade |
|---|---:|---|
| AE Title do Router | `VOXEL_ROUTER` | AE Title chamado pelo emissor DICOM |
| Porta C-STORE | `11112/TCP` | Recebimento de objetos DICOM |
| Porta MWL | `11113/TCP` | Serviço de worklist |
| API local | `127.0.0.1:17841` | Administração local; não é exposta na rede |
| AE Title de teste | `VOXEL_TEST_SCU` | Permitido apenas para o teste sintético inicial |
| Dados operacionais | `C:\ProgramData\VOXEL\Router` | Configuração, banco SQLite, spool, quarentena e logs |

## Opção A — gerar o pacote EXE em um Windows de build

Use esta opção se você baixou/clonou o código e quer criar localmente o pacote para distribuição. É necessário Windows x64, conexão à internet, Git e **Python 3.12 x64** instalado com o Python Launcher (`py`). Abra PowerShell normal e execute:

```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force
git clone https://github.com/andreprogramadorbh-ai/Worklistvoxelpacs-desktop.git
cd .\Worklistvoxelpacs-desktop
.\installer\build.ps1
```

O script cria um ambiente isolado, instala dependências, empacota os executáveis com PyInstaller e gera o arquivo:

```text
dist\windows\VOXELRouterPackage.zip
```

## Opção B — baixar o pacote produzido pela automação

Depois que o workflow **Build Windows installer package** concluir no GitHub Actions, abra a execução, baixe o artefato `VOXELRouterPackage-windows-x64` e extraia `VOXELRouterPackage.zip` em uma pasta local, por exemplo `C:\Temp\VOXELRouterPackage`.

> O artefato de automação fica disponível por 14 dias. Para geração manual, abra a aba **Actions**, selecione o workflow e clique em **Run workflow** na branch `main`.

## Instalar o Router como serviço Windows

Em um PowerShell iniciado com **Executar como administrador**, navegue até a pasta extraída do pacote e execute:

```powershell
Set-ExecutionPolicy -Scope Process Bypass -Force
cd C:\Temp\VOXELRouterPackage
.\install.ps1
```

O instalador copia os binários para `C:\Program Files\VOXEL\Router`, cria a configuração em `C:\ProgramData\VOXEL\Router\config\config.json`, aplica ACL restrita, registra o serviço `VOXELRouterService` com a conta padrão `LocalSystem` e o inicia automaticamente. Por padrão, a allowlist aceita somente o AE de teste `VOXEL_TEST_SCU` a partir de `127.0.0.1`. Em ambiente homologado, a conta `LocalService` pode ser solicitada com o parâmetro `-UseLocalService`, desde que a política local permita essa alteração.

Confirme o estado do serviço:

```powershell
Get-Service VOXELRouterService
```

O resultado esperado contém `Status : Running`.

### Reparo de uma instalação anterior

Se uma versão anterior deixou o serviço parado, use o pacote atualizado e execute o reparo em PowerShell elevado. O comando reinstala o serviço, preserva a configuração existente e executa o teste DICOM sintético ao final:

```powershell
cd C:\\Users\\dedec\\Downloads\\VOXELRouterPackage
.\\repair.ps1
```

## Testar C-ECHO e C-STORE sem dados clínicos

Ainda em PowerShell, execute:

```powershell
cd C:\Temp\VOXELRouterPackage
.\test-reception.ps1
```

O cliente empacotado estabelece uma associação DICOM local, envia C-ECHO e envia um CT mínimo com identificadores `SYNTHETIC-TEST` e `TEST^SYNTHETIC`. Um resultado correto será:

```text
RECEPCAO_DICOM_OK echo=0x0000 store=0x0000 dataset=synthetic
Teste concluído: C-ECHO e C-STORE foram aceitos pelo Router.
```

> No código do Router, o status C-STORE `0x0000` somente é retornado após persistência no spool e registro na fila local. [1]

Os registros de execução ficam em:

```text
C:\ProgramData\VOXEL\Router\logs\router.log
```

## Preparar teste com uma modalidade real em ambiente de homologação

A configuração padrão **não expõe** a porta DICOM à rede nem permite AE Titles de modalidades. Para um teste formal de homologação, obtenha autorização da instituição, defina AE Title/IP/porta não clínicos e execute o instalador com uma allowlist explícita. O exemplo abaixo libera a porta para uma modalidade de teste chamada `CT_HOMOLOG` em `10.20.30.40`:

```powershell
cd C:\Temp\VOXELRouterPackage
.\install.ps1 `
  -RouterAETitle VOXEL_ROUTER `
  -DicomPort 11112 `
  -AllowedCallingAes CT_HOMOLOG `
  -AllowedSourceCidrs 10.20.30.40/32 `
  -OpenFirewallRule `
  -OverwriteConfig
```

Antes de enviar qualquer objeto, confirme todos os itens abaixo.

| Verificação | Condição esperada |
|---|---|
| AE Title chamado | `VOXEL_ROUTER` (ou o valor escolhido na instalação) |
| AE Title chamador | Exatamente presente em `allowed_calling_aes` |
| Origem de rede | IP contemplado em `allowed_source_cidrs` |
| Porta TCP | `11112` acessível somente pela rede homologada |
| Dados enviados | Exclusivamente dataset sintético/anonimizado até a homologação formal |
| Cloud Router | Não configurado até existir destino homologado e credenciais seguras |

Para alterar allowlists ou parâmetros posteriormente, pare o serviço, edite `C:\ProgramData\VOXEL\Router\config\config.json`, valide o JSON e reinicie-o:

```powershell
Stop-Service VOXELRouterService
notepad C:\ProgramData\VOXEL\Router\config\config.json
Start-Service VOXELRouterService
Get-Content C:\ProgramData\VOXEL\Router\logs\router.log -Tail 100
```

## Atualizar e desinstalar

Para atualizar, execute `install.ps1` a partir da nova versão do pacote. A configuração existente é preservada por padrão; use `-OverwriteConfig` apenas quando desejar recriá-la deliberadamente.

Para desinstalar sem apagar a fila, o spool e os logs:

```powershell
cd C:\Temp\VOXELRouterPackage
.\uninstall.ps1
```

A opção abaixo remove permanentemente os dados locais e só deve ser usada após confirmar que não há objetos pendentes ou necessários para auditoria:

```powershell
.\uninstall.ps1 -RemoveData
```

## Solução de problemas

| Sintoma | Ação segura |
|---|---|
| Serviço não inicia | Execute `Get-Content C:\ProgramData\VOXEL\Router\logs\router.log -Tail 200` e confira se as portas 11112/11113 estão livres. |
| C-ECHO/C-STORE recusado | Confirme AE chamado, `allowed_calling_aes` e `allowed_source_cidrs` no `config.json`. |
| Teste sintético não conecta | Verifique `Get-Service VOXELRouterService` e execute `Test-NetConnection 127.0.0.1 -Port 11112`. |
| Modalidade remota não conecta | Confira regra de firewall, rota e allowlist; não remova restrições de origem de forma ampla. |
| Necessidade de reconfigurar | Pare o serviço antes de editar `config.json`; reinicie-o somente após validar o JSON. |

## Referências

[1]: https://github.com/andreprogramadorbh-ai/Worklistvoxelpacs-desktop/blob/main/app/dicom/scp/storage_scp.py "Implementação do Storage SCP"
