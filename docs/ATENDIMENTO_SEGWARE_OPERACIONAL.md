# Vigware - Atendimento operacional estilo Segware

Esta versão cria a primeira tela de atendimento da ocorrência em modo operacional.

## O que mudou

- Clique no card abre uma área de atendimento em tela cheia, sem modal.
- Layout dividido em fila, timeline e dados da conta.
- Painel direito com localização, protocolo/como atuar, contatos, zonas/áreas e conexões.
- Botões operacionais: Atender, Deslocar, Observar e Finalizar.
- Bridge passa a sincronizar contatos de `active_net.contato_cliente`.
- Bridge passa a sincronizar áreas de `active_net.area` como zonas/áreas no Vigware.
- Bridge passa a enviar `dono_cliente.regras_do_local` como protocolo/como atuar e `informacoes_do_local` como observação do local.

## Segurança

A leitura do banco do Active Net continua somente SELECT.
Não altera porta 9800, não altera configuração do Active Net e não escreve no banco local do Active Net.
