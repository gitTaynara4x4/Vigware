# Receiver HMAC de produção

Este é o modo correto para o Vigware receber evento de bridge/receptora sem deixar endpoint público aberto.

## Fluxo

```text
PC do Active Net/JFL
↓
Vigware Bridge local
↓ HTTPS assinado com HMAC
Vigware Cloud na VPS
↓
PostgreSQL + tela do operador
```

## Headers obrigatórios

O bridge envia:

```http
X-Vigware-Bridge-Id: activenet-matriz
X-Vigware-Timestamp: 1783400000
X-Vigware-Nonce: 6f4c...
X-Vigware-Signature: sha256=<hmac>
```

A assinatura é calculada assim:

```text
sha256=HMAC_SHA256(bridge_secret, timestamp + "." + nonce + "." + raw_body_json)
```

## O que isso resolve

- Evita evento falso simples.
- Cada bridge tem sua própria chave.
- Bloqueia replay básico usando nonce.
- Bloqueia requisição fora da janela de tempo.
- O PC do Active Net não acessa o banco diretamente.

## Variáveis no EasyPanel

```env
REQUIRE_RECEIVER_KEY=true
RECEIVER_AUTH_MODE=hmac
RECEIVER_ALLOWED_DRIFT_SECONDS=300
VIGWARE_BRIDGE_ID=activenet-matriz
VIGWARE_BRIDGE_SECRET=TROQUE_POR_UMA_CHAVE_GRANDE_IGUAL_A_DO_BRIDGE
```

Para vários bridges:

```env
VIGWARE_BRIDGE_SECRETS={"activenet-matriz":"segredo1","activenet-filial":"segredo2"}
```

## Config no PC do Active Net

`bridge/config.json`:

```json
{
  "vigware_base_url": "https://apps-vigware.9ywrah.easypanel.host",
  "auth_mode": "hmac",
  "bridge_id": "activenet-matriz",
  "bridge_secret": "TROQUE_POR_UMA_CHAVE_GRANDE_IGUAL_A_DO_EASYPANEL",
  "active_net_base_url": "https://localhost:9081",
  "active_net_verify_ssl": false,
  "topics": ["/topic/evento", "/topic/atualizar-evento"],
  "send_remove_events": false,
  "log_level": "INFO",
  "reconnect_seconds": 5
}
```

## Teste

```powershell
.\scripts\test_receiver.ps1 `
  -BaseUrl "https://apps-vigware.9ywrah.easypanel.host" `
  -BridgeId "activenet-matriz" `
  -BridgeSecret "A_MESMA_CHAVE_DO_EASYPANEL"
```
