# Contrato Cloud Router v1

A API Cloud Router conecta o gateway Windows ao ERP VOXEL sem divulgar credenciais administrativas do Orthanc. Todos os endpoints exigem token de dispositivo rotativo, `device_id`, escopo de tenant/unidade e trilha de auditoria.

| Método | Endpoint | Objetivo |
|---|---|---|
| POST | `/api/router/v1/devices/register` | Parear o Router com tenant, unidade e política aprovada. |
| GET | `/api/router/v1/config` | Obter destinos, allowlists, regras e versão da configuração. |
| GET | `/api/router/v1/worklist/sync?cursor=` | Obter alterações incrementais de worklist para o dispositivo. |
| POST | `/api/router/v1/events` | Registrar eventos idempotentes de MWL, C-STORE, fila, erro e saúde. |

## Regras de segurança

O token deve ser associado ao `device_id`, ter expiração, rotação e revogação administrativa. O ERP deve validar tenant, unidade, permissão do dispositivo, JSON de entrada e `batch_hash` dos eventos. Dados clínicos não devem ser colocados em logs de integração; eventos devem usar identificadores minimizados ou hashes quando possível.

## Resposta padrão

```json
{"success": true, "message": "", "data": {}}
```

Erros retornam `success=false`, uma mensagem segura e HTTP coerente (`401`, `403`, `409`, `422` ou `500`), sem vazar tokens, dados DICOM ou SQL.
