import 'package:api_client/api_client.dart';
import 'package:auth/auth.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../auth_provider.dart';
import '../../../providers.dart';

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
