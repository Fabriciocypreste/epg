# EPG dos canais do M3U

Gerador XMLTV com as seis fontes fornecidas e o catálogo de `playlist_new.m3u`: 607 IDs para 1.085 entradas `.ts`. O catálogo está incluído em `channels.json` no repositório privado. Filmes `.mp4` e `.mkv` ficam fora. O M3U original, suas URLs, usuário e senha não são publicados.

## Funcionamento

1. `channels.json` contém nomes, IDs e aliases dos canais, sem links de reprodução.
2. `scrape_providers.py` consulta os endpoints públicos de programação da Claro e Vivo, sem login nem APIs de reprodução. `sources.txt` lista as fontes XMLTV alternativas.
3. `build_epg.py` baixa as fontes e procura o `tvg-id` exato; na ausência dele, tenta o nome normalizado. Remove marcadores de qualidade, preservando identificadores regionais. Correspondências ambíguas ficam sem programação para revisão manual.
4. Usa a primeira fonte com programas válidos para cada canal, incluindo as últimas 12 horas e os próximos sete dias. Fontes indisponíveis ou desatualizadas não impedem a tentativa das demais.
5. Produz `output/epg.xml`, `output/epg.xml.gz` e `output/report.json`, que informa cobertura e canais pendentes. Não inventa programas. Se nenhum programa utilizável for encontrado, falha antes de substituir a saída anterior.
6. GitHub Actions executa testes, atualiza a cada seis horas e grava os resultados quando o catálogo estiver preenchido. Agendamentos do GitHub podem atrasar; repositórios públicos sem atividade podem ter o agendamento suspenso pela plataforma.

A coleta direta de Claro e Vivo trouxe programação atual nos testes locais. Use `--scrape`; o workflow já utiliza essa opção. As fontes XMLTV antigas permanecem como alternativas, mas na validação inicial quatro estavam desatualizadas e duas retornaram erros HTTP. Nem todos os 607 IDs têm correspondência nas operadoras; confira `output/report.json` para a cobertura efetiva.

Coleta padrão: dois dias, até três consultas simultâneas na Vivo e pausa entre chamadas. Falhas individuais são contabilizadas em `scrapers`; a outra operadora e as alternativas continuam disponíveis. Nomes regionais são preservados. A cidade da Claro é configurável com `--claro-city` (padrão `1`, São Paulo). Horários da Claro usam o relógio local `America/Sao_Paulo`, conforme o formato observado; a Vivo fornece timestamps Unix. Sinopses são mantidas quando fornecidas, priorizando a Vivo. A grade pública da Claro testada fornece títulos e horários sem sinopse.

Referências dos formatos: [Claro](https://github.com/iptv-org/epg/blob/master/sites/claro.com.br/claro.com.br.config.js) e [Vivo](https://github.com/iptv-org/epg/blob/master/sites/vivoplay.com.br/vivoplay.com.br.config.js). O coletor Python deste projeto não depende desses pacotes Node.

As seis URLs são entradas fornecidas pelo usuário, não uma garantia de cobertura ou disponibilidade. Confira o relatório e a execução em Actions antes de usar.

## URL para o app

Após a primeira execução bem-sucedida, enquanto o repositório estiver público:

```text
https://raw.githubusercontent.com/Fabriciocypreste/epg/main/output/epg.xml
https://raw.githubusercontent.com/Fabriciocypreste/epg/main/output/epg.xml.gz
```

O campo `channel` dos programas corresponde ao `id` de `channels.json`. Para canais sem `tvg-id` no M3U, use o ID `m3u-...` correspondente no cadastro do app. Canais com o mesmo ID compartilham programação; revisar IDs inconsistentes do fornecedor. Aliases de nome podem ser corrigidos em `channels.json`.

O player continua recebendo o `.ts` pelo fluxo atual do seu app. XMLTV fornece título, sinopse, início e fim; o progresso é calculado pelo app a partir desses horários.

## Autenticação, credenciais e tokens

O repositório estava vazio antes desta implementação. Não havia login, API de autenticação nem documentação de sessões para analisar. Este gerador não adiciona autenticação de usuários.

**Componentes e fluxo:** Actions → Python → programação pública Claro/Vivo e XMLTV → arquivos gerados → app. Os downloads XMLTV não enviam credenciais do M3U. O repositório está privado: o app deverá obter o EPG por um endpoint do backend. Não inclua tokens do GitHub no aplicativo. O gerador não acessa nem retransmite os vídeos `.ts`.

**Token do GitHub:** `actions/checkout` usa o `GITHUB_TOKEN` temporário da execução para obter o código e fazer o commit dos arquivos gerados. A permissão `contents: write` está declarada no workflow. Nenhum token permanente ou senha fica no código; o token da execução não deve ser entregue ao app. O checkout persiste a credencial de Git durante o job e a remove na limpeza.

**Ao tornar privado:** as URLs raw deixam de ser um endpoint público confiável para o app. Hospede `output/epg.xml` no backend existente e entregue pelo domínio da sua API. Se necessário, proteja esse endpoint com a autenticação já usada no app; mantenha qualquer token de acesso ao GitHub somente no servidor. A publicação automática nesse backend não foi configurada porque seus dados de hospedagem não foram fornecidos.

Referência: [token automático do Actions](https://docs.github.com/en/actions/security-for-github-actions/security-guides/automatic-token-authentication), [checkout e credenciais](https://github.com/actions/checkout).

## Executar localmente

```bash
python -m pip install -r requirements.txt
python -m unittest -v
python build_epg.py --scrape --days 2
```

Para atualizar o catálogo com um novo M3U local:

```bash
python build_epg.py --import-m3u /caminho/playlist.m3u
```

Não adicione o M3U original ao Git. O `.gitignore` exclui playlists e arquivos `.env`.
