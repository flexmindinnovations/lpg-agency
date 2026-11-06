import 'package:device_identity/device_identity.dart';

/// Every word the Driver app's device-control screens show (ADR-071), kept in
/// one place so it can move to the i18n catalogue in one step later.
///
/// Wording reviewed with the `lpg-domain-expert` agent. The privacy line only
/// describes what is sent; whether the DPDP Act requires a notice like it, and
/// what it must say, is UNVERIFIED — confirm with the agency's adviser.
const driverDeviceStrings = DeviceStrings(
  nameTitle: 'Name this phone',
  nameIntro:
      'Your agency keeps a list of phones that use the Driver app. '
      'Give this phone a name the office will know.',
  nameFieldLabel: 'Phone name',
  nameFieldHint: 'For example: Ramesh, Van 2',
  nameWhy:
      'Your agency will see this name, the phone maker and model, the Android '
      'version and the app version. The app also sends a code made from this '
      'phone, which is stored in a coded form. The app does not read your IMEI.',
  nameContinue: 'Save name',
  waitingTitle: 'Waiting for approval',
  waitingMessage:
      'The office must approve this phone before you can start deliveries. '
      'Call your agency office and ask them to approve it.',
  waitingPhoneLabel: 'This phone',
  waitingCheckAgain: 'Check again',
  waitingStillWaiting:
      'Not approved yet. When the office says it is done, tap Check again. '
      'We also check by ourselves when you have signal.',
  waitingSignOut: 'Sign out',
  blockedTitle: 'This phone is blocked',
  blockedMessage:
      'Your agency has blocked this phone. You cannot use the app on it now. '
      'Call your agency office.',
  blockedTryAgain: 'Try signing in again',
  blockedKeptWork:
      'Deliveries not yet sent are safe on this phone. Do not delete the app '
      'or clear its data. They will be sent after the office unblocks the '
      'phone and you sign in again.',
);
