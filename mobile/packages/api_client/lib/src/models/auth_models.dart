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
