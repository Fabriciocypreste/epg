# Fontes de programação pesquisadas — 09/10/2026

| Fonte | URL | Dados e estado |
|---|---|---|
| Claro | https://www.claro.com.br/tv-por-assinatura/programacao/grade | Coletor integrado; títulos e horários atuais. Cidade padrão São Paulo, configurável. |
| Vivo | https://www.vivotv.com.br/ | Coletor integrado por endpoints públicos de metadados; horários e sinopses. |
| MeuGuia — Esportes | https://meuguia.tv/programacao/categoria/Esportes | Coletor integrado. Canal, título do jogo/evento, horários e categorias. |
| Prime Video | https://www.primevideo.com/-/pt/livetv | Coletor integrado para a seleção pública da página inicial; horários, títulos e sinopses. Janela curta e região variável. |
| mi.tv | https://mi.tv/br/sitemap | Candidato para ampliar cobertura. Sitemap com links de canais e página de programação por data acessíveis no teste. Ainda sem coletor neste projeto. Há nomes históricos no catálogo; validar por programação atual, não só pela presença no sitemap. |
| TV Map | https://tvmap.com.br/programacao/ | Candidato para ampliar cobertura. HTML público mostrou canais e horários, inclusive sportv. Ainda sem coletor neste projeto. |
| TV Globo | https://redeglobo.globo.com/tvglobo/programacao/ | Candidato para afiliadas e regionais. Grade usa carregamento dinâmico; página acessível, extração da lista de programas ainda não implementada. |
| TV Gazeta ES | https://redeglobo.globo.com/tvgazetaes/programacao/ | Página oficial regional acessível; coleta ainda não implementada. |
| ESPN | https://www.espn.com.br/programacao/detalhada | Candidato especializado. O acesso de pesquisa não revelou uma grade completa; exige inspeção adicional antes de implementar. |

## Formatos confirmados

- MeuGuia: links `/programacao/canal/CODIGO`. Exemplo sportv: https://meuguia.tv/programacao/canal/SPO . O HTML traz cabeçalhos de data e horários de cada programa; o canal da página indica onde passa o evento. O fim pode ser derivado do próximo início. Não criar duração para o último item.
- mi.tv: `https://mi.tv/br/async/channel/SLUG/AAAA-MM-DD/0`. Exemplo testado: https://mi.tv/br/async/channel/sportv/2026-10-09/0 . Requer verificar títulos, data, fuso e fim real antes de gerar XMLTV.
- Prime: JSON `dv-web-page-hydration-data` no HTML contém `station.name`, `station.schedule[].start/end` em milissegundos e `metadata.title/synopsis`. Algumas estações aparecem repetidas; deduplicar pelo ID e intervalo.
- Claro/Vivo: os endpoints e a conversão de horários estão em `scrape_providers.py`. Não consultar APIs de reprodução para obter EPG.

## Referências dos coletores

- https://github.com/iptv-org/epg/blob/master/sites/meuguia.tv/meuguia.tv.config.js
- https://github.com/iptv-org/epg/blob/master/sites/mi.tv/mi.tv.config.js
- https://github.com/iptv-org/epg/blob/master/sites/claro.com.br/claro.com.br.config.js
- https://github.com/iptv-org/epg/blob/master/sites/vivoplay.com.br/vivoplay.com.br.config.js

Prioridade implementada: MeuGuia Esportes → Vivo → Claro → Prime → XMLTV alternativas. mi.tv e TV Map são os próximos candidatos. Disponibilidade HTTP não garante cobertura, atualização nem estabilidade do formato; o relatório de geração deve mostrar o resultado efetivo.
