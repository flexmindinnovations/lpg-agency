import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../api_result.dart';
import '../../../shared/invoice_tile.dart';
import '../../../shared/metric_tile.dart';
import '../../../shared/order_row.dart';
import '../../orders/data/orders_provider.dart';
import '../../orders/domain/order_booking.dart';
import '../data/customers_provider.dart';
import 'customers_screen.dart';

/// One customer: who they are, what they owe, how many cylinders they hold,
/// their latest orders and invoices, and the quick actions an owner reaches
/// for (call, book an order, see their invoices).
class CustomerDetailScreen extends ConsumerWidget {
  const CustomerDetailScreen({super.key, required this.customerId});

  final String customerId;

  void _reload(WidgetRef ref) {
    ref.invalidate(customerDetailProvider(customerId));
    ref.invalidate(customerLedgerProvider(customerId));
    ref.invalidate(customerOrdersProvider(customerId));
    ref.invalidate(customerInvoicesProvider(customerId));
  }

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final customerAsync = ref.watch(customerDetailProvider(customerId));

    return Scaffold(
      appBar: AppBar(
        title: Text(customerAsync.value?.fullName ?? 'Customer'),
        actions: [
          IconButton(
            tooltip: 'Refresh',
            icon: const Icon(LpgIcons.sync),
            onPressed: () => _reload(ref),
          ),
        ],
      ),
      body: customerAsync.when(
        loading: () => const Center(child: LpgLoadingIndicator()),
        error: (err, _) => LpgErrorState(
          message: errorMessage(err),
          onRetry: () => _reload(ref),
        ),
        data: (customer) => RefreshIndicator(
          onRefresh: () async {
            _reload(ref);
            await ref.read(customerDetailProvider(customerId).future);
          },
          child: ListView(
            physics: const AlwaysScrollableScrollPhysics(),
            padding: LpgSpacing.page,
            children: [
              _Header(customer: customer),
              const SizedBox(height: LpgSpacing.md),
              _Actions(customer: customer),
              const _Gap(),
              _Money(customerId: customerId),
              const _Gap(),
              _Cylinders(customerId: customerId),
              const _Gap(),
              _RecentOrders(customer: customer),
              const _Gap(),
              _Invoices(customerId: customerId),
              const _Gap(),
              _Contact(customer: customer),
              const SizedBox(height: LpgSpacing.xl),
            ],
          ),
        ),
      ),
    );
  }
}

class _Gap extends StatelessWidget {
  const _Gap();

  @override
  Widget build(BuildContext context) => const SizedBox(height: LpgSpacing.lg);
}

class _Header extends StatelessWidget {
  const _Header({required this.customer});

  final CustomerResponse customer;

