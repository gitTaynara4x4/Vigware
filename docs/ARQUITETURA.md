# Arquitetura Vigware Cloud

## Fluxo

```txt
Central/Comunicador/Receptora
  ↓
Receiver HTTP/TCP/UDP futuro
  ↓
raw_events
  ↓
Parser/Normalizador
  ↓
occurrences
  ↓
occurrence_timeline
  ↓
WebSocket
  ↓
Frontend monitoramento
```

## MVP atual

O MVP usa receiver HTTP simulado:

```txt
POST /api/receiver/events
```

Isso cria raw_event, cria ou atualiza ocorrência, registra timeline e emite WebSocket.

## Próximos passos

1. Login e permissões.
2. Cadastro completo de cliente/conta/zona/contatos.
3. Receiver TCP/UDP para SIA/Contact ID.
4. Regras de protocolo por cliente.
5. OS técnica.
6. Viatura/pronta resposta.
7. App/portal cliente.
