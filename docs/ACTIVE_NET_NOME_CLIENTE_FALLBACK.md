# Active Net - fallback correto para nome do cliente

O Active Net nem sempre preenche `active_net.eventos.nome_cliente` nem `active_net.contas.nome_cliente`.

Quando esses campos vêm vazios, o nome correto do cliente pode estar na relação:

```text
active_net.contas.clientes_id
↓
active_net.clientes.id
↓
active_net.clientes.dono_cliente_id
↓
active_net.dono_cliente.nome
```

A partir desta versão, o bridge usa a ordem:

```text
1. contas.nome_cliente
2. clientes.nome
3. dono_cliente.nome
4. Conta XXXX
```

Tudo continua em modo somente leitura no PostgreSQL local do Active Net. O bridge não altera porta, não altera configuração, não escreve no banco e não reinicia o Active Net.
