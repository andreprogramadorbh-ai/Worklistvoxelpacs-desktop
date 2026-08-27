# VOXEL Router Desktop — Pacote Visual Windows

O pacote visual instala o **VOXEL Router** como serviço Windows e disponibiliza um painel administrativo local. O recebimento DICOM não depende de a interface estar aberta: após instalado, o serviço `VOXELRouterService` continua ativo em segundo plano e é reiniciado automaticamente pelo Windows em caso de falha.

## Componentes incluídos

| Componente | Finalidade | Local de instalação |
|---|---|---|
| `VOXELRouterSetup.exe` | Instalador gráfico com elevação UAC | Pasta `setup` do pacote extraído |
| `VOXELRouterService.exe` | Serviço Windows, C-STORE, MWL e API local | `C:\Program Files\VOXEL\Router` |
| `VOXELRouterDesktop.exe` | Painel operacional administrativo | `C:\Program Files\VOXEL\Router\desktop` |
| API administrativa local | Fonte de dados do painel, restrita a loopback | `http://127.0.0.1:17841` |
| Dados e logs | Banco SQLite, fila, configuração e logs | `C:\ProgramData\VOXEL\Router` |

## Instalação por interface gráfica

1. Extraia o arquivo `VOXELRouterPackage-visual.zip` em uma pasta local.
2. Abra a subpasta `setup` e execute `VOXELRouterSetup.exe`.
3. Confirme a solicitação do Controle de Conta de Usuário do Windows.
4. Mantenha marcada a abertura das portas **11112** e **11113** se as modalidades forem se conectar por rede.
5. Se já houver configuração homologada, mantenha marcada a opção de preservação da configuração local.
6. Clique em **Instalar e abrir painel**.

O instalador cria o atalho **Menu Iniciar → VOXEL PACS → VOXEL Router Desktop**. O painel também pode ser aberto diretamente em `C:\Program Files\VOXEL\Router\desktop\VOXELRouterDesktop.exe`.

## Operação do painel

| Tela | Dados ou ação disponível |
|---|---|
| Dashboard | Estado da API local e métricas de recebidos, Worklist, modalidades, fila e quarentena |
| Worklist | Itens `SCHEDULED` armazenados no banco local do Router |
| Modalidades | Modalidades cadastradas e o último resultado de C-ECHO |
| Router | Portas locais e ação de reinicialização do serviço Windows |
| Fila | Estado de entregas, tentativas e reprocessamento de itens elegíveis |
| Quarentena | Objetos rejeitados/quarentenados com origem e motivo |
| Logs/Auditoria | Eventos locais operacionais e rastreabilidade resumida |
| Configurações | Parâmetros DICOM, allowlists, destino, API-RIS e PACS/Orthanc |

> O painel consome a API local autenticada por token e restrita a `127.0.0.1`. Nenhuma rota administrativa fica exposta para a rede.

## Configuração segura de integração

### API-RIS

Informe no painel a URL base HTTPS da API-RIS, o identificador único da estação Router e o token Bearer. O token não é gravado em `config.json`; ele é protegido pela DPAPI do Windows em escopo de máquina e pode ser usado pelo serviço Windows sem ser exibido novamente na interface.

O cliente integrado valida os seguintes contratos do Router:

| Operação | Método e caminho esperado |
|---|---|
| Ler configuração atribuída à estação | `GET /api/router/v1/config` |
| Sincronizar itens da Worklist | `GET /api/router/v1/worklist/sync?cursor=…` |
| Publicar eventos operacionais | `POST /api/router/v1/events` |

A API-RIS precisa fornecer esses contratos e autorizar o cabeçalho `Authorization: Bearer <token>` junto com `X-VOXEL-ROUTER-DEVICE`.

### PACS Hetzner / Orthanc

Informe a URL HTTPS do Orthanc, usuário e senha para a API REST. O painel testa `GET /system` com autenticação HTTP Basic e, quando for bem-sucedido, confirma que o endpoint está acessível. A senha também é protegida com DPAPI e nunca é persistida na configuração pública.

O encaminhamento DICOM é configurado separadamente pelos campos **Host PACS DICOM**, **Porta PACS DICOM**, **Called AE PACS** e **TLS DICOM**. A comunicação REST com Orthanc e a associação DICOM não compartilham credenciais.

> Mantenha **Validar certificado TLS** marcado. Desative-o somente em uma homologação controlada, temporária e com certificado privado conhecido.

## Portas de rede

| Porta | Protocolo | Exposição recomendada |
|---|---|---|
| `11112/TCP` | DICOM C-STORE para o Router | Rede clínica privada, apenas origens autorizadas |
| `11113/TCP` | DICOM MWL/C-FIND | Rede clínica privada, apenas modalidades autorizadas |
| `17841/TCP` | API administrativa local | Somente `127.0.0.1`; não criar regra de firewall externa |

## Homologação após instalar

Abra o painel visual e verifique se o Dashboard indica **Serviço ativo** e **API local online**. Em seguida, configure as allowlists de AEs/IPs, a modalidade de teste e os endpoints de RIS/PACS. Para validar somente o receptor local, use o botão **Reparar e testar** do instalador ou execute `test-reception.ps1` a partir da pasta do pacote.

O teste sintético usa `127.0.0.1` e não transmite imagens ou dados clínicos reais. A homologação com a modalidade clínica deve ser feita com uma estação autorizada, uma ordem de teste aprovada e uma revisão dos logs operacionais.
