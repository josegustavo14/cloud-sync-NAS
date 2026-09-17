import 'dart:convert';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:personal_cloud_sync/api.dart';

void main() {
  test('configurable server and header authentication', () async {
    final api = Api(
      'https://my-server.example/cloud/',
      'x' * 32,
      client: MockClient((request) async {
        expect(
          request.url.toString(),
          'https://my-server.example/cloud/api/dashboard',
        );
        expect(request.headers['Authorization'], 'Bearer ${'x' * 32}');
        return http.Response(jsonEncode({'files': 7}), 200);
      }),
    );
    expect((await api.get('/dashboard'))['files'], 7);
    api.close();
  });
  test('reject invalid addresses and credentials', () {
    expect(() => Api('file:///tmp', 'x' * 32), throwsFormatException);
    expect(
      () => Api('http://user:pass@server', 'x' * 32),
      throwsFormatException,
    );
    expect(() => Api('https://server', 'short'), throwsFormatException);
  });
  test('surface authentication failures', () async {
    final api = Api(
      'https://server',
      'x' * 32,
      client: MockClient((_) async => http.Response('{}', 401)),
    );
    await expectLater(api.get('/accounts'), throwsException);
  });
  test('progress excludes duplicate counter', () {
    expect(
      jobProgress({
        'found': 10,
        'existing': 4,
        'downloaded': 5,
        'duplicates': 3,
        'errors': 1,
      }),
      1,
    );
    expect(formatBytes(1024), '1.0 KB');
  });
}
