import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api_result.dart';
import '../../../providers.dart';

/// Every price ever set, history included.
final priceEntriesProvider = FutureProvider<List<PriceEntry>>((ref) async {
  return unwrap(await ref.watch(priceListApiProvider).listPrices());
});

/// Oil-company rate changes waiting for review. A role that may not review
/// them simply sees none, rather than an error.
final priceProposalsProvider = FutureProvider<List<PriceProposal>>((ref) async {
  final result = await ref.watch(priceListApiProvider).listProposals();
  return switch (result) {
    Success<List<PriceProposal>>(:final value) => value,
    _ => const <PriceProposal>[],
  };
});
