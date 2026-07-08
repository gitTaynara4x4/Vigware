# Vigware Cloud — Importar no GitHub e EasyPanel

## 1. Subir para o GitHub

Extraia este ZIP, entre na pasta do projeto e rode:

```powershell
git init
git add .
git commit -m "primeira versão vigware cloud"
git branch -M main
git remote add origin https://github.com/SEU_USUARIO/vigware-cloud.git
git push -u origin main
```

Não suba `.env` nem `bridge/config.json`. Eles estão no `.gitignore`.

## 2. Criar app no EasyPanel

No EasyPanel:

- App: GitHub
- Branch: `main`
- Build: Dockerfile
- Porta interna: `8002`

## 3. Variáveis no EasyPanel

Configure no app:

```env
APP_NAME=Vigware Cloud
APP_ENV=prod
CORS_ORIGINS=*
DATABASE_URL=postgresql+psycopg://USUARIO:SENHA@HOST:5432/BANCO?sslmode=prefer
VIGWARE_RECEIVER_KEY=COLOQUE_UMA_CHAVE_FORTE_AQUI
REQUIRE_RECEIVER_KEY=true
```

A `DATABASE_URL` precisa começar com `postgresql+psycopg://`.

## 4. Domínio

Adicione o domínio no EasyPanel e ative HTTPS, exemplo:

```text
https://vigware.seudominio.com.br
```

Teste:

```text
https://vigware.seudominio.com.br/api/health
```

## 5. Bridge no PC do Active Net

No PC onde roda o Active Net/JFL, copie a pasta `bridge/`.

Renomeie:

```text
config.example.json -> config.json
```

Configure:

```json
{
  "vigware_base_url": "https://vigware.seudominio.com.br",
  "vigware_receiver_key": "A_MESMA_CHAVE_DO_EASYPANEL",
  "active_net_base_url": "https://localhost:9081",
  "active_net_verify_ssl": false,
  "topics": [
    "/topic/evento",
    "/topic/atualizar-evento"
  ],
  "send_remove_events": false,
  "log_level": "INFO",
  "reconnect_seconds": 5
}
```

Rode:

```powershell
cd bridge
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned -Force
.\run_bridge.ps1
```

## 6. Testar receiver

No Windows:

```powershell
.\scripts\test_receiver.ps1 -BaseUrl "https://vigware.seudominio.com.br" -Key "SUA_CHAVE"
```

## Segurança correta do receiver

Esta versão usa HMAC por bridge/transmissor. No EasyPanel, use:

```env
REQUIRE_RECEIVER_KEY=true
RECEIVER_AUTH_MODE=hmac
RECEIVER_ALLOWED_DRIFT_SECONDS=300
VIGWARE_BRIDGE_ID=activenet-matriz
VIGWARE_BRIDGE_SECRET=TROQUE_POR_UMA_CHAVE_GRANDE_IGUAL_A_DO_BRIDGE
```

No PC do Active Net, o arquivo `bridge/config.json` precisa ter o mesmo `bridge_id` e o mesmo `bridge_secret`.

Teste:

```powershell
.\scripts\test_receiver.ps1 -BaseUrl "https://SEU_DOMINIO" -BridgeId "activenet-matriz" -BridgeSecret "A_MESMA_CHAVE"
```
