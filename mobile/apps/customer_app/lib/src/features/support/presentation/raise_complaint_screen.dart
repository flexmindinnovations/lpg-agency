import 'package:api_client/api_client.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../providers.dart';
import '../../../widgets/form_field_widgets.dart';
import '../../orders/data/orders_provider.dart';
import '../../profile/data/profile_provider.dart';
import '../data/complaints_provider.dart';

const _categories = <String, String>{
  ComplaintCategory.shortDelivery: 'Short Delivery',
  ComplaintCategory.damagedCylinder: 'Damaged Cylinder',
  ComplaintCategory.billingDispute: 'Billing Dispute',
  ComplaintCategory.driverConduct: 'Driver Conduct',
  ComplaintCategory.lateDelivery: 'Late Delivery',
  ComplaintCategory.other: 'Other',
};

const _priorities = <String, String>{
  ComplaintPriority.low: 'Low',
  ComplaintPriority.medium: 'Medium',
  ComplaintPriority.high: 'High',
  ComplaintPriority.critical: 'Critical',
};

/// Form to raise a new complaint (`ComplaintApi.raiseComplaint`) — category,
/// priority, description, and an optional related order.
class RaiseComplaintScreen extends ConsumerStatefulWidget {
  const RaiseComplaintScreen({super.key});

  @override
  ConsumerState<RaiseComplaintScreen> createState() =>
      _RaiseComplaintScreenState();
}

class _RaiseComplaintScreenState extends ConsumerState<RaiseComplaintScreen> {
  final _formKey = GlobalKey<FormState>();
  final _descriptionController = TextEditingController();

  String _category = ComplaintCategory.other;
  String _priority = ComplaintPriority.medium;
  String? _orderId;
  bool _submitting = false;
  String? _errorMessage;

  @override
  void dispose() {
    _descriptionController.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!(_formKey.currentState?.validate() ?? false)) return;

    final profile = ref.read(profileProvider).value;
    if (profile == null) {
      setState(() => _errorMessage = 'Your profile has not loaded yet.');
      return;
    }

    setState(() {
      _submitting = true;
      _errorMessage = null;
    });

    final result = await ref
        .read(complaintApiProvider)
        .raiseComplaint(
          RaiseComplaintRequest(
            customerId: profile.id,
            category: _category,
            priority: _priority,
            description: _descriptionController.text.trim(),
            orderId: _orderId,
          ),
        );

    if (!mounted) return;
    setState(() => _submitting = false);

    result.when(
      onSuccess: (_) {
        // Resolve the messenger and pop *before* invalidating — matches
        // the fix in order_detail_screen.dart's cancel flow, where
        // invalidating a provider this screen watched, then touching
        // `context` afterwards, hit a real framework assertion crash
        // live. Not the same provider here, but cheap to make this the
        // one order that's always safe rather than relying on which
        // provider happens to be watched today.
        final messenger = ScaffoldMessenger.of(context);
        Navigator.of(context).pop();
        ref.invalidate(complaintsProvider);
        messenger.showSnackBar(
          const SnackBar(content: Text('Complaint raised successfully.')),
        );
      },
      onFailure: (failure) => setState(() => _errorMessage = failure.message),
    );
  }

  @override
  Widget build(BuildContext context) {
    final colors = Theme.of(context).extension<LpgColors>()!;
    final theme = Theme.of(context);
    final ordersAsync = ref.watch(ordersProvider);

    return Scaffold(
      backgroundColor: theme.scaffoldBackgroundColor,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        centerTitle: true,
        title: Text(
          'Raise a Complaint',
          style: theme.textTheme.titleMedium?.copyWith(
            fontWeight: FontWeight.w600,
            color: colors.textPrimary,
          ),
        ),
      ),
      body: Form(
        key: _formKey,
        child: ListView(
          padding: const EdgeInsets.all(24.0),
          children: [
            if (_errorMessage != null) ...[
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: colors.statusDanger.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                  border: Border.all(
                    color: colors.statusDanger.withValues(alpha: 0.3),
                  ),
                ),
                child: Row(
                  children: [
                    Icon(Icons.error_outline, color: colors.statusDanger),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        _errorMessage!,
                        style: TextStyle(
                          color: colors.statusDanger,
                          fontWeight: FontWeight.w500,
                        ),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 24),
            ],

            const FieldLabel('Category'),
            FormDropdownField(
              value: _category,
              items: _categories,
              onChanged: (v) => setState(() => _category = v!),
            ),
            const SizedBox(height: 20),

            const FieldLabel('Priority'),
            FormDropdownField(
              value: _priority,
              items: _priorities,
              onChanged: (v) => setState(() => _priority = v!),
            ),
            const SizedBox(height: 20),

            const FieldLabel('Related order (optional)'),
            ordersAsync.when(
              loading: () => const LinearProgressIndicator(),
              error: (_, _) => const SizedBox.shrink(),
              data: (orders) => FormDropdownField<String?>(
                value: _orderId,
                items: {
                  for (final order in orders)
                    order.id:
                        'Order #${order.id.substring(0, 8).toUpperCase()}',
                },
                placeholder: 'None',
                onChanged: (v) => setState(() => _orderId = v),
              ),
            ),
            const SizedBox(height: 20),

            LpgTextField(
              label: 'Description',
              controller: _descriptionController,
              maxLines: 5,
              hintText: 'Tell us what happened...',
              validator: (v) => (v == null || v.trim().isEmpty)
                  ? 'Please describe the issue.'
                  : null,
            ),

            const SizedBox(height: 32),
            LpgButton(
              label: 'Submit Complaint',
              isLoading: _submitting,
              expand: true,
              onPressed: _submit,
            ),
          ],
        ),
      ),
    );
  }
}
