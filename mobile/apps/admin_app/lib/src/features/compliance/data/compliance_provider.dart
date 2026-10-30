import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api_result.dart';
import '../../../providers.dart';

/// Documents already overdue or due within 90 days, soonest first: drivers'
/// licences, vans' RC, insurance, fitness and PUC, godown licences and the
/// agency's own policy.
final complianceDocumentsProvider = FutureProvider<List<ComplianceDocument>>((
  ref,
) async {
  return unwrap(await ref.watch(fleetApiProvider).listComplianceDocuments());
});

/// How many documents have lapsed or lapse within 30 days. Zero for a role
/// that may not see them, so a badge never shows an error.
final complianceDueCountProvider = FutureProvider<int>((ref) async {
  final result = await ref.watch(fleetApiProvider).listComplianceDocuments();
  return switch (result) {
    Success<List<ComplianceDocument>>(:final value) =>
      value.where((d) => (d.daysLeft() ?? 999) <= 30).length,
    _ => 0,
  };
});
