import 'package:api_client/api_client.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../api_result.dart';
import '../../../providers.dart';

/// Complaints per page of the list.
const complaintPageSize = 50;

/// What the complaint list asks the server for: one status (`null` = all) and
/// optionally one customer.
class ComplaintQuery {
  const ComplaintQuery({this.status, this.customerId});

  final String? status;
  final String? customerId;

  @override
  bool operator ==(Object other) =>
      other is ComplaintQuery &&
      other.status == status &&
      other.customerId == customerId;

  @override
  int get hashCode => Object.hash(status, customerId);
}

/// One page (1-indexed) of complaints matching [ComplaintQuery], newest first
/// as the server orders them.
final complaintsProvider =
    FutureProvider.family<ComplaintListResponse, (ComplaintQuery, int)>((
      ref,
      key,
    ) async {
      return unwrap(
        await ref
            .watch(complaintApiProvider)
            .getMyComplaints(
              skip: (key.$2 - 1) * complaintPageSize,
              limit: complaintPageSize,
              status: key.$1.status,
              customerId: key.$1.customerId,
            ),
      );
    });

final complaintDetailProvider =
    FutureProvider.family<ComplaintResponse, String>((ref, id) async {
      return unwrap(await ref.watch(complaintApiProvider).getComplaint(id));
    });

/// Active staff a complaint can be handed to.
final complaintAssigneesProvider = FutureProvider<List<ComplaintAssignee>>((
  ref,
) async {
  return unwrap(await ref.watch(complaintApiProvider).getAssignees());
});
