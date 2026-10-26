import 'package:core/core.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api_result.dart';
import '../../../providers.dart';

/// Who is signed in: real name, role and agency name for the Profile tab.
class AdminProfile {
  const AdminProfile({
    required this.displayName,
    required this.role,
    this.email,
    this.agencyName,
  });

  final String displayName;
  final String role;
  final String? email;

  /// `null` when the caller may not read the tenant (no `tenant:read`).
  final String? agencyName;
}

final adminProfileProvider = FutureProvider<AdminProfile>((ref) async {
  final principal = switch (await ref.watch(authApiProvider).me()) {
    Success(:final value) => value,
    FailureResult(:final failure) => throw ApiException(failure),
  };

  // The agency name is a nicety: a missing permission must not hide the
  // user's own profile.
  final tenant = await ref.watch(adminApiProvider).getTenant();
  final agencyName = switch (tenant) {
    Success(:final value) when value.name.isNotEmpty => value.name,
    _ => null,
  };

  return AdminProfile(
    displayName: principal.displayName ?? principal.email ?? 'Admin',
    role: principal.role,
    email: principal.email,
    agencyName: agencyName,
  );
});
