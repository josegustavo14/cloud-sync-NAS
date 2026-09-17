# Validação da implementação inicial

Execução local em 17/09/2026, macOS com OrbStack e Flutter 3.41.3.

- Backend: 16 testes aprovados, cobrindo deduplicação entre contas, conteúdo distinto, incremental, versões antigas preservadas, `.part`, falha de provider, restart, migrations, comandos remotos restritos, Takeout ZIP, paths/symlinks, API autenticada, cancelamento, exclusão lógica, trava de writer, recuperação de órfãos, agendamento e proteção contra sobrescrita de conteúdo corrompido.
- Frontend: lint, testes de apresentação/API e build de produção. Atualização de Vite/Vitest; auditoria npm sem vulnerabilidades na execução.
- Android: `flutter analyze`, `flutter test` e `flutter build apk --debug` concluídos. APK em `android_app/build/app/outputs/flutter-apk/app-debug.apk` (não versionado).
- Docker: build completo com React, Python e rclone aprovado; teste integrado em `scripts/container_smoke.py` aprovado para auth, dedup, origem preservada, reinício e recriação usando o mesmo volume.

Ainda precisam de validação externa:

- Interface no navegador: ferramenta de navegador indisponível nesta sessão; não foi feita inspeção visual.
- Contas OAuth reais dos três providers e respectivas permissões.
- Execução no ZimaOS real e montagem read-only no Immich.
- Instalação do APK em aparelho Android.
- Pipeline de release com chave de assinatura e publicação GHCR; o APK local é debug.

O teste de recriação valida o volume e a reexecução da migration inicial. Não equivale a testar migrations entre duas versões de produção já lançadas.
