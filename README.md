# Personal Cloud Sync

Repositório: [josegustavo14/cloud-sync-NAS](https://github.com/josegustavo14/cloud-sync-NAS).

Cópia unidirecional de múltiplas nuvens, dispositivos e Google Takeout para um servidor ZimaOS. Python/FastAPI, SQLite, rclone, React e Flutter.

Status: **0.2.0, implementação inicial em validação**. Os fluxos locais e a infraestrutura são testáveis; a homologação com contas reais, ZimaOS e uma release publicada ainda é necessária antes de declarar V1.

## Garantias de armazenamento

- A interface dos providers permite apenas listar e ler. O rclone executa somente `lsjson` e `cat` nas sincronizações; nunca `sync`, `move`, `delete` ou upload.
- Downloads são transmitidos para `.part`, conferidos por tamanho e SHA-256, persistidos com `fsync` e publicados atomicamente no mesmo volume antes de indexar.
- Conteúdos idênticos compartilham uma cópia física. Cada conta e remote ID mantém sua própria origem no SQLite.
- Alterações na origem criam novos conteúdos; versões anteriores permanecem no disco. Exclusões remotas não removem dados locais.
- Remover/desativar uma integração preserva seus arquivos, origens e histórico. Para revogar OAuth, use também o painel do provider.
- Uma trava por volume impede motores concorrentes. Use uma instância e um worker.

## Instalar no ZimaOS

Para a imagem de teste pronta e importação sem `.env`, veja [instalação de teste no ZimaOS](docs/zimaos-test.md). O YAML pessoal `zimaos-test.yaml` contém o token local e fica fora do Git.

1. Prepare diretórios exclusivos (UID/GID 1000 utilizados pelo container):

   ```sh
   sudo mkdir -p /DATA/CloudSync /DATA/CloudSyncSources
   sudo chown 1000:1000 /DATA/CloudSync
   cp .env.example .env
   openssl rand -hex 32
   ```

2. Edite `.env`: use o token gerado em `PCS_TOKEN`, `PCS_ROOT=/DATA/CloudSync`, `PCS_SOURCE_ROOT=/DATA/CloudSyncSources` e `PCS_IMAGE=ghcr.io/josegustavo14/personal-cloud-sync:latest`. O token do exemplo não é uma credencial de produção.

3. Até existir uma imagem publicada, execute a partir deste checkout:

   ```sh
   docker compose up -d --build
   docker compose ps
   curl --fail http://localhost:8080/health
   ```

4. Abra `http://ENDERECO-DO-ZIMAOS:8080` e informe o token. Autorize suas contas seguindo [providers](docs/providers.md). Adicione cada integração na Web UI e configure a frequência.

O volume é persistente:

```text
/DATA/CloudSync/
├── data/                  # conteúdos SHA-256, com extensão preservada
│   └── .parts/            # downloads incompletos, fora do índice
├── database/              # SQLite, WAL e trava do worker
├── config/                # rclone.conf com OAuth
└── logs/                  # eventos JSONL; histórico completo no SQLite
```

Não coloque a origem dentro do destino, nem monte `/DATA/Gallery/immich` como destino. O mount `/sources` é somente leitura. Para dispositivos, copie/exponha seus arquivos em uma pasta montada nessa origem; o app Android é um **cliente administrativo**, sem upload automático da galeria nesta versão.

## Atualizar sem reinstalar

Com o GHCR configurado e uma release publicada, altere a tag de `PCS_IMAGE` em `.env` para a versão desejada:

```sh
docker compose pull
docker compose up -d --no-build
docker compose ps
curl --fail http://localhost:8080/health
```

As migrations são aplicadas antes de servir a API. Recriar o container não recria o volume. Faça backup antes de atualizações, especialmente quando houver migration. [Backup, restauração e homologação](docs/operations.md).

## Immich

Adicione ao serviço do Immich um volume **somente leitura**:

```yaml
volumes:
  - /DATA/CloudSync/data:/mnt/cloud-sync:ro
```

No Immich, crie uma External Library apontando para `/mnt/cloud-sync` e exclua `**/.parts/**` da varredura. Configure a varredura no próprio Immich. A aplicação não acessa seu banco, não depende de sua disponibilidade e não escreve no diretório interno do Immich.

## Aplicativo Android

O código está em `android_app/`. Configure o endereço do servidor e o token ao abrir. Suporta LAN, Tailscale e HTTPS via reverse proxy; as credenciais são persistidas no armazenamento seguro do Android. Jobs pertencem ao servidor e continuam sem o app.

```sh
cd android_app
flutter pub get
flutter analyze
flutter test
flutter build apk --debug
```

O APK debug serve para homologação. Releases usam uma chave estável em GitHub Secrets; consulte [releases](docs/releases.md). HTTP é permitido para LAN confiável; use HTTPS ao expor por domínio.

## Desenvolvimento e testes

```sh
python3 -m venv .venv
.venv/bin/pip install -r backend/requirements-dev.txt
npm --prefix frontend ci
.venv/bin/pytest -q
npm --prefix frontend run lint
npm --prefix frontend test
npm --prefix frontend run build
cd android_app && flutter analyze && flutter test
```

Para executar o backend localmente, configure `PCS_ROOT`, `PCS_SOURCE_ROOT` (diretórios separados), `PCS_TOKEN` (32 ou mais caracteres) e opcionalmente `PCS_WEB_ROOT=CAMINHO_ABSOLUTO/frontend/dist`:

```sh
.venv/bin/uvicorn app.main:create_app --factory --app-dir backend --port 8080
```

O frontend de desenvolvimento usa `npm --prefix frontend run dev` e encaminha `/api` ao backend. Não exponha o servidor Vite à internet.

Teste integrado de persistência com containers temporários:

```sh
docker build -t personal-cloud-sync:dev .
python3 scripts/container_smoke.py personal-cloud-sync:dev
```

## API

Todas as rotas `/api` exigem `Authorization: Bearer TOKEN`. `/health` é público e não retorna dados pessoais.

| Operação | Rota |
| --- | --- |
| Dashboard | `GET /api/dashboard` |
| Contas | `GET/POST /api/accounts` |
| Agendamento, ativar/desativar | `PATCH /api/accounts/{id}` |
| Desativar integração preservando dados | `DELETE /api/accounts/{id}` |
| Sincronizar conta / todas | `POST /api/accounts/{id}/sync`, `POST /api/sync` |
| Histórico paginado | `GET /api/jobs?account_id=&limit=100&offset=0` |
| Cancelar | `POST /api/jobs/{id}/cancel` |
| Logs incrementais | `GET /api/jobs/{id}/logs?after=0` |
| Arquivos | `GET /api/files?q=&provider=&account_id=&extension=&sha256=&original_path=&offset=0` |
| Origens de um conteúdo | `GET /api/files/{sha256}/origins` |
| Remotes configurados, sem tokens | `GET /api/remotes` |
| Configurações e comandos OAuth | `GET /api/settings` |

## Limitações desta implementação

- OAuth é realizado pelo assistente oficial do rclone no terminal, inclusive autorização headless em outro computador. A Web UI e o app orientam o fluxo; não há callback OAuth próprio nem wizard OAuth embutido.
- Takeout importa os bytes de pastas, ZIP e TAR/TGZ, sem extrair caminhos do arquivo compactado. JSON sidecars são preservados, mas metadados não são mesclados em EXIF nem reconstruídos em álbuns do Immich.
- O incremental compara ID, tamanho e data de modificação da origem. Alterações que preservam todos esses metadados exigem nova importação. A deduplicação final utiliza exclusivamente SHA-256.
- Descoberta termina antes do download; listagens ficam em memória. Bibliotecas muito grandes precisam de benchmark e futura descoberta paginada.
- Retries reiniciam o `.part`; não há retomada por byte. Falhas mantêm o parcial para inspeção. Jobs interrompidos tornam-se `failed` após reinício; novo Sync Now ou próximo agendamento retoma pelo índice.
- Arquivos históricos não são coletados automaticamente. SQLite e disco devem ser monitorados; esta cópia local não substitui uma segunda cópia de backup.
- Não há multiusuário: o token concede acesso administrativo. Use firewall/Tailscale e TLS no reverse proxy. Tokens e logs brutos do rclone nunca são retornados.

## Git e CI

Trabalhe em branches `feat/*`, `fix/*` ou `ci/*`, use Conventional Commits e PRs para `main`. O workflow executa backend → frontend → Flutter → Docker e teste de persistência. Tags semânticas geram imagem amd64/arm64 no GHCR e APK assinado. Nenhuma credencial ou configuração OAuth real deve entrar no Git.
