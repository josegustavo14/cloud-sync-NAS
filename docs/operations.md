# Operação, backup e homologação

## Backup consistente

Pare o serviço antes de copiar o estado, garantindo um conjunto consistente de SQLite, WAL e arquivos. Copie **todo** `/DATA/CloudSync` para um segundo disco/servidor, preservando permissões. O diretório `config` contém refresh tokens; proteja e cifre o backup. Reinicie depois com `docker compose up -d`.

Para restauração, pare o serviço e restaure o conjunto completo em um diretório dedicado. Configure `PCS_ROOT` para esse diretório. Não restaure apenas o arquivo SQLite enquanto o serviço estiver ativo.

Migrations são append-only e transacionais. Uma imagem antiga recusa um banco com versão de schema mais recente; rollback após migration pode exigir restaurar o backup completo. Atualizações sem alteração do schema podem retornar à imagem anterior usando o mesmo volume.

## Logs e falhas

- Histórico completo: tabela `events`, acessível em Histórico → Logs.
- Log adicional: `logs/events.jsonl`, rotação em 5 MiB para `.jsonl.1`.
- Processo: `docker compose logs --tail=100 cloud-sync`.
- Não há logs de URLs autenticadas, conteúdo do rclone.conf ou saída bruta de exceções dos providers.
- Falhas deixam `.part` fora do índice. Novo download do mesmo remote ID substitui somente seu próprio parcial. Partes abandonadas podem ser inspecionadas e removidas manualmente com o serviço parado.
- Conteúdo publicado antes de um crash é verificado e reaproveitado na próxima importação. Hash divergente em conteúdo existente gera falha e não sobrescreve o arquivo.
- O token deve ter pelo menos 32 caracteres. Para rotacionar, altere `.env`, recrie o serviço e reconecte os clientes.

## Critérios de homologação V1

| Critério | Evidência automatizada / validação necessária |
| --- | --- |
| Mesmo SHA, uma cópia física | Teste unitário e smoke Docker |
| SHAs diferentes, cópias diferentes | Teste unitário e smoke Docker |
| Download incompleto continua `.part` | Teste unitário |
| Falha do provider preserva arquivos | Teste unitário |
| Reinício preserva índice e conteúdo | Teste unitário e smoke Docker |
| Recriação executa migration e preserva estado | Smoke Docker; homologar futuras migrations reais |
| Origem nunca recebe delete | Superfície de comandos restrita, testes; mount local `:ro` |
| Google Drive / OneDrive / Dropbox | Autorizar contas reais e verificar permissões e downloads |
| Múltiplas contas | Teste de dedup entre contas; homologar contas reais |
| Agendamento | Scheduler persistido, teste unitário; observar ciclo real no ZimaOS |
| Android | Analyze/tests e build no CI; instalar APK em aparelho |
| Immich | Montar `:ro`, cadastrar External Library e testar varredura |
| Releases | Configurar GitHub, GHCR, Secrets e executar primeira tag |

Não considere a implantação homologada apenas porque os testes unitários passaram. A primeira execução no ZimaOS deve usar uma origem pequena conhecida e uma segunda exportação que contenha duplicatas e arquivos novos. Compare quantidades, hashes e permissões antes de importar a biblioteca completa.

## Segurança de implantação

Use disco local para SQLite (não NFS/SMB). O container roda como UID/GID 1000, com filesystem raiz somente leitura, sem capabilities e sem elevação. Mantenha apenas os diretórios de estado graváveis. Não exponha Docker socket, filesystem raiz do host ou a pasta interna do Immich.

O token dá acesso administrativo; não há segregação entre usuários. O serviço não fornece HTTPS próprio. Use um reverse proxy com TLS ou uma rede Tailscale confiável. A UI é servida pelo mesmo domínio da API e não habilita CORS amplo.
