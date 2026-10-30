import 'package:admin_app/src/api_result.dart';
import 'package:admin_app/src/features/customers/data/customers_provider.dart';
import 'package:admin_app/src/features/customers/domain/customer_rules.dart';
import 'package:admin_app/src/features/customers/presentation/add_customer_screen.dart';
import 'package:admin_app/src/features/customers/presentation/customer_detail_screen.dart';
import 'package:admin_app/src/features/customers/presentation/kyc_review_sheet.dart';
import 'package:admin_app/src/features/fleet/data/fleet_providers.dart';
import 'package:admin_app/src/providers.dart';
import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

CustomerResponse _customer({
  String status = 'onboarding',
  List<CustomerAddressResponse> addresses = const [],
}) => CustomerResponse(
  id: 'cu1',
  tenantId: 't',
  branchId: 'b1',
  fullName: 'Meena Iyer',
  phoneNumber: '+919876543210',
  customerType: 'domestic',
  kycStatus: 'pending',
  status: status,
  addresses: addresses,
);

Future<void> _tall(WidgetTester tester) async {
  tester.view.physicalSize = const Size(800, 4200);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
}

void main() {
  group('customer rules', () {
    test('recognises a GSTIN however it is typed', () {
      expect(isValidGstin('27AAPFU0939F1ZV'), isTrue);
      expect(isValidGstin(' 27aapfu0939f1zv '), isTrue);
      expect(tidyGstin(' 27aapfu 0939f1zv'), '27AAPFU0939F1ZV');
      expect(isValidGstin('27AAPFU0939F1ZVX'), isFalse);
      expect(isValidGstin('AAPFU0939F1ZV'), isFalse);
      expect(isValidGstin(''), isFalse);
    });

    test('recognises a PIN code and an email', () {
      expect(isValidPincode('411038'), isTrue);
      expect(isValidPincode('011038'), isFalse);
      expect(isValidPincode('4110'), isFalse);
      expect(isValidEmail('meena@example.com'), isTrue);
      expect(isValidEmail('meena@'), isFalse);
    });
  });

  group('AddCustomerScreen', () {
    Widget app({List<FleetBranch>? branches}) => ProviderScope(
      overrides: [
        // Validation must stop before any request.
        customerApiProvider.overrideWith(
          (ref) => throw StateError('the API must not be called'),
        ),
        fleetBranchesProvider.overrideWith(
          (ref) async =>
              branches ??
              const [FleetBranch(id: 'b1', name: 'Hadapsar', isActive: true)],
        ),
      ],
      child: MaterialApp(
        theme: LpgTheme.light,
        home: const AddCustomerScreen(),
      ),
    );

    testWidgets('asks for what is missing before sending anything', (
      tester,
    ) async {
      await _tall(tester);
      await tester.pumpWidget(app());
      await tester.pumpAndSettle();

      await tester.tap(find.widgetWithText(LpgButton, 'Add customer'));
      await tester.pump();

      expect(find.text('Check the fields marked in red.'), findsOneWidget);
      expect(find.text('Enter the name.'), findsOneWidget);
      expect(find.text('Enter a 10-digit mobile number.'), findsOneWidget);
      expect(find.text('Enter the address.'), findsOneWidget);
      expect(find.text('Enter the city.'), findsOneWidget);
      expect(find.text('Enter the 6-digit PIN code.'), findsOneWidget);
    });

    testWidgets('a household has no contact person or GSTIN to fill', (
      tester,
    ) async {
      await _tall(tester);
      await tester.pumpWidget(app());
      await tester.pumpAndSettle();

      expect(find.textContaining('Full name'), findsOneWidget);
      expect(find.textContaining('Contact person'), findsNothing);
      expect(find.text('GSTIN (optional)'), findsNothing);
      // One branch: nothing to choose.
      expect(find.textContaining('Branch'), findsNothing);
    });

    testWidgets('a commercial customer needs a contact person', (tester) async {
      await _tall(tester);
      await tester.pumpWidget(app());
      await tester.pumpAndSettle();

      await tester.tap(find.text('Domestic'));
      await tester.pumpAndSettle();
      await tester.tap(find.text('Commercial'));
      await tester.pumpAndSettle();

      expect(find.textContaining('Business name'), findsOneWidget);
      expect(find.text('GSTIN (optional)'), findsOneWidget);

      await tester.tap(find.widgetWithText(LpgButton, 'Add customer'));
      await tester.pump();
      expect(
        find.text('Enter who to contact at the business.'),
        findsOneWidget,
      );
    });

    testWidgets('with several branches the branch must be chosen', (
      tester,
    ) async {
      await _tall(tester);
      await tester.pumpWidget(
        app(
          branches: const [
            FleetBranch(id: 'b1', name: 'Hadapsar', isActive: true),
            FleetBranch(id: 'b2', name: 'Kothrud', isActive: true),
          ],
        ),
      );
      await tester.pumpAndSettle();

      expect(find.textContaining('Branch'), findsOneWidget);
    });
  });

  group('KycReviewSheet', () {
    const doc = KycDocumentResponse(
      id: 'k1',
      docType: 'aadhaar',
      documentNumber: 'XXXX XXXX 1234',
      verificationStatus: 'pending',
    );

    Widget host(KycDocumentResponse d) => ProviderScope(
      overrides: [
        kycApiProvider.overrideWith(
          (ref) => throw StateError('the API must not be called'),
        ),
      ],
      child: MaterialApp(
        theme: LpgTheme.light,
        home: Scaffold(
          body: KycReviewSheet(customerId: 'cu1', document: d),
        ),
      ),
    );

    testWidgets('rejecting needs a reason first', (tester) async {
      await _tall(tester);
      await tester.pumpWidget(host(doc));

      expect(find.text('XXXX XXXX 1234'), findsOneWidget);
      expect(find.text('Waiting for review'), findsOneWidget);

      await tester.tap(find.text('Reject'));
      await tester.pump();
      await tester.tap(find.text('Reject document'));
      await tester.pump();

      expect(find.textContaining('Say why'), findsOneWidget);
    });

    testWidgets('a verified document offers no decision', (tester) async {
      await _tall(tester);
      await tester.pumpWidget(
        host(
          const KycDocumentResponse(
            id: 'k1',
            docType: 'aadhaar',
            documentNumber: 'XXXX XXXX 1234',
            verificationStatus: 'verified',
          ),
        ),
      );

      expect(find.text('Verified'), findsOneWidget);
      expect(find.text('Verify document'), findsNothing);
    });
  });

  group('CustomerDetailScreen', () {
    Widget app(CustomerResponse customer) => ProviderScope(
      key: ValueKey(customer.status),
      overrides: [
        customerDetailProvider.overrideWith((ref, id) async => customer),
        customerLedgerProvider.overrideWith(
          (ref, id) async => throw const ApiException(Failure(message: 'no')),
        ),
        customerOrdersProvider.overrideWith((ref, id) async => const []),
        customerInvoicesProvider.overrideWith(
          (ref, id) async => throw const ApiException(Failure(message: 'no')),
        ),
        customerKycProvider.overrideWith(
          (ref, id) async => const [
            KycDocumentResponse(
              id: 'k1',
              docType: 'aadhaar',
              documentNumber: 'XXXX XXXX 1234',
              verificationStatus: 'pending',
            ),
          ],
        ),
      ],
      child: MaterialApp(
        theme: LpgTheme.light,
        home: const CustomerDetailScreen(customerId: 'cu1'),
      ),
    );

    testWidgets('a new customer is offered approval, an active one is not', (
      tester,
    ) async {
      await _tall(tester);
      await tester.pumpWidget(app(_customer()));
      await tester.pumpAndSettle();
      expect(find.text('Approve customer'), findsOneWidget);
      expect(find.text('Identity documents'), findsOneWidget);
      expect(find.text('Waiting for review'), findsOneWidget);
      expect(find.text('Add address'), findsOneWidget);
      expect(find.textContaining('Add one before booking'), findsOneWidget);

      await tester.pumpWidget(app(_customer(status: 'active')));
      await tester.pumpAndSettle();
      expect(find.text('Approve customer'), findsNothing);
    });
  });
}