  @override
  Widget build(BuildContext context) {
    final text = context.lpgText;
    final colors = context.lpgColors;
    final kycVerified = customer.kycStatus == 'verified';

    return LpgCard(
      child: Row(
        children: [
          LpgAvatar(name: customer.fullName, size: LpgSizes.avatarLg),
          const SizedBox(width: LpgSpacing.md),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(customer.fullName, style: text.titleMedium),
                const SizedBox(height: 2),
                Text(
                  [
                    if (customer.consumerNumber != null)
                      customer.consumerNumber!,
                    LpgFormat.sentence(customer.customerType),
                  ].join('  ·  '),
                  style: text.bodySmall?.copyWith(color: colors.textSecondary),
                ),
                const SizedBox(height: LpgSpacing.sm),
                Wrap(
                  spacing: LpgSpacing.xs,
                  runSpacing: LpgSpacing.xs,
                  children: [
                    LpgStatusBadge(
                      label: LpgFormat.statusLabel(customer.status),
                      severity: customerStatusSeverity(customer.status),
                    ),
                    LpgStatusBadge(
                      label: kycVerified
                          ? 'KYC verified'
                          : 'KYC ${LpgFormat.statusLabel(customer.kycStatus).toLowerCase()}',
                      severity: kycVerified
                          ? LpgStatusSeverity.success
                          : LpgStatusSeverity.warning,
                      icon: kycVerified
                          ? LpgIcons.verified
                          : LpgIcons.unverified,
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _Actions extends StatelessWidget {
  const _Actions({required this.customer});

  final CustomerResponse customer;

  Future<void> _call(BuildContext context) async {
    final uri = Uri(scheme: 'tel', path: customer.phoneNumber);
    if (!await launchUrl(uri) && context.mounted) {
      LpgFeedback.showToast(
        context,
        'Could not open the phone app.',
        tone: LpgTone.danger,
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Expanded(
          child: LpgButton(
            label: 'Call',
            icon: LpgIcons.call,
            variant: LpgButtonVariant.secondary,
            onPressed: () => _call(context),
          ),
        ),
        const SizedBox(width: LpgSpacing.sm),
        Expanded(
          child: LpgButton(
            label: 'New order',
            icon: LpgIcons.add,
            onPressed: () => context.pushNamed(
              'order_new',
              queryParameters: {'customer': customer.id},
            ),
          ),
        ),
      ],
    );
  }
}

class _Money extends ConsumerWidget {
  const _Money({required this.customerId});

  final String customerId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(customerInvoicesProvider(customerId));
    final open = [
      for (final i in async.value?.items ?? const <InvoiceResponse>[])
        if (i.status != 'cancelled' && i.balanceDue > 0) i,
    ];
    final owed = open.fold<double>(0, (sum, i) => sum + i.balanceDue);

    return MetricTile(
      label: 'Outstanding',
      value: async.isLoading && !async.hasValue
          ? '…'
          : LpgFormat.currencyWhole(owed),
      caption: async.hasError
          ? 'Could not load invoices'
          : open.isEmpty
          ? 'Nothing due'
          : '${open.length} ${open.length == 1 ? 'invoice' : 'invoices'} unpaid',
      icon: LpgIcons.invoice,
      tone: owed > 0 ? LpgTone.warning : LpgTone.success,
      attention: owed > 0,
      onTap: () => context.pushNamed(
        'invoices',
        queryParameters: {'customer': customerId},
      ),
    );
  }
}

class _Cylinders extends ConsumerWidget {
  const _Cylinders({required this.customerId});

  final String customerId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final ledger = ref.watch(customerLedgerProvider(customerId));
    final names = ref.watch(cylinderNamesProvider).value ?? const {};
    final text = context.lpgText;
    final colors = context.lpgColors;

    final Widget body = ledger.when(
      loading: () => const LpgSkeleton(height: 64),
      error: (err, _) => Text(
        'Cylinder balance is not available for your role.',
        style: text.bodyMedium?.copyWith(color: colors.textSecondary),
      ),
      data: (l) {
        final held = [
          for (final b in l.balances)
            if (b.quantity != 0) b,
        ];
        if (held.isEmpty) {
          return Text(
            'No cylinders with this customer.',
            style: text.bodyMedium?.copyWith(color: colors.textSecondary),
          );
        }
        return LpgGroupedList(
          children: [
            for (final b in held)
              LpgListTile(
                leadingIcon: LpgIcons.cylinder,
                title: names[b.cylinderTypeId] ?? 'Cylinder',
                trailing: Text('${b.quantity}', style: text.titleMedium),
              ),
          ],
        );
      },
    );

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [const SectionHeading('Cylinders with customer'), body],
    );
  }
}

class _RecentOrders extends ConsumerWidget {
  const _RecentOrders({required this.customer});

  final CustomerResponse customer;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(customerOrdersProvider(customer.id));
    final text = context.lpgText;
    final colors = context.lpgColors;

    final Widget body = async.when(
      loading: () => const LpgSkeleton(height: 120),
      error: (err, _) => Text(
        errorMessage(err),
        style: text.bodyMedium?.copyWith(color: colors.statusDanger),
      ),
      data: (orders) {
        if (orders.isEmpty) {
          return Text(
            'No orders yet.',
            style: text.bodyMedium?.copyWith(color: colors.textSecondary),
          );
        }
        return LpgGroupedList(
          children: [
            for (final o in orders)
              OrderTile(
                order: o,
                onTap: () => context.goNamed(
                  'order_detail',
                  pathParameters: {'orderId': o.id},
                ),
              ),
          ],
        );
      },
    );

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SectionHeading(
          'Recent orders',
          actionLabel: 'See all',
          onAction: () => context.goNamed(
            'orders',
            queryParameters: {'q': customer.phoneNumber},
          ),
        ),
        body,
      ],
    );
  }
}

class _Invoices extends ConsumerWidget {
  const _Invoices({required this.customerId});

  final String customerId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final async = ref.watch(customerInvoicesProvider(customerId));
    final text = context.lpgText;
    final colors = context.lpgColors;

    final Widget body = async.when(
      loading: () => const LpgSkeleton(height: 120),
      error: (err, _) => Text(
        errorMessage(err),
        style: text.bodyMedium?.copyWith(color: colors.statusDanger),
      ),
      data: (page) {
        if (page.items.isEmpty) {
          return Text(
            'No invoices yet.',
            style: text.bodyMedium?.copyWith(color: colors.textSecondary),
          );
        }
        return LpgGroupedList(
          children: [
            for (final i in page.items.take(5))
              InvoiceTile(
                invoice: i,
                onTap: () => context.pushNamed(
                  'invoice_detail',
                  pathParameters: {'invoiceId': i.invoiceId},
                ),
              ),
          ],
        );
      },
    );

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        SectionHeading(
          'Invoices',
          actionLabel: 'See all',
          onAction: () => context.pushNamed(
            'invoices',
            queryParameters: {'customer': customerId},
          ),
        ),
        body,
      ],
    );
  }
}

class _Contact extends StatelessWidget {
  const _Contact({required this.customer});

  final CustomerResponse customer;

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const SectionHeading('Contact and addresses'),
        LpgCard(
          child: Column(
            children: [
              LpgKeyValueRow(
                label: 'Phone',
                value: customer.phoneNumber,
                icon: LpgIcons.phone,
              ),
              if (customer.alternateMobile != null)
                LpgKeyValueRow(
                  label: 'Alternate',
                  value: customer.alternateMobile!,
                  icon: LpgIcons.phone,
                ),
              if (customer.email != null)
                LpgKeyValueRow(
                  label: 'Email',
                  value: customer.email!,
                  icon: LpgIcons.email,
                ),
              if (customer.contactPerson != null)
                LpgKeyValueRow(
                  label: 'Contact person',
                  value: customer.contactPerson!,
                  icon: LpgIcons.user,
                ),
            ],
          ),
        ),
        const SizedBox(height: LpgSpacing.sm),
        if (customer.addresses.isEmpty)
          const LpgBanner(
            tone: LpgTone.warning,
            message:
                'No saved address. Add one on the dashboard before booking.',
          )
        else
          LpgGroupedList(
            children: [
              for (final a in customer.addresses)
                LpgListTile(
                  leadingIcon: LpgIcons.location,
                  title: addressLabel(a),
                  trailing: a.isPrimary
                      ? const LpgStatusBadge(
                          label: 'Primary',
                          severity: LpgStatusSeverity.info,
                        )
                      : null,
                ),
            ],
          ),
      ],
    );
  }
}
