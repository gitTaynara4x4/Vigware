# Correção: restauração 3250 fecha falha 1250

Regra operacional:

- `1250` abre ocorrência de falha de keep alive em Observação.
- `3250` fecha automaticamente todas as ocorrências `1250` ativas da mesma conta.
- O board também reconcilia ocorrências antigas: se o último evento importado da conta entre `1250` e `3250` for `3250`, a ocorrência antiga é finalizada automaticamente.

Isso evita que clientes já reconectados continuem presos na tela.
