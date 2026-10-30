import 'package:api_client/api_client.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api_result.dart';
import '../../../providers.dart';

/// `YYYY-MM-DD` for the API.
String cashBookDay(DateTime day) =>
    '${day.year.toString().padLeft(4, '0')}-'
    '${day.month.toString().padLeft(2, '0')}-'
    '${day.day.toString().padLeft(2, '0')}';

/// One day of the cash book: what was collected, by method, and how the
/// drivers' handovers for it stand.
final cashBookProvider = FutureProvider.family<CashBook, String>((
  ref,
  day,
) async {
  return unwrap(await ref.watch(adminApiProvider).getCashBook(day: day));
});

/// The cash each driver is carrying right now, whatever the day.
final cashInHandProvider = FutureProvider<CashInHand>((ref) async {
  return unwrap(await ref.watch(adminApiProvider).getCashInHand());
});
