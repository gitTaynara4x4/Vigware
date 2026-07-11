# Restauração de conexão Active Net

O Vigware trata os dois formatos encontrados na integração:

- `1250` (falha de keep alive) → `3250` (restauração de keep alive);
- `E250` (falha de conexão com módulo) → `R250` (restauração de conexão).

Restaurações de comunicação fecham automaticamente todas as falhas de comunicação ativas da mesma conta. Restaurações de alarme, energia e bateria continuam apenas na timeline para decisão do operador.

Também são reconhecidas restaurações cujo código varia, mas cuja descrição informa restauração/restabelecimento de conexão, comunicação, GPRS, Ethernet ou keep alive.
