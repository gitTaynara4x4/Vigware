# API Vigware Cloud

## Health

```http
GET /api/health
```

## Monitoramento

```http
GET /api/monitoring
```

Retorna colunas:

```json
{
  "columns": {
    "newers": [],
    "started": [],
    "displacement": [],
    "inPlace": [],
    "observation": []
  }
}
```

## Receiver HTTP simulado

```http
POST /api/receiver/events
```

```json
{
  "account_code": "0594",
  "event_code": "E130",
  "partition": "001",
  "zone": "005",
  "raw": "EVENTO_BRUTO_AQUI",
  "protocol": "HTTP_SIMULATED"
}
```

## Demo

```http
POST /api/demo/seed
POST /api/demo/reset
POST /api/demo/simulate/e130
POST /api/demo/simulate/e301
```

## Ocorrência

```http
GET /api/occurrences/{id}
GET /api/occurrences/{id}/timeline
POST /api/occurrences/{id}/watch
POST /api/occurrences/{id}/unwatch
POST /api/occurrences/{id}/status
```

Body para status:

```json
{
  "status": "STARTED",
  "note": "opcional"
}
```

Status aceitos:

```txt
NEW
STARTED
DISPLACEMENT
IN_PLACE
OBSERVATION
FINISHED
CANCELED
```

## WebSocket

```txt
/ws/monitoring
```

Recebe eventos como:

```json
{"type":"event_received"}
{"type":"status_changed"}
```
