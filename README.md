# EPG dos canais do M3U

Gerador XMLTV com as seis fontes fornecidas. O catálogo extraído de `playlist_new.m3u` foi preparado localmente: 607 IDs para 1.085 entradas `.ts`. Sua publicação no repositório público ficou bloqueada pela revisão automática; `channels.json` começa vazio. Depois de tornar o repositório privado, importe o M3U localmente ou solicite a inclusão do catálogo preparado. Filmes `.mp4` e `.mkv` ficam fora. O M3U original, suas URLs, usuário e senha não são publicados.

## Funcionamento

1. `channels.json` contém nomes, IDs e aliases dos canais, sem links de reprodução.
2. `sources.txt` lista as fontes HTTPS XMLTV na ordem de preferência.
3. `build_epg.py` baixa as fontes e procura o `tvg-id` exato; na ausência dele, tenta o nome normalizado. Remove marcadores de qualidade, preservando identificadores regionais. Correspondências ambíguas ficam sem programação para revisão manual.
4. Usa a primeira fonte com programas válidos para cada canal, incluindo as últimas 12 horas e os próximos sete dias. Fontes indisponíveis ou desatualizadas não impedem a tentativa das demais.
5. Produz `output/epg.xml`, `output/epg.xml.gz` e `output/report.json`, que informa cobertura e canais pendentes. Não inventa programas. Se nenhum programa utilizável for encontrado, falha antes de substituir a saída anterior.
6. GitHub Actions executa testes, atualiza a cada seis horas e grava os resultados quando o catálogo estiver preenchido. Agendamentos do GitHub podem atrasar; repositórios públicos sem atividade podem ter o agendamento suspenso pela plataforma.

Na validação inicial, as quatro fontes BrazilTVEPG responderam XMLTV, mas não tinham programas na janela da data desta sessão (09/10/2026); as duas outras fontes retornaram erros HTTP. Portanto, ainda não há um EPG atual gerado. É necessário restaurar/substituir as fontes para obter programação atual.

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

**Componentes e fluxo:** Actions → Python → fontes XMLTV HTTPS → arquivos gerados → app. Os downloads XMLTV não enviam credenciais do M3U. O app obtém o EPG público por GET, sem token. O gerador não acessa nem retransmite os vídeos `.ts`.

**Token do GitHub:** `actions/checkout` usa o `GITHUB_TOKEN` temporário da execução para obter o código e fazer o commit dos arquivos gerados. A permissão `contents: write` está declarada no workflow. Nenhum token permanente ou senha fica no código; o token da execução não deve ser entregue ao app. O checkout persiste a credencial de Git durante o job e a remove na limpeza.

**Ao tornar privado:** as URLs raw deixam de ser um endpoint público confiável para o app. Hospede `output/epg.xml` no backend existente e entregue pelo domínio da sua API. Se necessário, proteja esse endpoint com a autenticação já usada no app; mantenha qualquer token de acesso ao GitHub somente no servidor. A publicação automática nesse backend não foi configurada porque seus dados de hospedagem não foram fornecidos.

Referência: [token automático do Actions](https://docs.github.com/en/actions/security-for-github-actions/security-guides/automatic-token-authentication), [checkout e credenciais](https://github.com/actions/checkout).

## Executar localmente

```bash
python -m pip install -r requirements.txt
python -m unittest -v
python build_epg.py
```

Para atualizar o catálogo com um novo M3U local:

```bash
python build_epg.py --import-m3u /caminho/playlist.m3u
```

Não adicione o M3U original ao Git. O `.gitignore` exclui playlists e arquivos `.env`.
