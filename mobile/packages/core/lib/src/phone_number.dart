/// Phone numbers as people type them, turned into the E.164 form the
/// backend stores (`+919876543210`).
///
/// Indian customers and drivers type their mobile number the way they say
/// it: ten digits, sometimes with a leading `0` or `91`, often with spaces.
/// The backend matches accounts on strict E.164, so a bare ten-digit number
/// used to get an OTP and then "No account is associated with this number"
/// (QA CA-02). Normalising on the device fixes that before the request.
abstract final class PhoneNumbers {
  /// The default country code, shown as a fixed `+91` prefix on sign-in.
  static const indiaDialCode = '+91';

  /// [input] as E.164, or `null` when it can't be a phone number.
  ///
  /// - `98765 43210`, `098765-43210`, `919876543210`, `+91 98765 43210` all
  ///   become `+919876543210` (an Indian mobile starts with 6–9).
  /// - Any other number that starts with `+` and has 8–15 digits is kept
  ///   as given (international).
  static String? normalize(String input) {
    final trimmed = input.trim();
    final international = trimmed.startsWith('+');
    final digits = trimmed.replaceAll(RegExp(r'[\s\-().]'), '');
    if (!RegExp(r'^\+?[0-9]+$').hasMatch(digits)) return null;
    final bare = international ? digits.substring(1) : digits;

    final indianMobile = RegExp(r'^[6-9][0-9]{9}$');
    if (indianMobile.hasMatch(bare) && !international) {
      return '$indiaDialCode$bare';
    }
    if (bare.length == 11 && bare.startsWith('0')) {
      final local = bare.substring(1);
      if (indianMobile.hasMatch(local) && !international) {
        return '$indiaDialCode$local';
      }
    }
    if (bare.length == 12 && bare.startsWith('91')) {
      final local = bare.substring(2);
      if (indianMobile.hasMatch(local)) return '$indiaDialCode$local';
    }
    if (international && bare.length >= 8 && bare.length <= 15) {
      return '+$bare';
    }
    return null;
  }
}
