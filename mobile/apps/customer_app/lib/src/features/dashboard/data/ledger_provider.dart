import 'package:api_client/api_client.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../providers.dart';
import '../../profile/data/profile_provider.dart';

/// Provides the current customer's cylinder ledger.
final ledgerProvider = FutureProvider<CylinderLedgerResponse?>((ref) async {
  final profile = await ref.watch(profileProvider.future);
  if (profile == null) return null;

  final api = ref.watch(cylinderLedgerApiProvider);
  final result = await api.getLedger(profile.id);
  return result.when(
    onSuccess: (data) => data,
    onFailure: (failure) => throw Exception(failure.message),
  );
});
