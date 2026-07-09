# Drag/drop de ocorrências

A tela inicial agora permite mover ocorrências arrastando o card entre as colunas operacionais:

- Novos -> `NEW`
- Iniciado -> `STARTED`
- Deslocamento -> `DISPLACEMENT`
- Observação -> `OBSERVATION`

Ao soltar o card, o frontend chama:

```http
POST /api/occurrences/{id}/status
```

com uma nota operacional indicando que a ocorrência foi movida por arrasto. O backend já registra a mudança na timeline.

A movimentação é otimista: o card muda de coluna na hora e depois a tela é sincronizada com a API. Caso a API falhe, a tela atualiza novamente e mostra aviso.
