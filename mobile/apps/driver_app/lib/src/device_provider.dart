import 'package:device_identity/device_identity.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// The phone's identity and approval state (ADR-071). `main()` sets it up
/// before the first frame — it has to be plugged into the API client before
/// the session is restored — and overrides this provider; the default fails
/// loudly if that is missed.
final deviceControlProvider = Provider<DeviceControl>(
  (ref) => throw UnimplementedError(
    'deviceControlProvider must be overridden in main().',
  ),
);
