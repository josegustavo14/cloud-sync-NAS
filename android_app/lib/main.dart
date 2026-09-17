import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'api.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const CloudSyncApp());
}

class CloudSyncApp extends StatelessWidget {
  const CloudSyncApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'Personal Cloud Sync',
    debugShowCheckedModeBanner: false,
    theme: ThemeData(
      colorScheme: ColorScheme.fromSeed(seedColor: const Color(0xff215cb5)),
      scaffoldBackgroundColor: const Color(0xfff6f8fc),
      useMaterial3: true,
      inputDecorationTheme: const InputDecorationTheme(
        border: OutlineInputBorder(),
      ),
    ),
    home: const Home(),
  );
}

const providerNames = {
  'google_drive': 'Google Drive',
  'onedrive': 'OneDrive',
  'dropbox': 'Dropbox',
  'filesystem': 'Dispositivo / pasta',
  'takeout': 'Google Takeout',
};
const states = {
  'started': 'Na fila',
  'running': 'Sincronizando',
  'completed': 'Concluído',
  'failed': 'Falhou',
  'cancelled': 'Cancelado',
};
const destinations = [
  NavigationDestination(icon: Icon(Icons.dashboard_outlined), label: 'Início'),
  NavigationDestination(icon: Icon(Icons.cloud_outlined), label: 'Contas'),
  NavigationDestination(icon: Icon(Icons.sync), label: 'Sync'),
  NavigationDestination(icon: Icon(Icons.folder_outlined), label: 'Arquivos'),
  NavigationDestination(icon: Icon(Icons.history), label: 'Histórico'),
  NavigationDestination(icon: Icon(Icons.settings_outlined), label: 'Ajustes'),
];

class Home extends StatefulWidget {
  const Home({super.key});
  @override
  State<Home> createState() => _HomeState();
}

class _HomeState extends State<Home> {
  final storage = const FlutterSecureStorage();
  final server = TextEditingController(),
      token = TextEditingController(),
      search = TextEditingController(),
      extension = TextEditingController();
  Api? api;
  Timer? timer;
  int selected = 0, filePage = 0, historyPage = 0, totalFiles = 0;
  String fileProvider = '', fileAccount = '', historyAccount = '';
  String? error;
  bool loading = false, refreshing = false;
  Map<String, dynamic> dashboard = {};
  List<dynamic> accounts = [], jobs = [], files = [];
  @override
  void initState() {
    super.initState();
    restore();
  }

  Future<void> restore() async {
    try {
      server.text = await storage.read(key: 'server') ?? '';
      token.text = await storage.read(key: 'token') ?? '';
      if (server.text.isNotEmpty && token.text.isNotEmpty && mounted) {
        await connect();
      }
    } catch (_) {
      if (mounted) {
        setState(
          () => error =
              'Não foi possível ler as credenciais. Configure o acesso.',
        );
      }
    }
  }

  @override
  void dispose() {
    timer?.cancel();
    api?.close();
    for (final c in [server, token, search, extension]) {
      c.dispose();
    }
    super.dispose();
  }

  Future<void> connect() async {
    setState(() {
      loading = true;
      error = null;
    });
    Api? candidate;
    try {
      candidate = Api(server.text.trim(), token.text.trim());
      final data = await candidate.get('/dashboard');
      await storage.write(key: 'server', value: server.text.trim());
      await storage.write(key: 'token', value: token.text.trim());
      if (!mounted) {
        candidate.close();
        return;
      }
      api?.close();
      api = candidate;
      setState(() {
        dashboard = data as Map<String, dynamic>;
        selected = 0;
      });
      timer?.cancel();
      timer = Timer.periodic(const Duration(seconds: 3), (_) => refresh());
      await refresh();
    } catch (e) {
      candidate?.close();
      if (mounted) {
        setState(() => error = e.toString());
      }
    } finally {
      if (mounted) {
        setState(() => loading = false);
      }
    }
  }

