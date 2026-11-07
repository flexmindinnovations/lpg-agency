import 'dart:async';

import 'package:flutter/foundation.dart';

import 'device_api.dart';

/// Where this phone stands with the agency.
enum DeviceAccess {
  /// Nothing is holding the phone back (or nothing is known to).
  allowed,

  /// Signed in, but waiting for the agency to approve the phone.
  pending,

  /// The agency blocked (or removed) the phone.
  blocked,
}

/// Holds the phone's [DeviceAccess] and keeps it current (ADR-071).
///
/// It changes when:
/// - an API call is refused with `DEVICE_PENDING` / `DEVICE_BLOCKED` /
///   `DEVICE_REMOVED` ([reportRefusal]);
/// - the server is asked directly ([refresh]) — on the waiting screen's timer
///   and button, when the app returns to the foreground, and when the server
///   sends `device.status_changed` over the live connection;
/// - the user leaves the blocked screen to try signing in again ([reset]).
///
/// A [ChangeNotifier] so `go_router`'s `refreshListenable` re-evaluates its
/// redirect the moment the state changes.
class DeviceAccessController extends ChangeNotifier {
  DeviceAccessController({required this.api, this.onBlocked, this.onResumed});

  final DeviceApi api;

  /// Called once when the phone becomes blocked — the app signs the user out
  /// (their unsent work stays on the phone).
  final Future<void> Function()? onBlocked;

  /// Called when the phone goes from blocked or waiting back to allowed — the
  /// Driver app resumes sending its saved deliveries.
  final void Function()? onResumed;

  DeviceAccess _access = DeviceAccess.allowed;
  bool _checking = false;
  bool _needsName = false;
  String? _displayName;

  DeviceAccess get access => _access;

  /// True when the agency has not seen this phone before and nobody has named
  /// it yet — the app asks for a name once. A phone the agency already knows
  /// (even after a reinstall) is never asked.
  bool get needsName => _needsName;

  /// The name the agency has for this phone (a generated `device_<code>`
  /// until the user picks one), or `null` before the server has answered.
  String? get displayName => _displayName;

  /// True while a [refresh] is running (the waiting screen shows progress).
  bool get isChecking => _checking;

  /// The server refused a call from this phone.
  void reportRefusal(String errorCode) {
    switch (errorCode) {
      case 'DEVICE_PENDING':
        _set(DeviceAccess.pending);
      case 'DEVICE_BLOCKED':
      case 'DEVICE_REMOVED':
        _set(DeviceAccess.blocked);
      default:
        break; // DEVICE_REQUIRED is answered by the API client's refresh.
    }
  }

  /// Asks the server where this phone stands. A failed check (no network, a
  /// 401) changes nothing: being offline must never lock a driver out.
  Future<void> refresh() async {
    if (_checking) return;
    _checking = true;
    notifyListeners();
    try {
      final result = await api.me();
      result.when(
        onSuccess: _apply,
        onFailure: (failure) {
          final code = failure.errorCode;
          if (code != null) reportRefusal(code);
        },
      );
    } finally {
      _checking = false;
      notifyListeners();
    }
  }

  /// Gives this phone a name. Returns `null` when the agency accepted it, else
  /// the sentence to show (for a name another phone already has, it includes
  /// the name to try instead).
  Future<String?> setName(String name) async {
    final result = await api.setName(name);
    String? problem;
    result.when(
      onSuccess: _apply,
      onFailure: (failure) => problem = failure.message,
    );
    notifyListeners();
    return problem;
  }

  /// Back to "allowed" so the sign-in screen can try again; a refusal at
  /// sign-in puts the state straight back.
  void reset() => _set(DeviceAccess.allowed);

  void _apply(DeviceStatusReport report) {
    _needsName = report.needsName;
    _displayName = report.displayName ?? _displayName;
    if (!report.allowed) {
      switch (report.status) {
        case 'pending':
          _set(DeviceAccess.pending);
        case 'blocked':
        case 'removed':
          _set(DeviceAccess.blocked);
        default:
          break;
      }
      return;
    }
    _set(DeviceAccess.allowed);
  }

  void _set(DeviceAccess next) {
    if (_access == next) return;
    final previous = _access;
    _access = next;
    notifyListeners();
    if (next == DeviceAccess.blocked) {
      final callback = onBlocked;
      if (callback != null) unawaited(callback());
    }
    if (next == DeviceAccess.allowed && previous != DeviceAccess.allowed) {
      onResumed?.call();
    }
  }
}
