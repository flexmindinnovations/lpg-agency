import 'package:device_identity/device_identity.dart';

/// Every word the Admin app's device-control screens show (ADR-071), kept in
/// one place so it can move to the i18n catalogue in one step later.
///
/// Wording reviewed with the `lpg-domain-expert` agent. The privacy line only
/// describes what is sent; whether the DPDP Act requires a notice like it, and
/// what it must say, is UNVERIFIED — confirm with the agency's adviser.
const adminDeviceStrings = DeviceStrings(
  nameTitle: 'Name this phone',
  nameIntro:
      'Your agency keeps a list of phones that use the Admin app. '
      'Give this phone a name the owner will know.',
  nameFieldLabel: 'Phone name',
  nameFieldHint: 'For example: Counter phone, Manager',
  nameWhy:
      'Your agency will see this name, the phone maker and model, the '
      'Android or iOS version and the app version. The app also sends a code '
      'made from this phone, which is stored in a coded form. The app does '
      'not read your IMEI.',
  nameContinue: 'Save name',
  waitingTitle: 'Waiting for approval',
  waitingMessage:
      'The agency owner must approve this phone before you can use the app. '
      'They can do it on the web dashboard, under Settings > Linked Devices.',
  waitingPhoneLabel: 'This phone',
  waitingCheckAgain: 'Check again',
  waitingStillWaiting:
      'Not approved yet. When the owner says it is done, tap Check again. '
      'We also check by ourselves when you have signal.',
  waitingSignOut: 'Sign out',
  blockedTitle: 'This phone is blocked',
  blockedMessage:
      'Your agency has blocked this phone. You cannot use the app on it now. '
      'Ask the agency owner to unblock it.',
  blockedTryAgain: 'Try signing in again',
);
