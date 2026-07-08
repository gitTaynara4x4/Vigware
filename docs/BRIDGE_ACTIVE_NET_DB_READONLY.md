# Vigware Bridge Active Net - modo banco somente leitura

Este modo é o caminho seguro para produção inicial.

Ele **não mexe na porta 9800**, **não altera configurações do Active Net** e **não escreve no banco local do Active Net**.

Fluxo:

```text
Centrais/JFL -> Active Net porta 9800 -> PostgreSQL local active_net.eventos
                                      -> Vigware Bridge SELECT read-only
                                      -> Vigware Cloud HMAC
```

Configuração no PC do Active Net/JFL:

```json
{
  "vigware_base_url": "https://apps-vigware.9ywrah.easypanel.host",
  "source_mode": "database",
  "auth_mode": "hmac",
  "bridge_id": "activenet-matriz",
  "bridge_secret": "MESMA_CHAVE_DO_EASYPANEL",
  "active_net_pg_host": "127.0.0.1",
  "active_net_pg_port": 5433,
  "active_net_pg_database": "postgres",
  "active_net_pg_user": "postgres",
  "active_net_pg_password": "",
  "active_net_pg_schema": "active_net",
  "active_net_events_table": "eventos",
  "initial_position": "latest",
  "poll_seconds": 2
}
```

`initial_position=latest` significa que na primeira execução o bridge começa do último `id` existente e só envia eventos novos dali em diante.

Para executar:

```powershell
cd "$env:USERPROFILE\Desktop\Vigware\bridge"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned -Force
.\run_bridge.ps1
```
