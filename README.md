# VOXEL ROUTER DESKTOP

> **DICOM Gateway & Modality Worklist**

O VOXEL Router Desktop é o componente local do ecossistema VOXEL PACS destinado a clínicas e serviços de diagnóstico por imagem. Ele disponibiliza MWL, recebe objetos DICOM por C-STORE, registra-os em spool local durável, mantém uma fila offline e encaminha instâncias ao VOXEL PACS Cloud.

## Estado atual

A versão `0.1.0` estabelece a base de engenharia do produto: configuração centralizada, banco SQLite com migrations, spool atômico, deduplicação por SOP Instance UID/hash, fila persistente com retry, Storage SCP, C-ECHO, API local em loopback e testes automatizados do núcleo.

A operação clínica exige homologação de DICOM Conformance por modalidade e fabricante antes de qualquer uso em produção. A interface PySide6, o serviço Windows instalável, a sincronização Cloud Router v1, o MWL SCP completo e o instalador profissional seguem como módulos da implementação planejada.

## Princípios de segurança

O projeto não grava senhas em código, não versiona dados clínicos, spool, banco ou logs. A confirmação de C-STORE só ocorre após persistência local atômica e registro transacional da fila. O Router não altera datasets silenciosamente.

## Desenvolvimento

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
pytest
```

Em Windows, o serviço deve ser executado com uma conta de serviço dedicada e `C:\ProgramData\VOXEL\Router` deve receber ACL restrita. Para o Cloud, configure sempre um destino homologado; não há host, porta, AE Title ou credencial clínica hardcoded.

## Estrutura

A organização de módulos separa DICOM, fila, banco, API local, segurança e interface. Consulte `docs/ARCHITECTURE.md` e `docs/DICOM_CONFORMANCE.md` antes de implementar ou homologar integrações.

## Licença e dados clínicos

Código e documentação podem ser versionados. Arquivos DICOM, bancos SQLite, segredos e exportações são explicitamente ignorados pelo Git.
