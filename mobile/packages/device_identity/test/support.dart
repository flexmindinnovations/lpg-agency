import 'dart:convert';
import 'dart:typed_data';

import 'package:device_identity/device_identity.dart';
import 'package:dio/dio.dart';

/// A [DeviceIdentityStorage] that keeps everything in memory.
class MemoryStorage implements DeviceIdentityStorage {
  MemoryStorage({this.installId, this.name});

  String? installId;
  String? name;
  int installIdWrites = 0;

  @override
  Future<String?> readInstallId() async => installId;

  @override
  Future<void> writeInstallId(String value) async {
    installIdWrites++;
    installId = value;
  }

  @override
  Future<String?> readName() async => name;

  @override
  Future<void> writeName(String value) async => name = value;
}

class FakeDetailsSource implements DeviceDetailsSource {
  const FakeDetailsSource([
    this.details = const DeviceDetails(
      manufacturer: 'Xiaomi',
      model: 'Redmi 12',
      osVersion: 'Android 13',
      appVersion: '1.4.0',
      platform: 'android',
      hardwareId: 'android-id-1',
    ),
  ]);

  final DeviceDetails details;

  @override
  Future<DeviceDetails> read() async => details;
}

Future<DeviceIdentity> loadIdentity({
  MemoryStorage? storage,
  String appType = 'driver_app',
  DeviceDetailsSource source = const FakeDetailsSource(),
}) => DeviceIdentity.load(
  appType: appType,
  storage: storage ?? MemoryStorage(),
  detailsSource: source,
);

class FakeAdapter implements HttpClientAdapter {
  FakeAdapter(this.handler);

  final ResponseBody Function(RequestOptions options) handler;
  final List<RequestOptions> seen = [];

  @override
  Future<ResponseBody> fetch(
    RequestOptions options,
    Stream<Uint8List>? requestStream,
    Future<void>? cancelFuture,
  ) async {
    seen.add(options);
    return handler(options);
  }

  @override
  void close({bool force = false}) {}
}

ResponseBody jsonBody(Object body, int status) => ResponseBody.fromString(
  jsonEncode(body),
  status,
  headers: {
    Headers.contentTypeHeader: [Headers.jsonContentType],
  },
);

/// A Dio whose every request goes to [handler], with all statuses delivered
/// as responses (so `DioException`s come from `validateStatus`, as in the app).
Dio fakeDio(ResponseBody Function(RequestOptions options) handler) {
  final dio = Dio(BaseOptions(baseUrl: 'https://api.test'));
  dio.httpClientAdapter = FakeAdapter(handler);
  return dio;
}
