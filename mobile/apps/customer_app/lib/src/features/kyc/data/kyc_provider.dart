import 'package:api_client/api_client.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../providers.dart';
import '../../profile/data/profile_provider.dart';

/// Provides the current customer's KYC documents. Empty (not an error) when
/// the profile hasn't loaded yet -- matches [ordersProvider]/
/// [invoicesProvider]'s own not-authenticated-yet convention rather than
/// flashing an error state during the normal startup fetch race.
final kycDocumentsProvider = FutureProvider<List<KycDocumentResponse>>((
  ref,
) async {
  final profile = await ref.watch(profileProvider.future);
  if (profile == null) return [];

  final api = ref.watch(kycApiProvider);
  final result = await api.getMyDocuments(profile.id);
  return result.when(
    onSuccess: (data) => data.items,
    onFailure: (failure) => throw Exception(failure.message),
  );
});
