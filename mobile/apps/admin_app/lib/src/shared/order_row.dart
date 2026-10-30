import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';

import '../features/orders/domain/order_flow.dart';

/// The icon an order's status is shown with, the same across every list.
IconData orderStatusIcon(String status) => switch (status) {
  'delivered' || 'closed' => LpgIcons.success,
  'cancelled' => LpgIcons.cancel,
  'failed_delivery' => LpgIcons.warning,
  'out_for_delivery' => LpgIcons.truck,
  'assigned' || 'ready_for_dispatch' => LpgIcons.package,
  'booked' => LpgIcons.pending,
  _ => LpgIcons.orders,
};

/// An order as one row of an [LpgGroupedList]: a tinted status icon, "Order
/// ORD000061", the customer and status underneath, the date and a chevron on
/// the right. The same row the Customer and Driver apps use.
class OrderTile extends StatelessWidget {
  const OrderTile({
    super.key,
    required this.order,
    required this.onTap,
    this.subtitle,
    this.trailing,
  });

  final OrderResponse order;
  final VoidCallback onTap;

  /// Replaces "customer · status" (a queue shows what is in the order).
  final String? subtitle;

  /// Replaces the date (a queue shows its action instead).
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return LpgListTile(
      leadingIcon: orderStatusIcon(order.status),
      leadingTone: orderStatusSeverity(order.status).tone,
      title: 'Order ${LpgFormat.orderNumber(order.orderNumber, order.id)}',
      subtitle:
          subtitle ??
          '${order.customerName ?? 'Customer'}  ·  '
              '${LpgFormat.statusLabel(order.status)}',
      trailing:
          trailing ??
          Text(
            LpgFormat.shortDate(order.requestedDate),
            style: context.lpgText.bodySmall,
          ),
      showChevron: trailing == null,
      onTap: onTap,
    );
  }
}
