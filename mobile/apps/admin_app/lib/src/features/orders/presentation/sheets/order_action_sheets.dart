import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../providers.dart';
import '../../domain/order_flow.dart';

/// A sheet that asks for a reason and runs [submit] with it. Pops `true`
/// when [submit] succeeds. Used for cancelling an order and for rejecting a
/// cancellation request.
class ReasonSheet extends StatefulWidget {
  const ReasonSheet({
    super.key,
    required this.intro,
    required this.label,
    required this.actionLabel,
    required this.submit,
    this.destructive = false,
  });

  final String intro;
  final String label;
  final String actionLabel;
  final bool destructive;
  final Future<Result<Object?>> Function(String reason) submit;

  @override
  State<ReasonSheet> createState() => _ReasonSheetState();
}

class _ReasonSheetState extends State<ReasonSheet> {
  final _controller = TextEditingController();
  String? _error;
  bool _busy = false;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    final reason = _controller.text.trim();
    if (reason.isEmpty) {
      setState(() => _error = 'Enter a reason.');
      return;
    }
    setState(() {
      _busy = true;
      _error = null;
    });
    final result = await widget.submit(reason);
    if (!mounted) return;
    switch (result) {
      case Success<Object?>():
        Navigator.of(context).pop(true);
      case FailureResult<Object?>(:final failure):
        setState(() {
          _busy = false;
          _error = failure.message;
        });
    }
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            widget.intro,
            style: context.lpgText.bodyMedium?.copyWith(
              color: context.lpgColors.textSecondary,
            ),
          ),
          const SizedBox(height: LpgSpacing.md),
          LpgTextField(
            label: widget.label,
            controller: _controller,
            isRequired: true,
            maxLines: 3,
            maxLength: 1000,
            textCapitalization: TextCapitalization.sentences,
            enabled: !_busy,
          ),
          if (_error != null) ...[
            const SizedBox(height: LpgSpacing.sm),
            LpgBanner(tone: LpgTone.danger, message: _error!),
          ],
          const SizedBox(height: LpgSpacing.lg),
          LpgButton(
            label: widget.actionLabel,
            variant: widget.destructive
                ? LpgButtonVariant.destructive
                : LpgButtonVariant.primary,
            isLoading: _busy,
            expand: true,
            onPressed: _busy ? null : _send,
          ),
        ],
      ),
    );
  }
}

/// Picks a new delivery date for a failed delivery and moves the order back
/// to Confirmed, waiting for a new trip.
class RescheduleSheet extends ConsumerStatefulWidget {
  const RescheduleSheet({super.key, required this.order});

  final OrderResponse order;

  @override
  ConsumerState<RescheduleSheet> createState() => _RescheduleSheetState();
}

class _RescheduleSheetState extends ConsumerState<RescheduleSheet> {
  late DateTime _date = _today();
  late final TextEditingController _dateText = TextEditingController(
    text: LpgFormat.date(_date),
  );
  String? _error;
  bool _busy = false;

  static DateTime _today() {
    final now = DateTime.now();
    return DateTime(now.year, now.month, now.day);
  }

  @override
  void dispose() {
    _dateText.dispose();
    super.dispose();
  }

  Future<void> _pick() async {
    final today = _today();
    final picked = await showDatePicker(
      context: context,
      initialDate: _date,
      firstDate: today,
      lastDate: today.add(const Duration(days: 365)),
    );
    if (picked == null) return;
    setState(() {
      _date = picked;
      _dateText.text = LpgFormat.date(picked);
    });
  }

  Future<void> _send() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    final result = await ref
        .read(orderApiProvider)
        .rescheduleOrder(widget.order.id, _date);
    if (!mounted) return;
    switch (result) {
      case Success<OrderResponse>():
        Navigator.of(context).pop(true);
      case FailureResult<OrderResponse>(:final failure):
        setState(() {
          _busy = false;
          _error = failure.message;
        });
    }
  }

  @override
  Widget build(BuildContext context) {
    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          Text(
            'The order leaves its trip and goes back to Confirmed. '
            'Send it out again when it is ready.',
            style: context.lpgText.bodyMedium?.copyWith(
              color: context.lpgColors.textSecondary,
            ),
          ),
          const SizedBox(height: LpgSpacing.md),
          LpgTextField(
            label: 'New delivery date',
            controller: _dateText,
            readOnly: true,
            isRequired: true,
            prefixIcon: LpgIcons.calendar,
            onTap: _busy ? null : _pick,
          ),
          if (_error != null) ...[
            const SizedBox(height: LpgSpacing.sm),
            LpgBanner(tone: LpgTone.danger, message: _error!),
          ],
          const SizedBox(height: LpgSpacing.lg),
          LpgButton(
            label: 'Reschedule',
            isLoading: _busy,
            expand: true,
            onPressed: _busy ? null : _send,
          ),
        ],
      ),
    );
  }
}

/// Records why a delivery failed and what happens to the order next.
class FailedDeliverySheet extends ConsumerStatefulWidget {
  const FailedDeliverySheet({super.key, required this.order});

  final OrderResponse order;

  @override
  ConsumerState<FailedDeliverySheet> createState() =>
      _FailedDeliverySheetState();
}

class _FailedDeliverySheetState extends ConsumerState<FailedDeliverySheet> {
  final _note = TextEditingController();
  String _reason = failedDeliveryReasons.keys.first;
  String _resolution = 'reschedule';
  String? _error;
  bool _busy = false;

  @override
  void dispose() {
    _note.dispose();
    super.dispose();
  }

  Future<void> _send() async {
    setState(() {
      _busy = true;
      _error = null;
    });
    final note = _note.text.trim();
    final result = await ref
        .read(orderApiProvider)
        .recordFailedDelivery(
          widget.order.id,
          reasonCode: _reason,
          resolutionAction: _resolution,
          note: note.isEmpty ? null : note,
        );
    if (!mounted) return;
    switch (result) {
      case Success<OrderResponse>():
        Navigator.of(context).pop(true);
      case FailureResult<OrderResponse>(:final failure):
        setState(() {
          _busy = false;
          _error = failure.message;
        });
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = context.lpgText;
    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        mainAxisSize: MainAxisSize.min,
        children: [
          LpgDropdownField<String>(
            label: 'Why did it fail?',
            value: _reason,
            items: failedDeliveryReasons,
            onChanged: _busy
                ? null
                : (value) {
                    if (value != null) setState(() => _reason = value);
                  },
          ),
          const SizedBox(height: LpgSpacing.md),
          Text('What next?', style: text.titleSmall),
          const SizedBox(height: LpgSpacing.sm),
          LpgChoiceChips<String>(
            options: failedDeliveryResolutions,
            selected: _resolution,
            onSelected: (value) {
              if (!_busy && value != null) setState(() => _resolution = value);
            },
          ),
          const SizedBox(height: LpgSpacing.md),
          LpgTextField(
            label: 'Note',
            hintText: 'Gate locked, back after 6 pm',
            controller: _note,
            maxLines: 2,
            maxLength: 500,
            textCapitalization: TextCapitalization.sentences,
            enabled: !_busy,
          ),
          if (_error != null) ...[
            const SizedBox(height: LpgSpacing.sm),
            LpgBanner(tone: LpgTone.danger, message: _error!),
          ],
          const SizedBox(height: LpgSpacing.lg),
          LpgButton(
            label: 'Record failed delivery',
            variant: LpgButtonVariant.destructive,
            isLoading: _busy,
            expand: true,
            onPressed: _busy ? null : _send,
          ),
        ],
      ),
    );
  }
}
