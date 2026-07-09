# Atendimento operacional estilo Segware

Esta versão amplia a tela de atendimento da ocorrência para ficar mais próxima da operação Segware/Sigma.

## Incluído

- Filtros funcionais da timeline: Todos, Eventos, Logs, Ocorrência e Mesmo auxiliar.
- Inserção de log pelo operador diretamente na timeline.
- Anotações temporárias com providência.
- Drawer lateral de mídia/imagens, com registro da mídia na timeline.
- Geração de eventos manuais X8 e X12.
- Painel direito com Localização, Anotações temporárias, Imagens do local, Usuários e contatos, Zonas/áreas, Conexões, Ordem de serviço e Como atuar.
- Drag and drop dos cards entre Novos, Iniciado, Deslocamento e Observação.
- Cache bust nos arquivos JS/CSS para o navegador pegar a versão nova.

## Observação

A parte de mídia registra os nomes dos arquivos na timeline. Persistência real de upload/armazenamento de imagem deve ser ligada depois a storage próprio, S3 ou volume seguro da VPS.

Os botões Armar/Desarmar continuam registrando solicitação no Vigware. O envio real para Active Net/JFL deve passar pelo bridge local autorizado em etapa separada.
