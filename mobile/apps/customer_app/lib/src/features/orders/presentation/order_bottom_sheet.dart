import 'dart:convert';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../providers.dart';

/// Bottom sheet for creating a new gas order.
class OrderBottomSheet extends ConsumerStatefulWidget {
  const OrderBottomSheet({super.key});

  @override
  ConsumerState<OrderBottomSheet> createState() => _OrderBottomSheetState();
}

class _OrderBottomSheetState extends ConsumerState<OrderBottomSheet> {
  int _quantity = 1;

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);

    return Container(
      decoration: BoxDecoration(
        color: theme.scaffoldBackgroundColor,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(24)),
      ),
      padding: EdgeInsets.only(
        left: 24,
        right: 24,
        top: 16,
        bottom: MediaQuery.of(context).viewInsets.bottom + 32,
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          // Drag handle
          Center(
            child: Container(
              width: 40,
              height: 4,
              decoration: BoxDecoration(
                color: colors.borderDefault,
                borderRadius: BorderRadius.circular(2),
              ),
            ),
          ),
          const SizedBox(height: 32),

          Text(
            'New Order',
            style: theme.textTheme.headlineSmall?.copyWith(
              fontWeight: FontWeight.w700,
              color: colors.textPrimary,
            ),
            textAlign: TextAlign.center,
          ),
          const SizedBox(height: 8),
          Text(
            'Select the quantity for standard 14kg cylinder.',
            style: theme.textTheme.bodyMedium?.copyWith(
              color: colors.textSecondary,
            ),
            textAlign: TextAlign.center,
          ),

          const SizedBox(height: 32),

          // Quantity selector
          Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              _buildQtyButton(
                icon: Icons.remove,
                onPressed: _quantity > 1
                    ? () => setState(() => _quantity--)
                    : null,
                colors: colors,
              ),
              const SizedBox(width: 24),
              Text(
                '$_quantity',
                style: theme.textTheme.displaySmall?.copyWith(
                  fontWeight: FontWeight.w600,
                  color: colors.textPrimary,
                ),
              ),
              const SizedBox(width: 24),
              _buildQtyButton(
                icon: Icons.add,
                onPressed: () => setState(() => _quantity++),
                colors: colors,
              ),
            ],
          ),

          const SizedBox(height: 48),

          LpgButton(
            label: 'Confirm Order',
            expand: true,
            onPressed: () {
              final syncCoordinator = ref.read(syncCoordinatorProvider);
              syncCoordinator.enqueueOperation(
                'order_gas',
                jsonEncode({'quantity': _quantity, 'cylinder_size_kg': 14.0}),
              );

              if (context.mounted) {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(
                    content: const Text('Order queued for synchronization.'),
                    backgroundColor: colors.statusSuccess,
                  ),
                );
                context.pop();
              }
            },
          ),
        ],
      ),
    );
  }

  Widget _buildQtyButton({
    required IconData icon,
    required VoidCallback? onPressed,
    required LpgColors colors,
  }) {
    final disabled = onPressed == null;
    return GestureDetector(
      onTap: onPressed,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 100),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: colors.surfaceRaised,
          shape: BoxShape.circle,
          border: Border.all(
            color: disabled ? colors.borderDefault : colors.actionPrimary,
          ),
        ),
        child: Icon(
          icon,
          size: 20,
          color: disabled
              ? colors.textSecondary.withValues(alpha: 0.3)
              : colors.actionPrimary,
        ),
      ),
    );
  }
}
