# Correção de duplicidade 1130/3130

Regra aplicada:

- `1130` / disparo / alarme abre ocorrência operacional.
- `3130` / zona em alarme normalizada / restauração NÃO abre card novo.
- `3130` entra na timeline da ocorrência `1130` correspondente.
- Cards antigos de restauração/normalização criados por versões anteriores são finalizados automaticamente na consulta do board.
- `3250` continua fechando automaticamente falha `1250` de keep alive.
- Arme/desarme normal (`1401`, `3401`, etc.) continua como histórico/status, não ocorrência comum.

Motivo: no Contact ID/Active Net, códigos `3xxx` geralmente representam restauração/normalização do evento `1xxx`. Algumas descrições contêm a palavra “alarme”, como “Zona em Alarme Normalizada”, e isso estava fazendo o Vigware criar uma segunda ocorrência.
