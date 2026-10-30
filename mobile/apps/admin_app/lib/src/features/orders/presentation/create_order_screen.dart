import 'dart:async';

import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:uuid/uuid.dart';

import '../../../api_result.dart';
import '../../../providers.dart';
import '../data/orders_provider.dart';
import '../domain/order_booking.dart';

/// Books an order for a customer, the way the dashboard's New order form
/// does: a customer, one of their addresses, how the booking arrived, the
/// delivery day and one or more cylinder lines from what can be booked now.
class CreateOrderScreen extends ConsumerStatefulWidget {
  const CreateOrderScreen({super.key, this.initialCustomerId});

  /// Books for this customer straight away (from a customer's page).
  final String? initialCustomerId;

  @override
  ConsumerState<CreateOrderScreen> createState() => _CreateOrderScreenState();
}

class _CreateOrderScreenState extends ConsumerState<CreateOrderScreen> {
  CustomerResponse? _customer;
  String? _addressId;
  String _source = 'staff';
  DateTime _day = DateTime.now();
  List<BookingLine> _lines = const [BookingLine()];

  bool _submitting = false;
  bool _showErrors = false;
  String? _serverError;

  /// Kept across a failed attempt so a retry after a dropped connection
  /// can't book the order twice.
  String _idempotencyKey = const Uuid().v4();

  List<OrderableCylinderTypeResponse> get _orderable => _customer == null
      ? const []
      : ref.read(orderableCylindersProvider(_customer!.id)).value ?? const [];

  Future<void> _pickCustomer() async {
    final picked = await LpgFeedback.showSheet<CustomerResponse>(
      context,
      title: 'Select customer',
      builder: (_) => const _CustomerPickerSheet(),
    );
    if (picked == null || !mounted) return;
    _select(picked);
  }

  void _select(CustomerResponse picked) {
    setState(() {
      _customer = picked;
      _addressId = defaultAddress(picked)?.id;
      _lines = const [BookingLine()];
      _serverError = null;
      _idempotencyKey = const Uuid().v4();
    });
  }

  @override
  void initState() {
    super.initState();
    final id = widget.initialCustomerId;
    if (id != null) _preselect(id);
  }

  Future<void> _preselect(String id) async {
    final result = await ref.read(customerApiProvider).getCustomer(id);
    if (!mounted) return;
    if (result case Success<CustomerResponse>(:final value)) _select(value);
  }

  Future<void> _pickDay() async {
    final today = DateTime.now();
    final picked = await showDatePicker(
      context: context,
      initialDate: _day,
      firstDate: DateTime(today.year, today.month, today.day),
      lastDate: today.add(const Duration(days: 60)),
    );
    if (picked != null) setState(() => _day = picked);
  }

  void _setLine(int index, BookingLine line) {
    setState(() {
      _lines = [
        for (var i = 0; i < _lines.length; i++) i == index ? line : _lines[i],
      ];
      _serverError = null;
    });
  }

  void _removeLine(int index) {
    setState(() => _lines = [..._lines]..removeAt(index));
  }

