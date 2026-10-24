import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../providers.dart';
import '../data/orders_provider.dart';

class OrderDetailScreen extends ConsumerStatefulWidget {
  const OrderDetailScreen({super.key, required this.orderId});

  final String orderId;

  @override
  ConsumerState<OrderDetailScreen> createState() => _OrderDetailScreenState();
}

class _OrderDetailScreenState extends ConsumerState<OrderDetailScreen> {
  bool _actionLoading = false;

  Future<void> _cancelOrder(String reason) async {
    setState(() => _actionLoading = true);
    final orderApi = ref.read(orderApiProvider);
    final result = await orderApi.cancelOrder(widget.orderId, reason);
    setState(() => _actionLoading = false);

    if (!mounted) return;

    result.when(
      onSuccess: (_) {
        LpgFeedback.showToast(context, 'Order cancellation requested successfully');
        ref.invalidate(adminOrderDetailProvider(widget.orderId));
        ref.invalidate(adminOrdersProvider(1));
      },
      onFailure: (failure) {
        LpgFeedback.showToast(context, failure.message);
      },
    );
  }

  void _showCancelDialog() {
    final controller = TextEditingController();
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Cancel Order'),
        content: TextField(
          controller: controller,
          decoration: const InputDecoration(
            labelText: 'Cancellation Reason',
            hintText: 'Enter reason for cancellation',
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Back'),
          ),
          ElevatedButton(
            onPressed: () {
              final reason = controller.text.trim();
              if (reason.isNotEmpty) {
                Navigator.pop(ctx);
                _cancelOrder(reason);
              }
            },
            child: const Text('Confirm Cancel'),
          ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final text = context.lpgText;

    final orderAsync = ref.watch(adminOrderDetailProvider(widget.orderId));

    return Scaffold(
      appBar: AppBar(
        title: Text('Order #${widget.orderId.substring(0, 8)}'),
        actions: [
          IconButton(
            icon: const Icon(LpgIcons.orders),
            onPressed: () => ref.invalidate(adminOrderDetailProvider(widget.orderId)),
          ),
        ],
      ),
      body: orderAsync.when(
        loading: () => const Center(child: LpgLoadingIndicator()),
        error: (err, _) => LpgErrorState(
          message: 'Failed to load order details: $err',
          onRetry: () => ref.invalidate(adminOrderDetailProvider(widget.orderId)),
        ),
        data: (order) => SingleChildScrollView(
          padding: LpgSpacing.page,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              // Header Card
              LpgCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(order.orderNumber ?? order.id.substring(0, 8), style: text.headlineSmall),
                        LpgStatusBadge(
                          label: order.status,
                          severity: switch (order.status.toLowerCase()) {
                            'delivered' => LpgStatusSeverity.success,
                            'cancelled' => LpgStatusSeverity.danger,
                            'out_for_delivery' => LpgStatusSeverity.info,
                            _ => LpgStatusSeverity.warning,
                          },
                        ),
                      ],
                    ),
                    const SizedBox(height: LpgSpacing.sm),
                    Text('Customer ID: ${order.customerId}', style: text.bodyLarge),
                    Text(
                      'Requested Date: ${LpgFormat.date(order.requestedDate)}',
                      style: text.bodyMedium?.copyWith(color: colors.textSecondary),
                    ),
                  ],
                ),
              ),

              const SizedBox(height: LpgSpacing.lg),
              Text('Order Lines', style: text.titleMedium),
              const SizedBox(height: LpgSpacing.sm),

              ...order.lines.map((line) => Padding(
                    padding: const EdgeInsets.only(bottom: LpgSpacing.xs),
                    child: LpgCard(
                      child: Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text('Cylinder Type #${line.cylinderTypeId.substring(0, 8)}', style: text.bodyLarge),
                              Text('Quantity: ${line.quantityOrdered}', style: text.bodySmall?.copyWith(color: colors.textSecondary)),
                            ],
                          ),
                          Text(LpgFormat.currency((line.unitPrice ?? 0.0) * line.quantityOrdered), style: text.titleSmall),
                        ],
                      ),
                    ),
                  )),

              const SizedBox(height: LpgSpacing.lg),
              LpgCard(
                child: Row(
                  mainAxisAlignment: MainAxisAlignment.spaceBetween,
                  children: [
                    Text('Total Amount', style: text.titleMedium),
                    Text(
                      LpgFormat.currency(order.totalAmount ?? 0.0),
                      style: text.headlineSmall?.copyWith(color: colors.actionPrimary),
                    ),
                  ],
                ),
              ),

              const SizedBox(height: LpgSpacing.xl),
              if (order.status.toLowerCase() != 'cancelled' && order.status.toLowerCase() != 'delivered') ...[
                LpgButton(
                  label: 'Cancel Order',
                  variant: LpgButtonVariant.destructive,
                  isLoading: _actionLoading,
                  onPressed: _actionLoading ? null : _showCancelDialog,
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
