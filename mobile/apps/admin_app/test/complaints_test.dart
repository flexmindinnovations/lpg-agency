import 'package:admin_app/src/features/complaints/presentation/complaint_presentation.dart';
import 'package:admin_app/src/features/complaints/presentation/resolve_complaint_sheet.dart';
import 'package:admin_app/src/providers.dart';
import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

ComplaintResponse _complaint({
  String status = 'Assigned',
  String category = 'LateDelivery',
  DateTime? slaDueAt,
}) => ComplaintResponse(
  id: 'c1',
  complaintNumber: 'CMP-0007',
  customerId: 'cu1',
  category: category,
  priority: 'High',
  status: status,
  description: 'Arrived a day late.',
  slaDueAt: slaDueAt,
  createdAt: DateTime(2026, 10, 29, 9),
  updatedAt: DateTime(2026, 10, 29, 9),
  customerName: 'E2E Customer',
);

void main() {
  final now = DateTime(2026, 10, 30, 12);

  group('deadline wording', () {
    test('says how long is left, or how late it is', () {
      expect(
        slaLabel(_complaint(slaDueAt: now.add(const Duration(hours: 5))), now),
        'Due in 5 h',
      );
      expect(
        slaLabel(
          _complaint(slaDueAt: now.subtract(const Duration(hours: 3))),
          now,
        ),
        'Overdue by 3 h',
      );
      expect(
        slaLabel(
          _complaint(slaDueAt: now.subtract(const Duration(days: 4))),
          now,
        ),
        'Overdue by 4 d',
      );
    });

    test('a finished complaint or one with no deadline says nothing', () {
      expect(
        slaLabel(
          _complaint(
            status: 'Resolved',
            slaDueAt: now.subtract(const Duration(days: 1)),
          ),
          now,
        ),
        isNull,
      );
      expect(slaLabel(_complaint(), now), isNull);
    });

    test('reads how long ago something was raised', () {
      expect(ago(now.subtract(const Duration(minutes: 12)), now), '12 min ago');
      expect(ago(now.subtract(const Duration(hours: 5)), now), '5 h ago');
      expect(ago(now.subtract(const Duration(days: 3)), now), '3 d ago');
    });
  });

  group('labels', () {
    test('humanises the backend statuses and categories', () {
      expect(humanizeStatus('InProgress'), 'In progress');
      expect(complaintCategoryLabel('GasLeakSafety'), 'Gas leak / safety');
      expect(complaintCategoryLabel('SomethingNew'), 'Something new');
    });

    test('colours priority and status', () {
      expect(complaintPrioritySeverity('Critical'), LpgStatusSeverity.danger);
      expect(complaintStatusSeverity('Resolved'), LpgStatusSeverity.success);
      expect(complaintStatusSeverity('Open'), LpgStatusSeverity.info);
    });
  });

  group('ResolveComplaintSheet', () {
    testWidgets('will not resolve without saying what was done', (
      tester,
    ) async {
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            // Validation must stop before any request.
            complaintApiProvider.overrideWith(
              (ref) => throw StateError('the API must not be called'),
            ),
          ],
          child: MaterialApp(
            theme: LpgTheme.light,
            home: Scaffold(
              body: ResolveComplaintSheet(complaint: _complaint()),
            ),
          ),
        ),
      );

      await tester.tap(find.text('Resolve complaint'));
      await tester.pump();

      expect(find.textContaining('what was done'), findsWidgets);
      expect(find.textContaining('on record'), findsOneWidget);
    });
  });
}
