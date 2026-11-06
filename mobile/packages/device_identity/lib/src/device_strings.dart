/// Every word the device-control screens show. Each app supplies its own
/// instance, kept in one file per app (`device_strings.dart`), so the wording
/// can be moved to the i18n catalogue in one step later.
class DeviceStrings {
  const DeviceStrings({
    required this.nameTitle,
    required this.nameIntro,
    required this.nameFieldLabel,
    required this.nameFieldHint,
    required this.nameWhy,
    required this.nameContinue,
    required this.waitingTitle,
    required this.waitingMessage,
    required this.waitingPhoneLabel,
    required this.waitingCheckAgain,
    required this.waitingStillWaiting,
    required this.waitingSignOut,
    required this.blockedTitle,
    required this.blockedMessage,
    required this.blockedTryAgain,
    this.blockedKeptWork,
  });

  /// "Name this phone" — shown once, before the first sign-in.
  final String nameTitle;
  final String nameIntro;
  final String nameFieldLabel;

  /// An example name, shown in the empty field.
  final String nameFieldHint;

  /// Why the agency is told about the phone (privacy, shown with the name).
  final String nameWhy;
  final String nameContinue;

  /// "Waiting for approval".
  final String waitingTitle;
  final String waitingMessage;

  /// Label above the phone's name on the waiting screen.
  final String waitingPhoneLabel;
  final String waitingCheckAgain;

  /// Shown after a check finds the phone is still waiting.
  final String waitingStillWaiting;
  final String waitingSignOut;

  /// "This phone is blocked".
  final String blockedTitle;
  final String blockedMessage;
  final String blockedTryAgain;

  /// The Driver app's reassurance that unsent deliveries are safe; `null` for
  /// an app with no offline queue.
  final String? blockedKeptWork;
}
