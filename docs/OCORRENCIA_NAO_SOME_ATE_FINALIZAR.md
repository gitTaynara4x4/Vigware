# Ocorrência não some automaticamente

Regra operacional aplicada:

- A ocorrência permanece em tela enquanto estiver com status ativo:
  - NEW / Novos
  - STARTED / Iniciado
  - DISPLACEMENT / Deslocamento
  - IN_PLACE / No local
  - OBSERVATION / Observação
- Eventos de restauração/normalização, como `3250 - Restauração de keep alive`, não finalizam automaticamente a ocorrência.
- A restauração é adicionada na timeline da ocorrência ativa.
- A ocorrência só sai da fila quando o operador clicar em `Finalizar` ou `Cancelar`.

Exemplo:

1. `1250 - Falha de keep alive` abre ocorrência em Observação.
2. `3250 - Restauração de keep alive` entra na timeline.
3. O card continua na tela.
4. Operador avalia e finaliza manualmente.
