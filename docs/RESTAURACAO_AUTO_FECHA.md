# Restauração de comunicação fecha ocorrência automaticamente

Regra aplicada:

- `1250 - Falha de keep alive` abre ocorrência em Observação.
- `3250 - Restauração de keep alive` registra timeline e finaliza automaticamente a ocorrência `1250` ativa da mesma conta.
- A ocorrência sai da tela porque muda para `FINISHED`.
- Outros eventos de restauração continuam entrando apenas na timeline até definirmos regras específicas.
