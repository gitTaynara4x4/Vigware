# Vigware Cloud

Sistema de monitoramento estilo central: receiver, ocorrências, timeline, tela em tempo real e integração Active Net/JFL.

## Rodar local

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8002 --reload
```

Abra:

```text
http://127.0.0.1:8002
```

## Rodar na VPS com EasyPanel

Use Dockerfile e porta interna `8002`.

Variáveis principais:

```env
APP_NAME=Vigware Cloud
APP_ENV=prod
CORS_ORIGINS=*
DATABASE_URL=postgresql+psycopg://USUARIO:SENHA@HOST:5432/BANCO?sslmode=prefer
VIGWARE_RECEIVER_KEY=COLOQUE_UMA_CHAVE_FORTE_AQUI
REQUIRE_RECEIVER_KEY=true
```

Guia:

```text
docs/EASYPANEL_UBUNTU_24.md
```

## Receiver Active Net

Endpoint de produção:

```text
POST /api/receiver/activenet
POST /api/receiver/activenet/batch
Header: X-Vigware-Key
```

Exemplo:

```json
{
  "account_code": "0073",
  "event_code": "1250",
  "description": "Falha de keep alive",
  "info_1": "---",
  "info_2": "---",
  "date_time": "06/07/26 04:48:10"
}
```

## Bridge Active Net no Windows

Pasta:

```text
bridge/
```

Guia:

```text
docs/BRIDGE_ACTIVENET_WINDOWS.md
```

Fluxo:

```text
Active Net/JFL → bridge Windows → Vigware Cloud na VPS → ocorrência na tela
```

## Eventos Active Net já cadastrados

```text
1250 = Falha de keep alive → abre ocorrência técnica
3250 = Restauração de keep alive → histórico
1602 = Teste periódico → histórico
1401 = Desarme por usuário → histórico
1409 = Desarme via controle remoto → histórico
```
