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
    this.displayName,
    this.email,
  });

  factory Principal.fromJson(Map<String, dynamic> json) => Principal(
    userId: json['user_id'] as String,
    tenantId: json['tenant_id'] as String?,
    role: json['role'] as String,
    permissions: (json['permissions'] as List<dynamic>).cast<String>().toSet(),
    displayName: json['display_name'] as String?,
    email: json['email'] as String?,
  );

  final String userId;
  final String? tenantId;
  final String role;
  final Set<String> permissions;

  /// The signed-in user's real name (`null` when the account has none).
  final String? displayName;
  final String? email;
}

/// `GET`/`PATCH /auth/me/profile`: the signed-in staff member's own name and
/// contact number.
class MyProfile {
  const MyProfile({
    required this.userId,
    required this.role,
    this.email,
    this.displayName,
    this.contactPhone,
    this.avatarUrl,
  });

  factory MyProfile.fromJson(Map<String, dynamic> json) => MyProfile(
    userId: json['user_id'] as String,
    role: json['role'] as String,
    email: json['email'] as String?,
    displayName: json['display_name'] as String?,
    contactPhone: json['contact_phone'] as String?,
    avatarUrl: json['avatar_url'] as String?,
  );

  final String userId;
  final String role;
  final String? email;
  final String? displayName;
  final String? contactPhone;

  /// A link to the profile picture that stops working after a while (the
  /// server makes a new one on every read), or `null` when there is none.
  /// Show it; never store it.
  final String? avatarUrl;
}
