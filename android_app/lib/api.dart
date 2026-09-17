import 'dart:convert';
import 'dart:math';
import 'package:http/http.dart' as http;

class Api {
  Api(String server, this.token, {http.Client? client})
    : base = Uri.parse(server.replaceFirst(RegExp(r'/+$'), '')),
      client = client ?? http.Client() {
    if (!['http', 'https'].contains(base.scheme) ||
        base.host.isEmpty ||
        base.userInfo.isNotEmpty ||
        base.hasQuery ||
        base.hasFragment) {
      throw const FormatException('Informe um endereço HTTP ou HTTPS válido.');
    }
    if (token.length < 32) {
      throw const FormatException(
        'O token deve conter pelo menos 32 caracteres.',
      );
    }
  }
  final Uri base;
  final String token;
  final http.Client client;
  Future<dynamic> get(String path) => send(path, method: 'GET');
  Future<dynamic> send(
    String path, {
    String method = 'POST',
    Object? body,
  }) async {
    final request = http.Request(method, Uri.parse('$base/api$path'))
      ..followRedirects = false;
    request.headers.addAll({
      'Authorization': 'Bearer $token',
      'Content-Type': 'application/json',
    });
    if (body != null) {
      request.body = jsonEncode(body);
    }
    final response = await http.Response.fromStream(
      await client.send(request).timeout(const Duration(seconds: 20)),
    ).timeout(const Duration(seconds: 20));
    if (response.statusCode == 401) {
      throw Exception('Token inválido. Verifique as configurações.');
    }
    if (response.statusCode >= 300) {
      dynamic detail;
      try {
        detail = (jsonDecode(response.body) as Map)['detail'];
      } catch (_) {
        /* Proxy errors use the fallback below. */
      }
      throw Exception(
        detail is String
            ? detail
            : 'Falha ao acessar o servidor (${response.statusCode}).',
      );
    }
    return jsonDecode(response.body);
  }

  void close() => client.close();
}

String formatBytes(num value) {
  if (value <= 0) {
    return '0 B';
  }
  final index = min((log(value) / log(1024)).floor(), 4);
  return '${(value / pow(1024, index)).toStringAsFixed(index == 0 ? 0 : 1)} ${['B', 'KB', 'MB', 'GB', 'TB'][index]}';
}

String formatDate(dynamic value) {
  final date = DateTime.tryParse(value?.toString() ?? '')?.toLocal();
  if (date == null) {
    return 'Ainda não';
  }
  return '${date.day.toString().padLeft(2, '0')}/${date.month.toString().padLeft(2, '0')}/${date.year} ${date.hour.toString().padLeft(2, '0')}:${date.minute.toString().padLeft(2, '0')}';
}

double jobProgress(Map job) => (job['found'] as num) == 0
    ? (job['status'] == 'completed' ? 1 : 0)
    : (((job['existing'] as num) +
                  (job['downloaded'] as num) +
                  (job['errors'] as num)) /
              (job['found'] as num))
          .clamp(0.0, 1.0);