  Future<void> refresh() async {
    if (api == null || refreshing) {
      return;
    }
    refreshing = true;
    final client = api!;
    try {
      final data = await Future.wait([
        client.get('/dashboard'),
        client.get('/accounts'),
        client.get(
          '/jobs?offset=${historyPage * 100}${historyAccount.isEmpty ? '' : '&account_id=$historyAccount'}',
        ),
      ]);
      if (mounted && client == api) {
        setState(() {
          dashboard = data[0] as Map<String, dynamic>;
          accounts = data[1] as List;
          jobs = data[2] as List;
          error = null;
        });
      }
    } catch (e) {
      if (mounted && client == api) {
        setState(() => error = e.toString());
      }
    } finally {
      refreshing = false;
    }
  }

  Future<void> action(
    String path, {
    Object? body,
    String method = 'POST',
  }) async {
    setState(() => loading = true);
    try {
      await api!.send(path, body: body, method: method);
      await refresh();
    } catch (e) {
      if (mounted) {
        setState(() => error = e.toString());
      }
    } finally {
      if (mounted) {
        setState(() => loading = false);
      }
    }
  }

  Future<void> loadFiles() async {
    try {
      final query = Uri(
        queryParameters: {
          'q': search.text,
          'provider': fileProvider,
          'extension': extension.text,
          'offset': '${filePage * 100}',
          if (fileAccount.isNotEmpty) 'account_id': fileAccount,
        },
      ).query;
      final result = await api!.get('/files?$query') as Map<String, dynamic>;
      if (mounted) {
        setState(() {
          files = result['items'] as List;
          totalFiles = result['total'] as int;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() => error = e.toString());
      }
    }
  }

  Future<void> addAccount() async {
    final added = await showDialog<bool>(
      context: context,
      builder: (_) => AccountDialog(api: api!),
    );
    if (added == true) {
      await refresh();
    }
  }

  Widget connectionForm() => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      const Icon(Icons.cloud_outlined, size: 64, color: Color(0xff215cb5)),
      const SizedBox(height: 20),
      const Text(
        'Suas nuvens. Sua casa.',
        style: TextStyle(fontSize: 28, fontWeight: FontWeight.w600),
      ),
      const SizedBox(height: 8),
      const Text('Conecte ao seu servidor por LAN, Tailscale ou domínio.'),
      const SizedBox(height: 24),
      TextField(
        controller: server,
        keyboardType: TextInputType.url,
        autocorrect: false,
        decoration: const InputDecoration(
          labelText: 'Endereço do servidor',
          hintText: 'https://cloud.seudominio.com',
        ),
      ),
      const SizedBox(height: 16),
      TextField(
        controller: token,
        obscureText: true,
        autocorrect: false,
        enableSuggestions: false,
        decoration: const InputDecoration(labelText: 'Token de acesso'),
      ),
      const SizedBox(height: 20),
      FilledButton(
        onPressed: loading ? null : connect,
        child: Text(loading ? 'Conectando…' : 'Conectar'),
      ),
      const SizedBox(height: 12),
      const Text(
        'Use HTTPS por domínio. HTTP está disponível para redes locais confiáveis.',
      ),
    ],
  );
  Widget stat(String title, Object value, IconData icon) => Card(
    child: ListTile(
      leading: Icon(icon, color: const Color(0xff215cb5)),
      title: Text(
        '$value',
        style: const TextStyle(fontSize: 23, fontWeight: FontWeight.w600),
      ),
      subtitle: Text(title),
    ),
  );
  Widget dashboardPage() => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      Container(
        padding: const EdgeInsets.all(24),
        decoration: BoxDecoration(
          color: const Color(0xffe6effd),
          borderRadius: BorderRadius.circular(18),
        ),
        child: const Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(Icons.shield_outlined, color: Color(0xff215cb5)),
            SizedBox(height: 14),
            Text(
              'Sua biblioteca,\nno seu servidor.',
              style: TextStyle(fontSize: 28, fontWeight: FontWeight.w600),
            ),
            SizedBox(height: 12),
            Text('Cópias locais. Origens preservadas.'),
          ],
        ),
      ),
      const SizedBox(height: 16),
      stat('Arquivos únicos', dashboard['files'] ?? 0, Icons.folder_outlined),
      stat(
        'Contas conectadas',
        dashboard['accounts'] ?? 0,
        Icons.cloud_outlined,
      ),
      stat(
        'Biblioteca local',
        formatBytes(dashboard['stored_bytes'] ?? 0),
        Icons.storage,
      ),
      stat(
        'Espaço disponível',
        formatBytes(dashboard['storage']?['free'] ?? 0),
        Icons.sd_storage_outlined,
      ),
      ListTile(
        title: const Text('Última sincronização'),
        subtitle: Text(formatDate(dashboard['last_sync'])),
      ),
      ListTile(
        title: const Text('Próxima sincronização'),
        subtitle: Text(formatDate(dashboard['next_sync'])),
      ),
      FilledButton.icon(
        onPressed: loading ? null : () => action('/sync'),
        icon: const Icon(Icons.sync),
        label: const Text('Sincronizar tudo'),
      ),
      if ((dashboard['recent_errors'] as List? ?? []).isNotEmpty)
        const Padding(
          padding: EdgeInsets.all(16),
          child: Text(
            'Há erros recentes. Consulte os logs no histórico.',
            style: TextStyle(color: Colors.red),
          ),
        ),
    ],
  );
  Widget accountsPage() => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      FilledButton.icon(
        onPressed: addAccount,
        icon: const Icon(Icons.add),
        label: const Text('Adicionar conta'),
      ),
      const SizedBox(height: 16),
      if (accounts.isEmpty)
        const Padding(
          padding: EdgeInsets.all(20),
          child: Text('Adicione uma origem para começar.'),
        ),
      ...accounts.map(
        (a) => Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                ListTile(
                  contentPadding: EdgeInsets.zero,
                  leading: const Icon(Icons.cloud_outlined),
                  title: Text(a['name']),
                  subtitle: Text(providerNames[a['provider']] ?? a['provider']),
                  trailing: Switch(
                    value: a['enabled'] == 1,
                    onChanged: loading
                        ? null
                        : (v) => action(
                            '/accounts/${a['id']}',
                            method: 'PATCH',
                            body: {'enabled': v},
                          ),
                  ),
                ),
                DropdownButton<int>(
                  isExpanded: true,
                  value: a['interval_minutes'] as int,
                  items:
                      {
                            ...[0, 60, 360, 1440, 10080],
                            a['interval_minutes'] as int,
                          }
                          .map(
                            (m) => DropdownMenuItem(
                              value: m,
                              child: Text(
                                m == 0 ? 'Somente manual' : 'A cada $m minutos',
                              ),
                            ),
                          )
                          .toList(),
                  onChanged: loading
                      ? null
                      : (v) => action(
                          '/accounts/${a['id']}',
                          method: 'PATCH',
                          body: {'interval_minutes': v},
                        ),
                ),
                OutlinedButton.icon(
                  onPressed: loading || a['enabled'] != 1
                      ? null
                      : () => action('/accounts/${a['id']}/sync'),
                  icon: const Icon(Icons.sync),
                  label: const Text('Sincronizar agora'),
                ),
              ],
            ),
          ),
        ),
      ),
    ],
  );
  Widget jobCard(dynamic j) => Card(
    child: Padding(
      padding: const EdgeInsets.all(18),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            j['account_name'],
            style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
          ),
          Text('${states[j['status']]} • ${formatDate(j['started_at'])}'),
          const SizedBox(height: 18),
          Wrap(
            spacing: 22,
            runSpacing: 12,
            children:
                {
                      'found': 'Encontrados',
                      'existing': 'Existentes',
                      'new': 'Novos',
                      'duplicates': 'Duplicados',
                      'downloaded': 'Baixados',
                      'errors': 'Erros',
                    }.entries
                    .map(
                      (e) => Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            '${j[e.key]}',
                            style: const TextStyle(fontSize: 22),
                          ),
                          Text(e.value),
                        ],
                      ),
                    )
                    .toList(),
          ),
          const SizedBox(height: 18),
          LinearProgressIndicator(value: jobProgress(j)),
          const SizedBox(height: 8),
          if (j['current_file'] != null)
            Text(
              j['current_file'],
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
            ),
          Row(
            children: [
              TextButton(
                onPressed: () => showDialog<void>(
                  context: context,
                  builder: (_) =>
                      JobLogs(api: api!, job: Map<String, dynamic>.from(j)),
                ),
                child: const Text('Ver logs'),
              ),
              if (['started', 'running'].contains(j['status']))
                TextButton(
                  onPressed: loading
                      ? null
                      : () => action('/jobs/${j['id']}/cancel'),
                  child: const Text('Cancelar'),
                ),
            ],
          ),
        ],
      ),
    ),
  );
  Widget jobsPage(bool active) {
    final rows = active ? dashboard['active_jobs'] as List? ?? [] : jobs;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (!active)
          DropdownButtonFormField<String>(
            initialValue: historyAccount,
            decoration: const InputDecoration(labelText: 'Conta'),
            items: [
              const DropdownMenuItem(value: '', child: Text('Todas as contas')),
              ...accounts.map(
                (a) => DropdownMenuItem(
                  value: '${a['id']}',
                  child: Text(a['name']),
                ),
              ),
            ],
            onChanged: (v) {
              setState(() {
                historyAccount = v!;
                historyPage = 0;
              });
              refresh();
            },
          ),
        if (rows.isEmpty)
          Padding(
            padding: const EdgeInsets.all(24),
            child: Text(
              active
                  ? 'Nenhuma sincronização em andamento. Os jobs continuam no servidor mesmo com o celular desligado.'
                  : 'Nenhuma sincronização registrada.',
            ),
          ),
        ...rows.map(jobCard),
        if (!active)
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              TextButton(
                onPressed: historyPage == 0
                    ? null
                    : () {
                        setState(() => historyPage--);
                        refresh();
                      },
                child: const Text('Anterior'),
              ),
              Text('Página ${historyPage + 1}'),
              TextButton(
                onPressed: rows.length < 100
                    ? null
                    : () {
                        setState(() => historyPage++);
                        refresh();
                      },
                child: const Text('Próxima'),
              ),
            ],
          ),
      ],
    );
  }

  Widget filesPage() => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      TextField(
        controller: search,
        decoration: const InputDecoration(
          labelText: 'Nome, caminho ou SHA-256',
          prefixIcon: Icon(Icons.search),
        ),
        onSubmitted: (_) {
          filePage = 0;
          loadFiles();
        },
      ),
      const SizedBox(height: 12),
      DropdownButtonFormField<String>(
        initialValue: fileProvider,
        isExpanded: true,
        decoration: const InputDecoration(labelText: 'Provider'),
        items: [
          const DropdownMenuItem(value: '', child: Text('Todos os providers')),
          ...providerNames.entries.map(
            (e) => DropdownMenuItem(value: e.key, child: Text(e.value)),
          ),
        ],
        onChanged: (v) {
          fileProvider = v!;
          filePage = 0;
          loadFiles();
        },
      ),
      const SizedBox(height: 12),
      DropdownButtonFormField<String>(
        initialValue: fileAccount,
        isExpanded: true,
        decoration: const InputDecoration(labelText: 'Conta'),
        items: [
          const DropdownMenuItem(value: '', child: Text('Todas as contas')),
          ...accounts.map(
            (a) =>
                DropdownMenuItem(value: '${a['id']}', child: Text(a['name'])),
          ),
        ],
        onChanged: (v) {
          fileAccount = v!;
          filePage = 0;
          loadFiles();
        },
      ),
      const SizedBox(height: 12),
      TextField(
        controller: extension,
        decoration: const InputDecoration(labelText: 'Extensão (ex.: jpg)'),
        onSubmitted: (_) {
          filePage = 0;
          loadFiles();
        },
      ),
      TextButton.icon(
        onPressed: () {
          filePage = 0;
          loadFiles();
        },
        icon: const Icon(Icons.search),
        label: const Text('Buscar arquivos'),
      ),
      Text('$totalFiles origem(ns) encontrada(s)'),
      ...files.map(
        (f) => Card(
          child: ListTile(
            leading: const Icon(Icons.insert_drive_file_outlined),
            title: Text(f['name']),
            subtitle: Text('${f['account_name']} • ${formatBytes(f['size'])}'),
            onTap: () async {
              try {
                final origins =
                    await api!.get('/files/${f['sha256']}/origins') as List;
                if (!mounted) {
                  return;
                }
                await showDialog<void>(
                  context: context,
                  builder: (context) => AlertDialog(
                    title: Text(f['name']),
                    content: SingleChildScrollView(
                      child: SelectableText(
                        'SHA-256\n${f['sha256']}\n\nCópia local\n${f['local_path']}\n\nOrigens\n${origins.map((o) => '${o['account_name']}: ${o['original_path']}').join('\n')}',
                      ),
                    ),
                    actions: [
                      TextButton(
                        onPressed: () => Navigator.pop(context),
                        child: const Text('Fechar'),
                      ),
                    ],
                  ),
                );
              } catch (e) {
                if (mounted) {
                  setState(() => error = e.toString());
                }
              }
            },
          ),
        ),
      ),
      Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          TextButton(
            onPressed: filePage == 0
                ? null
                : () {
                    filePage--;
                    loadFiles();
                  },
            child: const Text('Anterior'),
          ),
          Text('Página ${filePage + 1}'),
          TextButton(
            onPressed: (filePage + 1) * 100 >= totalFiles
                ? null
                : () {
                    filePage++;
                    loadFiles();
                  },
            child: const Text('Próxima'),
          ),
        ],
      ),
    ],
  );
  Widget settingsPage() => Column(
    crossAxisAlignment: CrossAxisAlignment.stretch,
    children: [
      connectionForm(),
      const Divider(height: 40),
      const Text('Autorizar contas', style: TextStyle(fontSize: 20)),
      const SizedBox(height: 12),
      const Text(
        'Execute no servidor o assistente rclone para OAuth. No Google Drive escolha drive.readonly.',
      ),
      const SelectableText(
        'docker compose exec cloud-sync rclone config --config /DATA/CloudSync/config/rclone.conf',
      ),
      const SizedBox(height: 16),
      const Text('Para reautenticar, substitua REMOTE pelo nome da conta:'),
      const SelectableText(
        'docker compose exec cloud-sync rclone config reconnect REMOTE: --config /DATA/CloudSync/config/rclone.conf',
      ),
      const Divider(height: 40),
      const Text('Immich External Library', style: TextStyle(fontSize: 20)),
      const SizedBox(height: 12),
      const SelectableText('/DATA/CloudSync/data:/mnt/cloud-sync:ro'),
      TextButton(
        onPressed: () => Clipboard.setData(
          const ClipboardData(text: '/DATA/CloudSync/data:/mnt/cloud-sync:ro'),
        ),
        child: const Text('Copiar volume somente leitura'),
      ),
      TextButton(
        onPressed: () async {
          timer?.cancel();
          api?.close();
          await storage.deleteAll();
          if (mounted) {
            setState(() {
              api = null;
              token.clear();
              dashboard = {};
              accounts = [];
              jobs = [];
              files = [];
              error = null;
            });
          }
        },
        child: const Text('Sair e remover credenciais'),
      ),
    ],
  );
  @override
  Widget build(BuildContext context) => Scaffold(
    appBar: AppBar(
      title: const Text('Personal Cloud Sync'),
      actions: [
        if (api != null)
          IconButton(
            onPressed: refresh,
            icon: const Icon(Icons.refresh),
            tooltip: 'Atualizar',
          ),
      ],
    ),
    body: RefreshIndicator(
      onRefresh: refresh,
      child: ListView(
        padding: const EdgeInsets.all(20),
        physics: const AlwaysScrollableScrollPhysics(),
        children: [
          if (error != null)
            Card(
              color: Theme.of(context).colorScheme.errorContainer,
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Text(error!),
              ),
            ),
          if (loading) const LinearProgressIndicator(),
          if (api == null)
            connectionForm()
          else
            switch (selected) {
              0 => dashboardPage(),
              1 => accountsPage(),
              2 => jobsPage(true),
              3 => filesPage(),
              4 => jobsPage(false),
              _ => settingsPage(),
            },
        ],
      ),
    ),
    bottomNavigationBar: api == null
        ? null
        : NavigationBar(
            selectedIndex: selected,
            labelBehavior: NavigationDestinationLabelBehavior.onlyShowSelected,
            destinations: destinations,
            onDestinationSelected: (value) {
              setState(() => selected = value);
              if (value == 3) {
                loadFiles();
              }
            },
          ),
  );
}

