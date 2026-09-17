# Instalação de teste no ZimaOS

O workflow `Publish ZimaOS test image` publica `ghcr.io/josegustavo14/personal-cloud-sync:test` após os checks. Não depende dos secrets de assinatura Android e não representa uma release estável.

O arquivo pessoal `zimaos-test.yaml` fica na raiz do checkout e está no `.gitignore`. Ele contém um token de acesso local, volumes absolutos e metadados `x-casaos`, sem depender de `.env` ou de código-fonte no NAS. Não compartilhe esse arquivo nem publique seu token.

1. Confirme que o workflow de publicação terminou e que o pacote GHCR está público (Package settings → Change visibility → Public).
2. No ZimaOS, abra a instalação de aplicativo personalizado e importe o conteúdo de `zimaos-test.yaml`.
3. Acesse `http://IP-DO-ZIMAOS:8088` e use o valor de `PCS_TOKEN` presente no YAML.
4. Coloque os arquivos de teste em `/DATA/CloudSyncSources`, cadastre uma conta filesystem com localização `.` e execute Sincronizar.

O estado fica em `/DATA/CloudSync`. A origem é montada como somente leitura. Na primeira inicialização, o entrypoint prepara apenas os diretórios da aplicação e muda para UID/GID 1000 antes de executar a API. Não muda permissões nem propriedade de arquivos recursivamente.

OAuth usa o rclone do container:

```sh
docker exec -it --user 1000:1000 personal-cloud-sync-test rclone config --config /DATA/CloudSync/config/rclone.conf
```

Reautenticação: use `rclone config reconnect NOME:` com o mesmo `--config`. A conta aparece na interface após concluir o assistente. No ZimaOS, a instalação personalizada pode usar nomes de projeto diferentes; por isso este guia usa o nome explícito do container.

Para atualizar, faça pull da tag `test` e recrie o container conservando os mesmos volumes. Essa tag acompanha a versão de teste; para reproduzir uma versão específica, use a tag `sha-COMMIT` publicada pelo mesmo workflow.

Referência: [Docker Compose e x-casaos no ZimaOS](https://www.zimaspace.com/docs/developer/app-store-compose-x-casaos).
