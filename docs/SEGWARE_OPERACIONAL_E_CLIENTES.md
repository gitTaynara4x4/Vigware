# Vigware - Tela operacional estilo Segware + clientes Active Net

Esta versão faz duas mudanças principais:

1. A tela de monitoramento fica compacta/escura, no padrão operacional de central.
2. O bridge passa a sincronizar contas/clientes do Active Net usando leitura somente `SELECT` no PostgreSQL local.

## Segurança

O bridge **não altera** a porta `9800`, não reinicia o Active Net e não grava no banco local da JFL.

Fluxo:

```text
Centrais/JFL
↓
Active Net recebe normal na porta 9800
↓
Active Net salva em PostgreSQL local
↓
Vigware Bridge lê active_net.eventos em modo readonly
↓
Vigware Cloud recebe com HMAC
↓
Tela operacional mostra ocorrência
```

## Config do bridge

No PC do Active Net, `bridge/config.json` deve ter:

```json
{
  "vigware_base_url": "https://apps-vigware.9ywrah.easypanel.host",
  "source_mode": "database",
  "auth_mode": "hmac",
  "bridge_id": "activenet-matriz",
  "bridge_secret": "A_MESMA_CHAVE_DO_EASYPANEL",
  "active_net_pg_host": "127.0.0.1",
  "active_net_pg_port": 5433,
  "active_net_pg_database": "postgres",
  "active_net_pg_user": "postgres",
  "active_net_pg_password": "",
  "active_net_pg_schema": "active_net",
  "active_net_events_table": "eventos",
  "active_net_last_id_file": "state.json",
  "poll_seconds": 2,
  "batch_size": 100,
  "initial_position": "latest",
  "sync_accounts_on_start": true,
  "sync_accounts_every_seconds": 600,
  "sync_accounts_limit": 5000
}
```

## Regras operacionais

- `1250` Falha de keep alive → abre em **Observação**.
- `3250` Restauração de keep alive → fecha ocorrência `1250` ativa da mesma conta.
- Eventos de teste/arme/desarme seguem como histórico, sem card operacional.
- Eventos críticos entram em **Novos**.

## Interface

A tela foi simplificada para 4 filas:

- Novos
- Iniciado
- Deslocamento
- Observação

Os cards mostram:

- nome do cliente/local;
- conta e partição;
- ícone do tipo de evento;
- código do evento.
