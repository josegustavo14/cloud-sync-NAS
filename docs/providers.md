# Providers e OAuth

Cada conta usa um remote exclusivo: `drive-pessoal:`, `drive-trabalho:`, `onedrive-pessoal:` etc. A aplicação não recebe client secrets nem tokens OAuth pela API. O rclone renova os tokens no arquivo persistente `/DATA/CloudSync/config/rclone.conf`.

## Configuração inicial

A Web UI oferece o assistente **Autorizar ou reautenticar uma conta pelo navegador**. Escolha o provider, dê um nome ao remote e siga as perguntas exibidas. Quando o rclone solicitar a autorização, abra o link mostrado, conclua o OAuth e cole apenas o resultado pedido. O remote é salvo diretamente em `rclone.conf`.

O fluxo de terminal abaixo permanece como recuperação para instalações antigas ou quando o assistente web for interrompido.

```sh
docker compose exec cloud-sync rclone config --config /DATA/CloudSync/config/rclone.conf
```

Escolha `n`, um nome simples com letras, números, hífen ou underscore, e o provider. Siga o OAuth oficial. Em servidor headless, responda **não** à autenticação automática por navegador e execute o comando `rclone authorize` indicado pelo assistente em um computador com navegador e a mesma versão do rclone. Cole o resultado apenas no assistente, nunca em logs, issues ou código.

Depois, abra Contas → Adicionar conta. A Web UI lista somente nomes e tipos dos remotes. No Android, informe `nome-do-remote:`; caminhos de subpastas podem ser acrescentados, por exemplo `drive-pessoal:Fotos`.

### Google Drive

Escolha `drive` e o escopo **drive.readonly**. Não escolha `drive.file`, que não concede leitura de toda a biblioteca. Um OAuth client próprio pode ser necessário conforme políticas/quota do Google; a configuração fica no rclone. Contas de organizações dependem das políticas do administrador.

Referência: [Google Drive no rclone](https://rclone.org/drive/).

### OneDrive

Escolha `onedrive`. Nas opções avançadas, use `access_scopes = Files.Read Files.Read.All offline_access` quando compatível com a conta e unidade selecionada. A descoberta de sites SharePoint pode exigir `Sites.Read.All`; adicione somente quando necessário. Teste listagem e download da unidade escolhida. Evite os escopos padrão de escrita quando leitura atender ao caso.

Referência: [OneDrive no rclone](https://rclone.org/onedrive/).

### Dropbox

Escolha `dropbox`. Para limitar permissões na autorização, configure um app OAuth próprio no Dropbox e selecione apenas os escopos de leitura necessários, incluindo `files.metadata.read`, `files.content.read` e acesso de leitura à conta quando requerido pelo rclone. O app OAuth padrão do rclone pode solicitar permissões mais amplas. Independentemente do escopo concedido, esta aplicação somente executa listagem e leitura; não promete um escopo read-only que o app OAuth escolhido não ofereça.

Referência: [Dropbox no rclone](https://rclone.org/dropbox/).

## Reautenticar ou revogar

```sh
docker compose exec cloud-sync rclone config reconnect NOME: --config /DATA/CloudSync/config/rclone.conf
```

Reautentique usando o mesmo nome para preservar a associação com a conta cadastrada. Desativar a integração cancela jobs pendentes/ativos e suspende agendamentos, sem apagar arquivos locais. Revogue o app no painel do Google/Microsoft/Dropbox para invalidar também suas credenciais. A aplicação mantém o registro da integração para preservar a proveniência.

## Dispositivos e Takeout

Monte a pasta de origem em `/sources` como `:ro`. Cadastre uma subpasta relativa, por exemplo `celular`, ou `takeout` como provider `takeout`. ZIP, `.tar`, `.tgz`, `.tar.gz` e exportações já extraídas são aceitos. Para adicionar uma exportação posterior, coloque-a nessa origem e execute novamente. Conteúdos iguais serão deduplicados mesmo quando nomes e caminhos forem diferentes.

Arquivos compactados são lidos por streaming sem `extractall`; nomes como `../../arquivo` nunca são usados como destino. Sidecars são guardados como arquivos independentes. Arquivos compactados muito grandes podem exigir tempo adicional, sobretudo TAR, porque cada entrada é reaberta para leitura.

Não conecte a biblioteca completa do Google Photos por API. Use exportações de [Google Takeout](https://takeout.google.com/).

## Operações permitidas

Na sincronização, a linha de comando rclone permite apenas [`lsjson`](https://rclone.org/commands/rclone_lsjson/) e [`cat`](https://rclone.org/commands/rclone_cat/). A origem nunca é passada como destino. Saída de erro do rclone é descartada para evitar expor credenciais; a aplicação registra mensagens sanitizadas.
