import 'dart:async';

import 'package:flutter/material.dart' show ThemeMode;
import 'package:flutter/foundation.dart' show ValueNotifier;
import 'package:riverpod/riverpod.dart';

/// The person's choice of appearance: follow the phone, or always light or
/// dark. It is a per-device preference, so it lives outside the per-session
/// provider tree (signing out must not change how the app looks) and is saved
/// so it survives a restart.
///
/// Create one in `main` with [load], hand it to the app through
/// [lpgThemeModeControllerProvider], and feed `MaterialApp.themeMode` from its
/// value.
class LpgThemeModeController extends ValueNotifier<ThemeMode> {
  /// Starts at [initial] and calls [write] with the mode's name whenever it
  /// changes. With no [write] it is kept in memory only (tests, previews).
  LpgThemeModeController({
    ThemeMode initial = ThemeMode.system,
    Future<void> Function(String value)? write,
  }) : _write = write,
       super(initial);

  final Future<void> Function(String value)? _write;

  /// Reads the saved choice with [read] (no saved choice, an unreadable one or
  /// a failed read all mean "follow the phone") and returns a controller that
  /// saves later changes with [write].
  static Future<LpgThemeModeController> load({
    required Future<String?> Function() read,
    required Future<void> Function(String value) write,
  }) async {
    String? saved;
    try {
      saved = await read();
    } on Object {
      // Storage unavailable: the default is fine.
    }
    return LpgThemeModeController(initial: parse(saved), write: write);
  }

  /// The mode named by [saved], or [ThemeMode.system] for anything else.
  static ThemeMode parse(String? saved) => ThemeMode.values.firstWhere(
    (m) => m.name == saved,
    orElse: () => ThemeMode.system,
  );

  /// Switches to [mode] now and saves it in the background.
  void select(ThemeMode mode) {
    if (mode == value) return;
    value = mode;
    final write = _write;
    if (write != null) {
      unawaited(
        write(mode.name).catchError((Object _) {
          // Not saved: it still applies until the app closes.
        }),
      );
    }
  }
}

/// The mode `MaterialApp.themeMode` should use: follows the controller, so a
/// change rebuilds the app with the new theme.
final lpgThemeModeProvider = Provider<ThemeMode>((ref) {
  final controller = ref.watch(lpgThemeModeControllerProvider);
  void changed() => ref.invalidateSelf();
  controller.addListener(changed);
  ref.onDispose(() => controller.removeListener(changed));
  return controller.value;
});

/// The app's one [LpgThemeModeController]. Apps override it with the loaded
/// one; the default is an in-memory controller so a screen built in a test
/// still works.
final lpgThemeModeControllerProvider = Provider<LpgThemeModeController>(
  (ref) => LpgThemeModeController(),
);
