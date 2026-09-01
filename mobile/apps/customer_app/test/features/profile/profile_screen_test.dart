import 'package:api_client/api_client.dart';
import 'package:customer_app/src/features/profile/data/profile_provider.dart';
import 'package:customer_app/src/features/profile/presentation/profile_screen.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_test/flutter_test.dart';

import '../../support/pump_screen.dart';

CustomerResponse _profile({
  String kycStatus = 'verified',
  List<CustomerAddressResponse> addresses = const [],
}) => CustomerResponse(
  id: 'cust-1',
  tenantId: 't1',
  branchId: 'b1',
  fullName: 'Asha Menon',
  phoneNumber: '+91 90000 00000',
  email: 'asha@example.com',
  customerType: 'domestic',
  kycStatus: kycStatus,
  status: 'active',
  addresses: addresses,
);

CustomerAddressResponse _address() => const CustomerAddressResponse(
  id: 'addr-1',
  line1: '12 Baker Street',
  city: 'Kochi',
  state: 'Kerala',
  pincode: '682001',
  addressType: 'delivery',
  isPrimary: true,
);

Widget _screen({CustomerResponse? profile, bool nullProfile = false, Object? error}) =>
    ProviderScope(
      overrides: [
        profileProvider.overrideWith((ref) async {
          if (error != null) throw error;
          if (nullProfile) return null;
          return profile ?? _profile();
        }),
      ],
      child: MaterialApp(theme: LpgTheme.light, home: const ProfileScreen()),
    );

void main() {
  group('ProfileScreen', () {
    testWidgets('renders the name, phone and KYC status', (tester) async {
      await pumpScreen(tester, _screen(profile: _profile()));

      expect(find.text('Asha Menon'), findsOneWidget);
      expect(find.text('+91 90000 00000'), findsOneWidget);
      expect(find.text('Verified'), findsOneWidget);
    });

    testWidgets('shows the "no addresses" empty state', (tester) async {
      await pumpScreen(tester, _screen(profile: _profile()));

      expect(find.text('No addresses saved yet.'), findsOneWidget);
    });

    testWidgets('lists a saved address with its PRIMARY badge', (tester) async {
      await pumpScreen(tester, _screen(profile: _profile(addresses: [_address()])));

      expect(find.text('PRIMARY'), findsOneWidget);
    });

    testWidgets('shows an error state with retry when the load fails', (
      tester,
    ) async {
      await pumpScreen(tester, _screen(error: Exception('down')));

      expect(find.textContaining('Failed to load profile'), findsOneWidget);
      expect(find.text('Retry'), findsOneWidget);
    });
  });
}