  Future<void> _submit() async {
    final customer = _customer;
    final problem = bookingProblem(
      customer: customer,
      addressId: _addressId,
      lines: _lines,
      orderable: _orderable,
    );
    if (problem != null || customer == null) {
      setState(() => _showErrors = true);
      return;
    }
    final address = customer.addresses.firstWhere((a) => a.id == _addressId);

    setState(() {
      _submitting = true;
      _serverError = null;
    });
    final request = CreateOrderRequest(
      branchId: customer.branchId,
      customerId: customer.id,
      addressId: address.id,
      deliveryAddress: DeliveryAddressPayload(
        addressLine: addressLabel(address),
      ),
      bookingSource: _source,
      requestedDate: deliveryDay(_day),
      lines: [
        for (final l in _lines)
          CreateOrderLineRequest(
            cylinderTypeId: l.cylinderTypeId!,
            quantity: l.quantity,
          ),
      ],
    );
    final result = await ref
        .read(orderApiProvider)
        .createOrder(request, idempotencyKey: _idempotencyKey);
    if (!mounted) return;
    switch (result) {
      case Success<OrderResponse>(:final value):
        ref.invalidate(adminOrdersProvider);
        LpgFeedback.showToast(
          context,
          'Order booked for ${customer.fullName}.',
          tone: LpgTone.success,
        );
        context.pushReplacementNamed(
          'order_detail',
          pathParameters: {'orderId': value.id},
        );
      case FailureResult<OrderResponse>(:final failure):
        if (failure.errorCode == 'CYLINDER_NOT_ORDERABLE') {
          // Stock or prices moved since the form loaded: show what is
          // bookable now.
          ref.invalidate(orderableCylindersProvider(customer.id));
        }
        setState(() {
          _submitting = false;
          _serverError = failure.message;
        });
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = context.lpgText;
    final colors = context.lpgColors;
    final customer = _customer;
    final orderableAsync = customer == null
        ? null
        : ref.watch(orderableCylindersProvider(customer.id));
    final orderable = orderableAsync?.value ?? const [];
    final problem = _showErrors
        ? bookingProblem(
            customer: customer,
            addressId: _addressId,
            lines: _lines,
            orderable: orderable,
          )
        : null;

    return Scaffold(
      appBar: AppBar(title: const Text('New order')),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: LpgSpacing.page,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (_serverError != null) ...[
                LpgBanner(message: _serverError!, tone: LpgTone.danger),
                const SizedBox(height: LpgSpacing.md),
              ],
              Text('Customer', style: text.titleMedium),
              const SizedBox(height: LpgSpacing.sm),
              LpgCard(
                onTap: _submitting ? null : _pickCustomer,
                child: Row(
                  children: [
                    Expanded(
                      child: customer == null
                          ? Text(
                              'Select a customer',
                              style: text.bodyLarge?.copyWith(
                                color: colors.textSecondary,
                              ),
                            )
                          : Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(customer.fullName, style: text.titleSmall),
                                Text(
                                  [
                                    customer.phoneNumber,
                                    ?customer.consumerNumber,
                                  ].join(' · '),
                                  style: text.bodySmall?.copyWith(
                                    color: colors.textSecondary,
                                  ),
                                ),
                              ],
                            ),
                    ),
                    Icon(LpgIcons.chevronDown, color: colors.textSecondary),
                  ],
                ),
              ),
              if (customer != null) ...[
                const SizedBox(height: LpgSpacing.lg),
                Text('Delivery address', style: text.titleMedium),
                const SizedBox(height: LpgSpacing.sm),
                if (customer.addresses.isEmpty)
                  const LpgBanner(
                    tone: LpgTone.warning,
                    message:
                        'This customer has no saved address. Add one on the '
                        'dashboard before booking.',
                  )
                else
                  LpgDropdownField<String>(
                    value: _addressId ?? '',
                    placeholder: 'Select an address',
                    items: {
                      for (final a in customer.addresses) a.id: addressLabel(a),
                    },
                    onChanged: _submitting
                        ? null
                        : (v) => setState(() => _addressId = v),
                  ),
              ],
              const SizedBox(height: LpgSpacing.lg),
              LpgDropdownField<String>(
                label: 'Booked through',
                value: _source,
                items: bookingSources,
                onChanged: _submitting
                    ? null
                    : (v) {
                        if (v != null) setState(() => _source = v);
                      },
              ),
              const SizedBox(height: LpgSpacing.md),
              LpgCard(
                onTap: _submitting ? null : _pickDay,
                child: Row(
                  children: [
                    const Icon(LpgIcons.calendar, size: LpgSizes.iconMd),
                    const SizedBox(width: LpgSpacing.sm),
                    Expanded(
                      child: Text(
                        'Delivery on ${LpgFormat.date(_day)}',
                        style: text.bodyLarge,
                      ),
                    ),
                    Icon(LpgIcons.chevronDown, color: colors.textSecondary),
                  ],
                ),
              ),
              const SizedBox(height: LpgSpacing.lg),
              Text('Cylinders', style: text.titleMedium),
              const SizedBox(height: LpgSpacing.sm),
              if (customer == null)
                Text(
                  'Pick a customer to see what can be booked for them.',
                  style: text.bodyMedium?.copyWith(color: colors.textSecondary),
                )
              else if (orderableAsync!.isLoading)
                const LpgSkeleton(height: 56)
              else if (orderableAsync.hasError)
                LpgErrorState(
                  message: errorMessage(orderableAsync.error!),
                  onRetry: () =>
                      ref.invalidate(orderableCylindersProvider(customer.id)),
                )
              else if (orderable.isEmpty)
                const LpgBanner(
                  tone: LpgTone.warning,
                  message:
                      'Nothing can be booked for this customer right now: no '
                      'cylinder type is both priced for them and in stock.',
                )
              else
                for (var i = 0; i < _lines.length; i++) ...[
                  _LineEditor(
                    line: _lines[i],
                    orderable: orderable,
                    takenIds: {
                      for (var j = 0; j < _lines.length; j++)
                        if (j != i && _lines[j].cylinderTypeId != null)
                          _lines[j].cylinderTypeId!,
                    },
                    enabled: !_submitting,
                    onChanged: (line) => _setLine(i, line),
                    onRemove: _lines.length > 1 ? () => _removeLine(i) : null,
                  ),
                  const SizedBox(height: LpgSpacing.sm),
                ],
              if (orderable.isNotEmpty && _lines.length < orderable.length)
                Align(
                  alignment: Alignment.centerLeft,
                  child: LpgButton(
                    label: 'Add another cylinder',
                    icon: LpgIcons.add,
                    variant: LpgButtonVariant.text,
                    onPressed: _submitting
                        ? null
                        : () => setState(
                            () => _lines = [..._lines, const BookingLine()],
                          ),
                  ),
                ),
              if (problem != null) ...[
                const SizedBox(height: LpgSpacing.md),
                LpgBanner(message: problem, tone: LpgTone.danger),
              ],
              const SizedBox(height: LpgSpacing.xl),
              LpgButton(
                label: 'Book order',
                isLoading: _submitting,
                onPressed: _submitting ? null : _submit,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _LineEditor extends StatelessWidget {
  const _LineEditor({
    required this.line,
    required this.orderable,
    required this.takenIds,
    required this.enabled,
    required this.onChanged,
    this.onRemove,
  });

  final BookingLine line;
  final List<OrderableCylinderTypeResponse> orderable;
  final Set<String> takenIds;
  final bool enabled;
  final ValueChanged<BookingLine> onChanged;
  final VoidCallback? onRemove;

  @override
  Widget build(BuildContext context) {
    final text = context.lpgText;
    final colors = context.lpgColors;
    final options = [
      for (final o in orderable)
        if (!takenIds.contains(o.cylinderTypeId)) o,
    ];
    OrderableCylinderTypeResponse? selected;
    for (final o in orderable) {
      if (o.cylinderTypeId == line.cylinderTypeId) selected = o;
    }

    return LpgCard(
      variant: LpgCardVariant.outlined,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          LpgDropdownField<String>(
            value: line.cylinderTypeId ?? '',
            label: 'Cylinder type',
            placeholder: 'Select a cylinder type',
            items: {
              for (final o in options)
                o.cylinderTypeId:
                    '${o.name} · ${LpgFormat.currency(o.unitPrice)}',
            },
            onChanged: enabled
                ? (v) {
                    if (v == null) return;
                    final stock = orderable
                        .firstWhere((o) => o.cylinderTypeId == v)
                        .availableQuantity;
                    onChanged(
                      BookingLine(
                        cylinderTypeId: v,
                        quantity: line.quantity.clamp(1, stock < 1 ? 1 : stock),
                      ),
                    );
                  }
                : null,
          ),
          if (selected != null) ...[
            const SizedBox(height: LpgSpacing.sm),
            Row(
              children: [
                Expanded(
                  child: Text(
                    '${selected.availableQuantity} in stock',
                    style: text.bodySmall?.copyWith(
                      color: colors.textSecondary,
                    ),
                  ),
                ),
                LpgQuantityStepper(
                  value: line.quantity,
                  min: 1,
                  max: selected.availableQuantity,
                  onChanged: enabled
                      ? (v) => onChanged(line.copyWith(quantity: v))
                      : null,
                ),
                if (onRemove != null)
                  IconButton(
                    tooltip: 'Remove this line',
                    onPressed: enabled ? onRemove : null,
                    icon: const Icon(LpgIcons.delete),
                  ),
              ],
            ),
          ],
        ],
      ),
    );
  }
}

/// Searchable customer list (`GET /customers?search=`), debounced.
class _CustomerPickerSheet extends ConsumerStatefulWidget {
  const _CustomerPickerSheet();

