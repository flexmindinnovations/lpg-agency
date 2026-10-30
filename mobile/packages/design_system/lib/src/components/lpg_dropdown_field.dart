import 'package:flutter/material.dart';

import '../icons.dart';
import '../layout.dart';
import '../theme.dart';
import 'lpg_feedback.dart';
import 'lpg_list_tile.dart';
import 'lpg_text_field.dart';

/// More options than this and the picker gains a search box.
const _searchableFrom = 7;

/// A labelled field that looks exactly like [LpgTextField] (same fill,
/// border, radius and focus colour, all from the theme's
/// `inputDecorationTheme`) and opens a themed bottom sheet to choose from.
///
/// The sheet suits a phone better than a popup menu: big touch targets, a
/// tick on the current choice, optional per-option [icons] and a search box
/// once the list is long. Use it for any "pick one" with four or more
/// options, or whenever the options come from data and may keep growing;
/// [LpgChoiceChips] stays for a switch between two or three.
///
/// [items] maps each value to its display text. [placeholder], when given,
/// is shown while nothing is chosen and, once something is, becomes a row
/// that clears the choice. A
/// [value] that is not among [items] counts as "nothing selected".
class LpgDropdownField<T> extends StatefulWidget {
  const LpgDropdownField({
    super.key,
    required this.value,
    required this.items,
    required this.onChanged,
    this.label,
    this.placeholder,
    this.prefixIcon,
    this.icons,
    this.validator,
    this.isRequired = false,
  });

  final T value;
  final Map<T, String> items;
  final void Function(T?)? onChanged;
  final String? label;
  final String? placeholder;
  final IconData? prefixIcon;

  /// Optional icon for each option, shown in the sheet and the closed field.
  final Map<T, IconData>? icons;
  final String? Function(T?)? validator;
  final bool isRequired;

  @override
  State<LpgDropdownField<T>> createState() => _LpgDropdownFieldState<T>();
}

class _LpgDropdownFieldState<T> extends State<LpgDropdownField<T>> {
  final _fieldKey = GlobalKey<FormFieldState<T>>();

  T? get _selected =>
      widget.items.containsKey(widget.value) ? widget.value : null;

  @override
  void didUpdateWidget(LpgDropdownField<T> oldWidget) {
    super.didUpdateWidget(oldWidget);
    // The parent owns the value, so keep the form field's copy (the one a
    // validator sees) in step with it.
    if (oldWidget.value != widget.value) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        _fieldKey.currentState?.didChange(_selected);
      });
    }
  }

  Future<void> _open(FormFieldState<T> state) async {
    final picked = await LpgFeedback.showSheet<_Pick<T>>(
      context,
      title: widget.label ?? widget.placeholder,
      builder: (_) => _PickerList<T>(
        items: widget.items,
        icons: widget.icons,
        selected: _selected,
        placeholder: widget.placeholder,
      ),
    );
    if (picked == null) return;
    state.didChange(picked.value);
    widget.onChanged?.call(picked.value);
  }

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final text = context.lpgText;
    final enabled = widget.onChanged != null;
    final selected = _selected;
    final shown = selected == null ? null : widget.items[selected];
    final shownIcon = selected == null ? null : widget.icons?[selected];

    final field = FormField<T>(
      key: _fieldKey,
      initialValue: selected,
      validator: widget.validator,
      enabled: enabled,
      builder: (state) {
        final label = shown ?? widget.placeholder;
        return Semantics(
          button: true,
          enabled: enabled,
          label: [
            if (widget.label != null)
              widget.isRequired ? '${widget.label}, required' : widget.label!,
            ?label,
          ].join(', '),
          excludeSemantics: true,
          onTap: enabled ? () => _open(state) : null,
          child: InkWell(
            borderRadius: BorderRadius.circular(LpgRadius.lg),
            onTap: enabled ? () => _open(state) : null,
            child: InputDecorator(
              isEmpty: false,
              decoration: InputDecoration(
                enabled: enabled,
                errorText: state.errorText,
                fillColor: enabled ? colors.card : colors.surfaceOverlay,
                prefixIcon: widget.prefixIcon == null
                    ? null
                    : Icon(widget.prefixIcon, size: LpgSizes.iconMd),
                suffixIcon: Icon(
                  LpgIcons.chevronDown,
                  color: colors.textSecondary,
                ),
              ),
              // One line that ends in an ellipsis, so a long address never
              // looks cut off mid-word (CA-14); the sheet shows it in full.
              child: Row(
                children: [
                  if (shownIcon != null) ...[
                    Icon(shownIcon, size: LpgSizes.iconMd),
                    const SizedBox(width: LpgSpacing.sm),
                  ],
                  Expanded(
                    child: Text(
                      label ?? '',
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: text.bodyLarge?.copyWith(
                        color: shown == null
                            ? colors.textDisabled
                            : (enabled
                                  ? colors.textPrimary
                                  : colors.textSecondary),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );

    if (widget.label == null) return field;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        ExcludeSemantics(
          child: LpgFieldLabel(widget.label!, isRequired: widget.isRequired),
        ),
        field,
      ],
    );
  }
}

/// What the sheet returns, so choosing "nothing" (the placeholder row) is
/// different from dismissing the sheet.
class _Pick<T> {
  const _Pick(this.value);

  final T? value;
}

class _PickerList<T> extends StatefulWidget {
  const _PickerList({
    required this.items,
    required this.icons,
    required this.selected,
    required this.placeholder,
  });

  final Map<T, String> items;
  final Map<T, IconData>? icons;
  final T? selected;
  final String? placeholder;

  @override
  State<_PickerList<T>> createState() => _PickerListState<T>();
}

class _PickerListState<T> extends State<_PickerList<T>> {
  String _query = '';

  @override
  Widget build(BuildContext context) {
    final colors = context.lpgColors;
    final needle = _query.trim().toLowerCase();
    final entries = [
      for (final e in widget.items.entries)
        if (needle.isEmpty || e.value.toLowerCase().contains(needle)) e,
    ];
    final searchable = widget.items.length > _searchableFrom;
    // The placeholder row is how a choice is cleared, so it only appears
    // once there is something to clear.
    final showPlaceholder =
        widget.placeholder != null && widget.selected != null && needle.isEmpty;

    return Column(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (searchable) ...[
          TextField(
            decoration: InputDecoration(
              hintText: 'Search',
              prefixIcon: Icon(LpgIcons.search, size: LpgSizes.iconMd),
            ),
            onChanged: (v) => setState(() => _query = v),
          ),
          const SizedBox(height: LpgSpacing.sm),
        ],
        Flexible(
          child: ListView(
            shrinkWrap: true,
            children: [
              if (showPlaceholder)
                LpgListTile(
                  title: widget.placeholder!,
                  onTap: () => Navigator.of(context).pop(_Pick<T>(null)),
                ),
              for (final e in entries)
                LpgListTile(
                  leadingIcon: widget.icons?[e.key],
                  title: e.value,
                  trailing: e.key == widget.selected
                      ? Icon(LpgIcons.check, color: colors.actionPrimary)
                      : null,
                  onTap: () => Navigator.of(context).pop(_Pick<T>(e.key)),
                ),
              if (entries.isEmpty)
                Padding(
                  padding: const EdgeInsets.all(LpgSpacing.lg),
                  child: Text(
                    'Nothing matches "$_query".',
                    textAlign: TextAlign.center,
                    style: context.lpgText.bodyMedium?.copyWith(
                      color: colors.textSecondary,
                    ),
                  ),
                ),
            ],
          ),
        ),
      ],
    );
  }
}
