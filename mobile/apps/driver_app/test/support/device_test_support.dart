import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:device_identity/device_identity.dart';

class _Storage implements DeviceIdentityStorage {
  @override
  Future<String?> readInstallId() async => 'install-id-0123456789abcdef';

  @override
  Future<void> writeInstallId(String value) async {}
}

class _Details implements DeviceDetailsSource {
  const _Details();

  @override
  Future<DeviceDetails> read() async => const DeviceDetails(model: 'Redmi 12');
}

/// A device API that never touches the network and always says "approved".
/// [needsName] makes it report a phone the agency has not seen, until
/// [setName] is called.
class QuietDeviceApi extends DeviceApi {
  QuietDeviceApi({this.needsName = false})
    : super(ApiClient(baseUrl: 'https://api.test').dio);

  bool needsName;
  String displayName = 'device_a1b2c3d4';

  @override
  Future<Result<DeviceStatusReport>> me() async => Success(_report());

  @override
  Future<Result<DeviceStatusReport>> setName(String name) async {
    needsName = false;
    displayName = name;
    return Success(_report());
  }

  DeviceStatusReport _report() => DeviceStatusReport(
    control: 'off',
    status: null,
    allowed: true,
    displayName: displayName,
    needsName: needsName,
  );
}

/// A [DeviceControl] for widget tests: a phone the agency already knows,
/// allowed, unless told otherwise. With [needsName] the agency reports a new
/// phone that still has to be named.
Future<DeviceControl> testDeviceControl({
  bool needsName = false,
  String? refusal,
}) async {
  final control = DeviceControl(
    identity: await DeviceIdentity.load(
      appType: 'driver_app',
      storage: _Storage(),
      detailsSource: const _Details(),
    ),
    access: DeviceAccessController(api: QuietDeviceApi(needsName: needsName)),
  );
  if (needsName) await control.access.refresh();
  if (refusal != null) control.access.reportRefusal(refusal);
  return control;
}