  @override
  ConsumerState<_CustomerPickerSheet> createState() =>
      _CustomerPickerSheetState();
}

class _CustomerPickerSheetState extends ConsumerState<_CustomerPickerSheet> {
  final _search = TextEditingController();
  Timer? _debounce;
  String _query = '';

  @override
  void dispose() {
    _debounce?.cancel();
    _search.dispose();
    super.dispose();
  }

  void _onChanged(String value) {
    _debounce?.cancel();
    _debounce = Timer(const Duration(milliseconds: 300), () {
      if (mounted) setState(() => _query = value.trim());
    });
  }

  @override
  Widget build(BuildContext context) {
    final async = ref.watch(customerSearchProvider(_query));
    return SizedBox(
      height: MediaQuery.sizeOf(context).height * 0.7,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          LpgTextField(
            label: 'Search',
            hintText: 'Name, phone or consumer number',
            controller: _search,
            prefixIcon: LpgIcons.search,
            onChanged: _onChanged,
            autofocus: true,
          ),
          const SizedBox(height: LpgSpacing.sm),
          LpgListTile(
            leadingIcon: LpgIcons.add,
            title: 'Add a new customer',
            subtitle: 'For someone who booked by phone or walked in',
            onTap: () async {
              final created = await context.pushNamed<CustomerResponse>(
                'customer_new',
              );
              if (created != null && context.mounted) {
                Navigator.of(context).pop(created);
              }
            },
          ),
          Expanded(
            child: async.when(
              loading: () => const LpgSkeletonList(itemCount: 4),
              error: (err, _) => LpgErrorState(
                message: errorMessage(err),
                onRetry: () => ref.invalidate(customerSearchProvider(_query)),
              ),
              data: (page) {
                if (page.items.isEmpty) {
                  return const LpgEmptyState(
                    message: 'No customers match.',
                    icon: LpgIcons.search,
                  );
                }
                return ListView.builder(
                  itemCount: page.items.length,
                  itemBuilder: (context, i) {
                    final c = page.items[i];
                    return LpgListTile(
                      title: c.fullName,
                      subtitle: [c.phoneNumber, ?c.consumerNumber].join(' · '),
                      onTap: () => Navigator.of(context).pop(c),
                    );
                  },
                );
              },
            ),
          ),
        ],
      ),
    );
  }
}
