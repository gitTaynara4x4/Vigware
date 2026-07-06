# Integração Active Net → Vigware

O relatório do Console mostrou que o Active Net usa STOMP/WebSocket em `/active-net-websocket` e tópicos como:

- `/topic/evento`
- `/topic/atualizar-evento`
- `/topic/atualizar-todos-eventos`
- `/topic/remover-evento`

Nesta primeira versão, o Vigware recebe eventos do Active Net por HTTP:

- `POST /api/activenet/event`
- `POST /api/activenet/batch`

## Teste rápido

1. Rode o Vigware em `http://127.0.0.1:8002`.
2. Abra o Active Net em `https://localhost:9081/home`.
3. Abra o Console do Active Net.
4. Cole o conteúdo de `scripts/activenet_bridge_console.js`.
5. Rode:

```js
window.__vigwareActiveNetSendAll()
```

Para deixar enviando os eventos novos visíveis:

```js
window.__vigwareActiveNetStartPolling(5)
```

Para parar:

```js
window.__vigwareActiveNetStopPolling()
```

## Como os eventos são tratados

O Vigware deduplica por conta, código, data/hora, serial, IMEI, MAC e informações da linha.

Códigos já cadastrados no seed:

- `1250` — Falha de keep alive — abre ocorrência técnica
- `3250` — Restauração de keep alive — só histórico/raw event
- `1602` — Teste periódico — só histórico/raw event
- `1401` — Desarme por usuário — só histórico/raw event
- `1409` — Desarme via controle remoto — só histórico/raw event

Códigos desconhecidos entram como evento histórico sem abrir ocorrência. Depois você ajusta quais códigos devem abrir ocorrência.
