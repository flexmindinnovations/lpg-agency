import 'package:api_client/api_client.dart';
import 'package:customer_app/src/features/profile/presentation/edit_profile_screen.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/pump_screen.dart';

const _profile = CustomerResponse(
  id: 'cust-1',
  tenantId: 't1',
  branchId: 'b1',
  fullName: 'Asha Menon',
  phoneNumber: '+919000000000',
  email: 'asha@example.com',
  customerType: 'domestic',
  kycStatus: 'verified',
  status: 'active',
  addresses: [],
);

Widget _screen() => ProviderScope(
  child: MaterialApp(
    theme: LpgTheme.light,
    home: const EditProfileScreen(profile: _profile),
  ),
);

void main() {
  group('EditProfileScreen', () {
    testWidgets('pre-fills the form from the passed profile', (tester) async {
      await pumpScreen(tester, _screen());

      expect(find.text('Asha Menon'), findsOneWidget);
      expect(find.text('asha@example.com'), findsOneWidget);
    });

    testWidgets('requires a full name on save', (tester) async {
      await pumpScreen(tester, _screen());

      await tester.enterText(find.text('Asha Menon'), '');
      await tester.tap(find.text('Save Changes'));
      await tester.pumpAndSettle();

      expect(find.text('Required'), findsWidgets);
    });
  });
}
