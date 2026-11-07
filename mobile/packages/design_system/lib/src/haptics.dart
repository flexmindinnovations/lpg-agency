import 'package:flutter/services.dart';

/// The three buzzes the apps use, named for what they tell the person, so a
/// screen asks for "success" rather than picking an impact strength.
///
/// Haptics are feedback, never the only signal: every call sits beside a
/// visible change. They are a no-op on devices without a vibration motor.
abstract final class LpgHaptics {
  /// A light tick for a choice moving: a stepper, a chip, a tab.
  static Future<void> selection() => HapticFeedback.selectionClick();

  /// A firm tap for something that went through: a delivery recorded.
  static Future<void> success() => HapticFeedback.mediumImpact();

  /// A heavy tap for something that needs the person's eyes: a form error
  /// the driver may not be looking at.
  static Future<void> warning() => HapticFeedback.heavyImpact();
}
