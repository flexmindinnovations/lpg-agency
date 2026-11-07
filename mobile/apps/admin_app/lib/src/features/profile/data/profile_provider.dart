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
    this.ownName,
    this.contactPhone,
  });

  /// What to show: the name, or the email, or "Admin".
  final String displayName;

  /// The name as saved on the account (`null` when none), for editing.
  final String? ownName;

  /// A number colleagues can use to reach this person (`null` when none).
  final String? contactPhone;
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

  // Also a nicety: the contact number only comes from the profile route.
  final own = switch (await ref.watch(authApiProvider).myProfile()) {
    Success(:final value) => value,
    FailureResult() => null,
  };

  // The profile route is read fresh; the principal's name can lag behind an
  // edit, so it is only the fallback when the profile route is unavailable.
  final ownName = own == null ? principal.displayName : own.displayName;

  return AdminProfile(
    displayName: ownName ?? principal.email ?? 'Admin',
    ownName: ownName,
    contactPhone: own?.contactPhone,
    role: principal.role,
    email: principal.email,
    agencyName: agencyName,
  );
});
