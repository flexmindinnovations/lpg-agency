import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:device_identity/device_identity.dart';

class _Storage implements DeviceIdentityStorage {
  _Storage({this.name});

  String? name;

  @override
  Future<String?> readInstallId() async => 'install-id-0123456789abcdef';

  @override
  Future<void> writeInstallId(String value) async {}

  @override
  Future<String?> readName() async => name;

  @override
  Future<void> writeName(String value) async => name = value;
}

class _Details implements DeviceDetailsSource {
  const _Details();

  @override
  Future<DeviceDetails> read() async => const DeviceDetails(model: 'Redmi 12');
}

/// A device API that never touches the network and always says "approved".
class QuietDeviceApi extends DeviceApi {
  QuietDeviceApi() : super(ApiClient(baseUrl: 'https://api.test').dio);

  @override
  Future<Result<DeviceStatusReport>> me() async => const Success(
    DeviceStatusReport(control: 'off', status: null, allowed: true),
  );
}

/// A [DeviceControl] for widget tests: a named, allowed phone unless told
/// otherwise.
Future<DeviceControl> testDeviceControl({
  String? savedName = 'Van 2 phone',
  String? refusal,
}) async {
  final control = DeviceControl(
    identity: await DeviceIdentity.load(
      appType: 'admin_app',
      storage: _Storage(name: savedName),
      detailsSource: const _Details(),
    ),
    access: DeviceAccessController(api: QuietDeviceApi()),
  );
  if (refusal != null) control.access.reportRefusal(refusal);
  return control;
}
