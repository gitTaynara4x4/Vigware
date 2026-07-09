# Correção clique nos cards

Corrige o clique nos cards da tela operacional.

Mudanças:
- clique dos cards tratado por delegação no `document`;
- não perde listener quando o WebSocket/refresh recria os cards;
- abre detalhe mesmo se a chamada de `watch` falhar temporariamente;
- mostra toast e erro no console caso a ocorrência não abra.
