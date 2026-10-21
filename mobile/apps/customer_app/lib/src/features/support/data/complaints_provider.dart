import 'package:api_client/api_client.dart';
import 'package:auth/auth.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../auth_provider.dart';
import '../../../providers.dart';

/// The national LPG emergency helpline — shown even when the contacts
/// can't be loaded (offline, server down): a leak can't wait for a retry.
const lpgEmergencyHelpline = '1906';

/// Who the customer can phone from Support: the emergency helpline and the
/// agency. Falls back to [lpgEmergencyHelpline] alone on any failure.
final supportContactsProvider = FutureProvider<SupportContacts>((ref) async {
  final result = await ref.watch(complaintApiProvider).getSupportContacts();
  return result.when(
    onSuccess: (contacts) => contacts,
    onFailure: (_) =>
        const SupportContacts(emergencyHelpline: lpgEmergencyHelpline),
  );
});

/// Provides the current customer's complaints.
final complaintsProvider = FutureProvider<List<ComplaintResponse>>((ref) async {
  final api = ref.watch(complaintApiProvider);
  final authController = ref.watch(authControllerProvider);

  if (authController.state.status == AuthStatus.authenticated &&
      authController.state.principal != null) {
    final result = await api.getMyComplaints();
    return result.when(
      onSuccess: (data) => data.items,
      onFailure: (failure) => throw Exception(failure.message),
    );
  }

  return [];
});

/// Provides a single complaint by its ID.
final complaintDetailProvider =
    FutureProvider.family<ComplaintResponse, String>((ref, id) async {
      final api = ref.watch(complaintApiProvider);
      final result = await api.getComplaint(id);
      return result.when(
        onSuccess: (data) => data,
        onFailure: (failure) => throw Exception(failure.message),
      );
    });
