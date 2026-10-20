/// Normalises a typed mobile number to E.164, assuming India (`+91`) when no
/// country code is given, so `9876543210`, `09876543210`, `919876543210` and
/// `+91 98765 43210` all become `+919876543210`.
///
/// Mirrors the backend's `lpg.domain.common.phone.normalize_phone_number`.
/// Input that already starts with `+` keeps its own country code; anything
/// unrecognised comes back with separators removed, for
/// [isValidPhoneNumber] to reject.
String normalizePhoneNumber(String raw) {
  final compact = raw.trim().replaceAll(RegExp(r'[\s\-().]'), '');
  if (compact.startsWith('+') || !RegExp(r'^\d+$').hasMatch(compact)) {
    return compact;
  }
  if (compact.length == 10) return '+91$compact';
  if (compact.length == 11 && compact.startsWith('0')) {
    return '+91${compact.substring(1)}';
  }
  if (compact.length == 12 && compact.startsWith('91')) return '+$compact';
  return compact;
}

/// Whether [normalized] (from [normalizePhoneNumber]) is an E.164 number.
bool isValidPhoneNumber(String normalized) =>
    RegExp(r'^\+[1-9]\d{9,14}$').hasMatch(normalized);