class AccountDialog extends StatefulWidget {
  const AccountDialog({super.key, required this.api});
  final Api api;
  @override
  State<AccountDialog> createState() => _AccountDialogState();
}

class _AccountDialogState extends State<AccountDialog> {
  final name = TextEditingController(), location = TextEditingController();
  String provider = 'filesystem';
  int interval = 360;
  String? error;
  bool saving = false;
  @override
  void dispose() {
    name.dispose();
    location.dispose();
    super.dispose();
  }

  Future<void> save() async {
    setState(() {
      saving = true;
      error = null;
    });
    try {
      await widget.api.send(
        '/accounts',
        body: {
          'name': name.text,
          'provider': provider,
          'location': location.text,
          'interval_minutes': interval,
        },
      );
      if (mounted) {
        Navigator.pop(context, true);
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          error = e.toString();
          saving = false;
        });
      }
    }
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: const Text('Adicionar conta'),
    content: SizedBox(
      width: 400,
      child: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: name,
              decoration: const InputDecoration(labelText: 'Nome da conta'),
            ),
            const SizedBox(height: 16),
            DropdownButtonFormField<String>(
              initialValue: provider,
              isExpanded: true,
              items: providerNames.entries
                  .map(
                    (e) => DropdownMenuItem(value: e.key, child: Text(e.value)),
                  )
                  .toList(),
              onChanged: (v) => setState(() => provider = v!),
              decoration: const InputDecoration(labelText: 'Provider'),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: location,
              decoration: InputDecoration(
                labelText: ['filesystem', 'takeout'].contains(provider)
                    ? 'Caminho dentro de /sources'
                    : 'Remote, ex.: pessoal:',
              ),
            ),
            const SizedBox(height: 16),
            DropdownButtonFormField<int>(
              initialValue: interval,
              items: const [
                DropdownMenuItem(value: 0, child: Text('Manual')),
                DropdownMenuItem(value: 60, child: Text('A cada hora')),
                DropdownMenuItem(value: 360, child: Text('A cada 6 horas')),
                DropdownMenuItem(value: 1440, child: Text('Diariamente')),
              ],
              onChanged: (v) => interval = v!,
              decoration: const InputDecoration(labelText: 'Frequência'),
            ),
            const SizedBox(height: 16),
            const Text(
              'Autorize as contas de nuvem pelo rclone no servidor. As instruções estão em Ajustes.',
            ),
            if (error != null)
              Text(error!, style: const TextStyle(color: Colors.red)),
          ],
        ),
      ),
    ),
    actions: [
      TextButton(
        onPressed: saving ? null : () => Navigator.pop(context),
        child: const Text('Cancelar'),
      ),
      FilledButton(
        onPressed: saving ? null : save,
        child: Text(saving ? 'Adicionando…' : 'Adicionar'),
      ),
    ],
  );
}

