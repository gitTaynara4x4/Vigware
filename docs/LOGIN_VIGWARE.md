# Login do Vigware Cloud

A tela inicial agora exige autenticação antes de carregar o monitoramento.

## Credencial inicial de desenvolvimento

- E-mail: `operador@vigware.local`
- Senha: `vigware123`

Antes de publicar, configure no `.env`:

```env
VIGWARE_ADMIN_EMAIL=seu-email@empresa.com
VIGWARE_ADMIN_PASSWORD=uma-senha-forte
AUTH_SESSION_HOURS=12
AUTH_COOKIE_NAME=vigware_session
```

A primeira inicialização cria automaticamente as tabelas `user_credentials` e `user_sessions`. Não é necessário executar SQL manualmente.

A autenticação usa cookie `HttpOnly`, senha com PBKDF2-SHA256 e sessão armazenada pelo hash do token. As rotas do receiver e do ActiveNet continuam independentes, usando a segurança própria do bridge.

O botão **Esqueci minha senha** ainda é apenas informativo. A recuperação por e-mail deve ser implementada quando houver serviço de envio configurado.
