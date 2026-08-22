# Declaração de Conformidade DICOM — VOXEL Router Desktop

**Produto:** VOXEL ROUTER DESKTOP  
**Versão de referência:** 0.1.0 (pré-homologação)  
**Estado:** declaração técnica inicial; não substitui validação por fabricante.

## Funções previstas

| Papel | Serviço | Estado da base |
|---|---|---|
| Verification SCP | C-ECHO recebido de modalidade autorizada | Implementado no motor base. |
| Storage SCP | C-STORE de SOP Classes de armazenamento negociadas | Implementado no motor base com persistência local e fila. |
| Storage SCU | C-STORE para VOXEL PACS Cloud configurado | Implementado no dispatcher base. |
| MWL SCP | Modality Worklist C-FIND | Arquitetura e esquema de dados preparados; handler completo será entregue na próxima etapa. |

## Associação

O AE Title, porta, Calling AE aceitos, IPs/CIDRs autorizados, timeouts e destino Cloud são configuráveis. O Router não usa valores de produção hardcoded. Associações de origem fora da allowlist devem ser recusadas e auditadas.

## Transfer syntaxes e SOP Classes

A base solicita/suporta contextos de armazenamento providos pelo `pynetdicom`, com sintaxes negociadas. A lista final de SOP Classes deve ser congelada durante homologação por modalidade; a versão produtiva só anunciará contextos que tenham sido validados contra o equipamento.

## Persistência e status

O C-STORE é confirmado com `0x0000` somente após a instância ser persistida em formato DICOM Part 10 e enfileirada transacionalmente. Falhas de validação ou persistência retornam erro DIMSE e geram auditoria/quarentena conforme política configurada.

## Limitações conhecidas

A versão 0.1.0 não deve ser implantada clinicamente sem: MWL C-FIND completo, interface de administração, serviço Windows instalado, certificados/TLS quando aplicável, conformance por fabricante e testes de indisponibilidade/reinicialização.
