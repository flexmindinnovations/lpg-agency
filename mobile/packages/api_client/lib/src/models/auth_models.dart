/// The `/auth/login`, `/auth/otp/verify`, `/auth/refresh` response shape —
/// mirrors the backend's `TokenResponse` schema
/// (`backend/src/lpg/api/v1/schemas/identity.py`).
class TokenPair {
  const TokenPair({required this.accessToken, this.refreshToken});

  factory TokenPair.fromJson(Map<String, dynamic> json) => TokenPair(
    accessToken: json['access_token'] as String,
    refreshToken: json['refresh_token'] as String?,
  );

  final String accessToken;

  /// Always present for mobile clients — the backend only omits it for the
  /// Dashboard's `HttpOnly` cookie flow (`TokenResponse`'s own docstring).
  final String? refreshToken;
}

/// `POST /auth/driver-login` response — step 1 of the Driver App sign-in
/// (password accepted, OTP issued). Mirrors the backend's
/// `DriverLoginChallengeResponse`.
class DriverLoginChallenge {
  const DriverLoginChallenge({required this.phoneHint, this.devOtp});

  factory DriverLoginChallenge.fromJson(Map<String, dynamic> json) =>
      DriverLoginChallenge(
        phoneHint: json['phone_hint'] as String,
        devOtp: json['dev_otp'] as String?,
      );

  /// The driver's phone number with all but the last four digits masked.
  final String phoneHint;

  /// The plaintext OTP. Non-null only when the backend runs with
  /// `otp_delivery_dev_mode` (local development, no SMS provider yet); always
  /// null in any real deployment.
  final String? devOtp;
}

/// `GET /auth/me` — mirrors the backend's `PrincipalResponse`.
class Principal {
  const Principal({
    required this.userId,
    required this.tenantId,
    required this.role,
    required this.permissions,
  });

  factory Principal.fromJson(Map<String, dynamic> json) => Principal(
    userId: json['user_id'] as String,
    tenantId: json['tenant_id'] as String?,
    role: json['role'] as String,
    permissions: (json['permissions'] as List<dynamic>).cast<String>().toSet(),
  );

  final String userId;
  final String? tenantId;
  final String role;
  final Set<String> permissions;
}