class JobLogs extends StatefulWidget {
  const JobLogs({super.key, required this.api, required this.job});
  final Api api;
  final Map<String, dynamic> job;
  @override
  State<JobLogs> createState() => _JobLogsState();
}

class _JobLogsState extends State<JobLogs> {
  final List<dynamic> rows = [];
  Timer? timer;
  String? error;
  bool reading = false;
  @override
  void initState() {
    super.initState();
    read();
    timer = Timer.periodic(const Duration(seconds: 2), (_) => read());
  }

  Future<void> read() async {
    if (reading) {
      return;
    }
    reading = true;
    try {
      final result =
          await widget.api.get(
                '/jobs/${widget.job['id']}/logs?after=${rows.isEmpty ? 0 : rows.last['id']}',
              )
              as List;
      if (mounted) {
        setState(() => rows.addAll(result));
      }
    } catch (e) {
      if (mounted) {
        setState(() => error = e.toString());
      }
    } finally {
      reading = false;
    }
  }

  @override
  void dispose() {
    timer?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AlertDialog(
    title: Text('Logs: ${widget.job['account_name']}'),
    content: SizedBox(
      width: 450,
      child: SingleChildScrollView(
        child: SelectableText(
          error ??
              (rows.isEmpty
                  ? 'Aguardando logs…'
                  : rows
                        .map(
                          (l) =>
                              '${formatDate(l['created_at'])} [${l['level']}] ${l['message']}',
                        )
                        .join('\n\n')),
        ),
      ),
    ),
    actions: [
      TextButton(
        onPressed: () => Navigator.pop(context),
        child: const Text('Fechar'),
      ),
    ],
  );
}
