# Vigware - Arme/desarme no atendimento operacional

Esta versão adiciona o bloco operacional de conexão/partição dentro do atendimento da ocorrência.

## Regra operacional

- Arme/desarme normal não abre card de ocorrência.
- Arme/desarme normal atualiza o status da conta/partição e aparece no histórico da conta.
- Falhas de arme, como `Sistema NÃO armado`, abrem ocorrência operacional.
- O operador passa a ter botões `Armar` e `Desarmar` no painel de Conexões.

## Importante

A etapa atual registra a solicitação do comando na timeline do Vigware. O envio real para a central/JFL será feito na próxima etapa pelo bridge local autorizado, sem mexer no banco do Active Net e sem alterar a recepção da porta 9800.

## Arquivos alterados

- `backend/app/services/occurrence_service.py`
- `backend/app/services/activenet_importer.py`
- `backend/app/services/seed.py`
- `backend/app/routers/occurrences.py`
- `backend/app/schemas/monitoring.py`
- `frontend/js/api.js`
- `frontend/js/monitoring.js`
- `frontend/css/styles.css`
