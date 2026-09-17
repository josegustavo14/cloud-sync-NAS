# GitHub, GHCR e releases

## Primeiro envio

Crie/indique o repositório de destino e configure `origin`. Revise a branch `feat/personal-cloud-sync`, execute os checks e abra PR. Como o projeto começou vazio, o primeiro commit pode servir de base para `main`; a implementação deve chegar pela revisão da branch.

Proteja `main` com PR obrigatório e checks do workflow CI. Use Conventional Commits e commits pequenos por mudança lógica. O template de PR inclui problema, resultado, validação e impactos.

## Secrets Android

Crie uma chave de assinatura **uma única vez**, guarde-a em backup seguro e configure:

- `ANDROID_KEYSTORE_BASE64`: arquivo JKS em base64.
- `ANDROID_KEYSTORE_PASSWORD`.
- `ANDROID_KEY_ALIAS`.
- `ANDROID_KEY_PASSWORD`.

Nunca adicione a chave, senha ou `key.properties` ao Git. A mesma chave e application ID permitem atualizar um APK já instalado. O `versionCode` usa o número crescente da execução do workflow. Não reinicie essa sequência abaixo do último APK distribuído.

O `GITHUB_TOKEN` do workflow recebe `packages: write` para publicar a imagem e `contents: write` apenas no job que cria a release. Não é necessário guardar um PAT pessoal para o fluxo padrão. Torne o pacote GHCR público ou configure autenticação de pull no ZimaOS.

## Tag versionada

Depois da homologação e do merge, atualize as versões em `backend/app/main.py`, `frontend/package.json`/lockfile e `android_app/pubspec.yaml`/lockfile em um commit. Crie uma tag semântica, por exemplo `v1.0.0`, e envie-a.

O workflow executa CI novamente, publica imagem para Linux amd64/arm64 com tags `1.0.0`, `1.0`, `latest`, compila o APK assinado e cria a GitHub Release com `personal-cloud-sync-v1.0.0.apk`. Se assinatura ou testes falharem, a release não é criada. Não crie `v1.0.0` antes de cumprir os critérios de homologação.

O APK release local exige as mesmas variáveis `ANDROID_KEYSTORE_PATH`, `ANDROID_KEYSTORE_PASSWORD`, `ANDROID_KEY_ALIAS`, `ANDROID_KEY_PASSWORD`. Sem chave, use `flutter build apk --debug` para testes; builds de produção não usam assinatura debug implicitamente.
