import 'package:api_client/api_client.dart';
import 'package:customer_app/src/features/kyc/data/kyc_provider.dart';
import 'package:customer_app/src/features/kyc/presentation/kyc_screen.dart';
import 'package:customer_app/src/features/profile/data/profile_provider.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

KycDocumentResponse _doc({
  String docType = 'aadhaar',
  String number = '123456789012',
  String status = 'verified',
  String? rejectionReason,
}) => KycDocumentResponse(
  id: 'doc-1',
  docType: docType,
  documentNumber: number,
  verificationStatus: status,
  rejectionReason: rejectionReason,
  verifiedAt: status == 'verified' ? DateTime(2026, 8, 26) : null,
);

Widget _screen({
  List<KycDocumentResponse>? docs,
  Object? error,
  String accountKyc = 'pending',
}) => ProviderScope(
  overrides: [
    profileProvider.overrideWith(
      (ref) async => CustomerResponse.fromJson({
        'id': 'c1',
        'tenant_id': 't1',
        'branch_id': 'b1',
        'full_name': 'Asha Rao',
        'phone_number': '+919876543210',
        'customer_type': 'domestic',
        'kyc_status': accountKyc,
        'status': 'active',
      }),
    ),
    kycDocumentsProvider.overrideWith((ref) async {
      if (error != null) throw error;
      return docs ?? const [];
    }),
  ],
  child: MaterialApp(theme: LpgTheme.light, home: const KycScreen()),
);

void main() {
  group('KycScreen', () {
    testWidgets('shows the empty state when there are no documents', (
      tester,
    ) async {
      await tester.pumpWidget(_screen(docs: const []));
      await tester.pumpAndSettle();

      expect(find.textContaining("haven't submitted any KYC"), findsOneWidget);
      expect(find.text('Add Document'), findsOneWidget);
    });

    testWidgets('an agency-verified account with no uploads says verified', (
      tester,
    ) async {
      await tester.pumpWidget(_screen(docs: const [], accountKyc: 'verified'));
      await tester.pumpAndSettle();

      expect(find.text('KYC verified'), findsOneWidget);
      expect(find.textContaining("haven't submitted"), findsNothing);
    });

    testWidgets('renders a document with a masked number and status', (
      tester,
    ) async {
      await tester.pumpWidget(_screen(docs: [_doc()]));
      await tester.pumpAndSettle();

      expect(find.text('Aadhaar Card'), findsOneWidget);
      expect(find.text('Verified'), findsOneWidget);
      // Only the last 4 digits are shown in the clear.
      expect(find.textContaining('9012'), findsOneWidget);
      expect(find.textContaining('123456789012'), findsNothing);
    });

    testWidgets('shows the rejection reason for a rejected document', (
      tester,
    ) async {
      await tester.pumpWidget(
        _screen(
          docs: [_doc(status: 'rejected', rejectionReason: 'Blurry photo')],
        ),
      );
      await tester.pumpAndSettle();

      expect(find.text('Rejected'), findsOneWidget);
      expect(find.text('Blurry photo'), findsOneWidget);
    });

    testWidgets('shows an error state with retry when the load fails', (
      tester,
    ) async {
      await tester.pumpWidget(_screen(error: Exception('network down')));
      await tester.pumpAndSettle();

      expect(find.textContaining('Failed to load'), findsOneWidget);
      expect(find.text('Retry'), findsOneWidget);
    });
  });
}
