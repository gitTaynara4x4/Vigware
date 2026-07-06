# Vigware Bridge Active Net no Windows

Este bridge roda no PC onde está o Active Net/JFL.

Ele conecta no WebSocket/STOMP local do Active Net:

```text
https://localhost:9081/active-net-websocket
```

Assina os tópicos:

```text
/topic/evento
/topic/atualizar-evento
```

E envia para a VPS:

```text
POST https://SEU_DOMINIO/api/receiver/activenet/batch
X-Vigware-Key: SUA_CHAVE
```

## Instalação rápida

1. Copie a pasta `bridge` para o PC do Active Net.
2. Renomeie:

```text
config.example.json → config.json
```

3. Edite `config.json`:

```json
{
  "vigware_base_url": "https://vigware.seudominio.com.br",
  "vigware_receiver_key": "A_MESMA_CHAVE_DO_EASYPANEL",
  "active_net_base_url": "https://localhost:9081",
  "active_net_verify_ssl": false,
  "topics": ["/topic/evento", "/topic/atualizar-evento"],
  "send_remove_events": false,
  "log_level": "INFO",
  "reconnect_seconds": 5
}
```

4. Abra PowerShell dentro da pasta `bridge` e rode:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned -Force
.\run_bridge.ps1
```

## Serviço Windows

Para rodar sempre, use o arquivo:

```text
install_service_windows.ps1
```

Ele usa NSSM. Primeiro rode manualmente com `run_bridge.ps1`; só instale serviço depois que conectar certo.

## Observação importante

`localhost` no bridge significa o PC do Active Net, porque o bridge roda nesse PC. Isso está certo.

O `vigware_base_url` precisa ser público, tipo:

```text
https://vigware.seudominio.com.br
```
