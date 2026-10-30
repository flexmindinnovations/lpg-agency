import 'package:admin_app/src/features/compliance/data/compliance_provider.dart';
import 'package:admin_app/src/features/compliance/presentation/compliance_document_sheet.dart';
import 'package:admin_app/src/features/compliance/presentation/compliance_presentation.dart';
import 'package:admin_app/src/features/compliance/presentation/compliance_screen.dart';
import 'package:admin_app/src/features/orders/data/orders_provider.dart';
import 'package:admin_app/src/providers.dart';
import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

final _today = DateTime(2026, 10, 30);

ComplianceDocument _doc({
  String id = 'd1',
  String ownerType = 'vehicle',
  String ownerId = 'v1',
  String docType = 'vehicle_insurance',
  int? daysFromToday = 5,
  DateTime? today,
  String status = 'pending',
}) {
  final base = today ?? _today;
  return ComplianceDocument(
    id: id,
    ownerType: ownerType,
    ownerId: ownerId,
    docType: docType,
    documentNumber: 'POL-$id',
    verificationStatus: status,
    expiryDate: daysFromToday == null
        ? null
        : DateTime(base.year, base.month, base.day + daysFromToday),
  );
}

const _fleet = FleetData(
  drivers: [
    FleetDriver(
      id: 'dr1',
      branchId: 'b',
      name: 'Ramesh Patil',
      status: 'active',
    ),
  ],
  vehicles: [
    FleetVehicle(
      id: 'v1',
      branchId: 'b',
      registrationNumber: 'MH12AB1234',
      capacityUnits: 40,
      status: 'active',
    ),
  ],
  warehouses: [
    FleetWarehouse(
      id: 'w1',
      branchId: 'b',
      name: 'Kothrud Godown',
      isActive: true,
    ),
  ],
);

void main() {
  group('wording and grouping', () {
    test('buckets by how soon it lapses', () {
      expect(urgencyFor(-1), Urgency.expired);
      expect(urgencyFor(0), Urgency.thisMonth);
      expect(urgencyFor(30), Urgency.thisMonth);
      expect(urgencyFor(31), Urgency.soon);
    });

    test('says how long is left or how late it is', () {
      expect(dueLabel(-12), 'Expired 12 d ago');
      expect(dueLabel(0), 'Expires today');
      expect(dueLabel(18), 'Expires in 18 d');
      expect(dueShort(-12), '12 d ago');
      expect(dueShort(0), 'Today');
      expect(dueShort(18), '18 d left');
    });

    test('groups worst first and drops papers that never lapse', () {
      final grouped = groupByUrgency([
        _doc(id: 'a', daysFromToday: 60),
        _doc(id: 'b', daysFromToday: -3),
        _doc(id: 'c', daysFromToday: -10),
        _doc(id: 'd', daysFromToday: 12),
        _doc(id: 'e', daysFromToday: null, docType: 'trem_card'),
      ], _today);

      expect(grouped[Urgency.expired]!.map((d) => d.id), ['c', 'b']);
      expect(grouped[Urgency.thisMonth]!.map((d) => d.id), ['d']);
      expect(grouped[Urgency.soon]!.map((d) => d.id), ['a']);
    });

    test('names the owner, falling back while the fleet loads', () {
      expect(
        complianceOwnerName(_doc(ownerType: 'vehicle', ownerId: 'v1'), _fleet),
        'MH12AB1234',
      );
      expect(
        complianceOwnerName(_doc(ownerType: 'driver', ownerId: 'dr1'), _fleet),
        'Ramesh Patil',
      );
      expect(
        complianceOwnerName(
          _doc(ownerType: 'warehouse', ownerId: 'w1'),
          _fleet,
        ),
        'Kothrud Godown',
      );
      expect(complianceOwnerName(_doc(ownerType: 'tenant'), _fleet), 'Agency');
      expect(complianceOwnerName(_doc(ownerType: 'vehicle'), null), 'Van');
    });

    test('labels the document types', () {
      expect(complianceDocTypeLabel('peso_form_f'), 'PESO licence (Form F)');
      expect(complianceDocTypeLabel('something_new'), 'Something new');
      expect(docTypeNeedsExpiry('trem_card'), isFalse);
      expect(docTypeNeedsExpiry('vehicle_puc'), isTrue);
    });
  });

  group('ComplianceScreen', () {
    Widget app(List<ComplianceDocument> docs) => ProviderScope(
      overrides: [
        complianceDocumentsProvider.overrideWith((ref) async => docs),
        complianceDueCountProvider.overrideWith((ref) async => 0),
        fleetProvider.overrideWith((ref) async => _fleet),
      ],
      child: MaterialApp(theme: LpgTheme.light, home: const ComplianceScreen()),
    );

    Future<void> tall(WidgetTester tester) async {
      tester.view.physicalSize = const Size(800, 3200);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
    }

    testWidgets('lists what has lapsed first, with whose it is', (
      tester,
    ) async {
      await tall(tester);
      final now = DateTime.now();
      await tester.pumpWidget(
        app([
          _doc(id: 'a', daysFromToday: -4, today: now),
          _doc(
            id: 'b',
            ownerType: 'driver',
            ownerId: 'dr1',
            docType: 'driving_licence',
            daysFromToday: 20,
            today: now,
          ),
          _doc(
            id: 'c',
            ownerType: 'warehouse',
            ownerId: 'w1',
            docType: 'peso_form_f',
            daysFromToday: 70,
            today: now,
          ),
        ]),
      );
      await tester.pumpAndSettle();

      expect(find.text('Expired (1)'), findsOneWidget);
      expect(find.text('Due within 30 days (1)'), findsOneWidget);
      expect(find.text('Due within 90 days (1)'), findsOneWidget);
      expect(find.text('Vehicle insurance'), findsOneWidget);
      expect(find.textContaining('MH12AB1234'), findsOneWidget);
      expect(find.textContaining('Ramesh Patil'), findsOneWidget);
      expect(find.textContaining('Kothrud Godown'), findsOneWidget);
      expect(find.text('4 d ago'), findsOneWidget);
      expect(find.text('20 d left'), findsOneWidget);
    });

    testWidgets('says so when everything is in date', (tester) async {
      await tall(tester);
      await tester.pumpWidget(app(const []));
      await tester.pumpAndSettle();

      expect(find.text('Everything is in date'), findsOneWidget);
    });
  });

  group('ComplianceDocumentSheet', () {
    testWidgets('a renewal needs its photo before anything is sent', (
      tester,
    ) async {
      tester.view.physicalSize = const Size(800, 3200);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      await tester.pumpWidget(
        ProviderScope(
          overrides: [
            // Validation must stop before any request.
            fleetApiProvider.overrideWith(
              (ref) => throw StateError('the API must not be called'),
            ),
          ],
          child: MaterialApp(
            theme: LpgTheme.light,
            home: Scaffold(
              body: ComplianceDocumentSheet(
                document: _doc(daysFromToday: -2, today: DateTime.now()),
                ownerName: 'MH12AB1234',
              ),
            ),
          ),
        ),
      );

      expect(find.text('Expired 2 d ago'), findsOneWidget);
      expect(find.text('POL-d1'), findsOneWidget);
      expect(find.text('Not verified yet'), findsOneWidget);

      await tester.tap(find.text('Renew'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Save renewal'));
      await tester.pump();

      expect(find.text('Add a photo of the renewed document.'), findsOneWidget);
    });
  });
}
