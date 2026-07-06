# Vigware Cloud na VPS Ubuntu 24.04 com EasyPanel

## O que fica online

O Vigware Cloud fica publicado na VPS. O PC onde roda o Active Net/JFL não chama `127.0.0.1`; ele chama o domínio da VPS.

Fluxo:

```text
Active Net / JFL no PC da empresa
↓
Vigware Bridge local
↓ HTTPS com X-Vigware-Key
Vigware Cloud na VPS
↓
Tela do operador em tempo real
```

## Variáveis do app no EasyPanel

Use o arquivo:

```text
deploy/easypanel/.env.easypanel.example
```

Configure no app:

```env
APP_NAME=Vigware Cloud
APP_ENV=prod
CORS_ORIGINS=*
DATABASE_URL=postgresql+psycopg://USUARIO:SENHA@HOST:5432/BANCO?sslmode=prefer
VIGWARE_RECEIVER_KEY=COLOQUE_UMA_CHAVE_FORTE_AQUI
REQUIRE_RECEIVER_KEY=true
```

A mesma `VIGWARE_RECEIVER_KEY` precisa ir no `bridge/config.json` do PC do Active Net.

## Porta

O container expõe a porta:

```text
8002
```

No EasyPanel, a aplicação deve apontar para a porta interna `8002`.

## Comando do app

O Dockerfile já usa:

```text
python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8002
```

## Teste de saúde

Depois de publicar, abra:

```text
https://SEU_DOMINIO/
```

E teste o receiver:

```powershell
.\scripts\test_receiver.ps1 -BaseUrl "https://SEU_DOMINIO" -Key "SUA_CHAVE"
```

Se retornar `ok: true`, a VPS já recebe evento.

## Primeiro evento real

Quando o bridge do PC Active Net estiver rodando, eventos como:

```text
Conta 0073
Evento 1250
Descrição Falha de keep alive
```

entram no endpoint:

```text
POST /api/receiver/activenet
```

E viram ocorrência se o código estiver configurado para abrir ocorrência.
