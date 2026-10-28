import 'package:api_client/api_client.dart';
import 'package:core/core.dart';
import 'package:design_system/design_system.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../../providers.dart';
import '../../data/orders_provider.dart';
import '../../domain/order_flow.dart';

/// The load-out weighment step of sending a trip out, for agencies that
/// weigh every cylinder before loading. One check per cylinder type on the
/// trip: pick the scale, say how many were weighed and how many came up
/// short. Once every type has a passing check the office can send the trip
/// out again.
class WeighmentSection extends ConsumerStatefulWidget {
  const WeighmentSection({
    super.key,
    required this.routeId,
    required this.needed,
    required this.names,
    this.warehouseId,
  });

  final String routeId;

  /// Cylinders to weigh, per cylinder type id.
  final Map<String, int> needed;
  final Map<String, String> names;

  /// Scales at this godown are listed first.
  final String? warehouseId;

  @override
  ConsumerState<WeighmentSection> createState() => _WeighmentSectionState();
}

class _WeighmentSectionState extends ConsumerState<WeighmentSection> {
  String? _scaleId;
  String? _busyType;
  String? _error;
  final Map<String, TextEditingController> _underweight = {};

  @override
  void dispose() {
    for (final c in _underweight.values) {
      c.dispose();
    }
    super.dispose();
  }

  TextEditingController _controllerFor(String typeId) =>
      _underweight.putIfAbsent(typeId, () => TextEditingController(text: '0'));

  Set<String> _passed(List<WeighmentRecord> records) => {
    for (final r in records)
      if (r.passesLoadOut) r.cylinderTypeId,
  };

  Future<void> _record(String typeId, int cylinders) async {
    final underweight = int.tryParse(_controllerFor(typeId).text.trim()) ?? -1;
    final problem = weighmentProblem(
      scaleId: _scaleId,
      cylinders: cylinders,
      underweight: underweight,
    );
    if (problem != null) {
      setState(() => _error = problem);
      return;
    }
    setState(() {
      _busyType = typeId;
      _error = null;
    });
    final result = await ref
        .read(weighmentApiProvider)
        .recordLoadOut(
          widget.routeId,
          scaleId: _scaleId!,
          cylinderTypeId: typeId,
          cylinders: cylinders,
          underweight: underweight,
        );
    if (!mounted) return;
    switch (result) {
      case Success<WeighmentRecord>(:final value):
        setState(() => _busyType = null);
        if (!value.passesLoadOut) {
          setState(
            () => _error =
                '${widget.names[typeId] ?? 'These cylinders'}: $underweight '
                'underweight, so the check did not pass. Replace the short '
                'cylinders and log the check again.',
          );
        }
        ref.invalidate(routeWeighmentsProvider(widget.routeId));
      case FailureResult<WeighmentRecord>(:final failure):
        setState(() {
          _busyType = null;
          _error = failure.message;
        });
    }
  }

  @override
  Widget build(BuildContext context) {
    final text = context.lpgText;
    final scalesAsync = ref.watch(activeScalesProvider);
    final recordsAsync = ref.watch(routeWeighmentsProvider(widget.routeId));

    final records = recordsAsync.value ?? const <WeighmentRecord>[];
    final passed = _passed(records);
    final allDone =
        recordsAsync.hasValue && widget.needed.keys.every(passed.contains);

    final scales =
        [
          for (final s in scalesAsync.value ?? const <ScaleSummary>[])
            if (!s.isExpired) s,
        ]..sort((a, b) {
          final aHere = a.warehouseId == widget.warehouseId ? 0 : 1;
          final bHere = b.warehouseId == widget.warehouseId ? 0 : 1;
          return aHere.compareTo(bHere);
        });
    _scaleId ??= scales.isEmpty ? null : scales.first.id;

    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text('Weigh the cylinders', style: text.titleSmall),
        const SizedBox(height: LpgSpacing.xs),
        Text(
          'Every cylinder on this trip is weighed before it is loaded. Log '
          'one check per cylinder type.',
          style: text.bodySmall?.copyWith(
            color: context.lpgColors.textSecondary,
          ),
        ),
        const SizedBox(height: LpgSpacing.sm),
        if (scalesAsync.hasValue && scales.isEmpty)
          const LpgBanner(
            tone: LpgTone.warning,
            message:
                'No scale in service with a valid certificate, or your role '
                "can't log weighments. Use the web dashboard.",
          )
        else ...[
          LpgDropdownField<String?>(
            label: 'Scale',
            isRequired: true,
            value: scales.any((s) => s.id == _scaleId) ? _scaleId : null,
            items: {for (final s in scales) s.id: s.assetTag},
            onChanged: _busyType != null
                ? null
                : (id) => setState(() => _scaleId = id),
          ),
          for (final entry in widget.needed.entries) ...[
            const SizedBox(height: LpgSpacing.md),
            if (passed.contains(entry.key))
              Row(
                children: [
                  const Icon(LpgIcons.check, size: LpgSizes.iconSm),
                  const SizedBox(width: LpgSpacing.xs),
                  Expanded(
                    child: Text(
                      '${widget.names[entry.key] ?? 'Cylinder'} · '
                      '${entry.value} weighed',
                      style: text.bodyMedium,
                    ),
                  ),
                ],
              )
            else
              Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  Text(
                    '${widget.names[entry.key] ?? 'Cylinder'} · '
                    '${entry.value} to weigh',
                    style: text.bodyMedium,
                  ),
                  const SizedBox(height: LpgSpacing.xs),
                  LpgTextField(
                    label: 'Underweight (0 if none)',
                    controller: _controllerFor(entry.key),
                    keyboardType: TextInputType.number,
                    inputFormatters: [FilteringTextInputFormatter.digitsOnly],
                    enabled: _busyType == null,
                  ),
                  const SizedBox(height: LpgSpacing.xs),
                  LpgButton(
                    label: 'Log check',
                    variant: LpgButtonVariant.tonal,
                    isLoading: _busyType == entry.key,
                    onPressed: _busyType != null || scales.isEmpty
                        ? null
                        : () => _record(entry.key, entry.value),
                  ),
                ],
              ),
          ],
        ],
        if (_error != null) ...[
          const SizedBox(height: LpgSpacing.sm),
          LpgBanner(tone: LpgTone.danger, message: _error!),
        ],
        if (allDone) ...[
          const SizedBox(height: LpgSpacing.sm),
          const LpgBanner(
            tone: LpgTone.success,
            message: 'All cylinders weighed. Send the trip out now.',
          ),
        ],
      ],
    );
  }
}
