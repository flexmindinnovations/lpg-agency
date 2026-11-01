import 'package:flutter/material.dart';

import '../icons.dart';
import '../layout.dart';
import '../theme.dart';
import 'lpg_empty_state.dart';

/// What a list tile uses to open an item: in the right-hand pane on a tablet,
/// or by navigating on a phone.
class LpgMasterDetailController {
  LpgMasterDetailController._(this._state);

  final _LpgMasterDetailState _state;

  /// The item open in the detail pane, if any.
  String? get selectedId => _state._selectedId;

  /// Whether the list and detail are on screen together.
  bool get twoPane => _state._twoPane;

  /// Shows [id] in the detail pane and returns `true`; on a phone it does
  /// nothing and returns `false`, so the caller navigates instead.
  bool open(String id) => _state._open(id);
}

/// A list ([masterBuilder]) beside the selected item's detail
/// ([detailBuilder]) when the screen is a tablet (>= 840px wide); just the
/// list on a phone, where tapping an item navigates to its own page.
class LpgMasterDetail extends StatefulWidget {
  const LpgMasterDetail({
    super.key,
    required this.masterBuilder,
    required this.detailBuilder,
    this.initialSelectedId,
    this.emptyMessage = 'Select an item to see its details.',
    this.emptyIcon = LpgIcons.empty,
    this.masterWidth = 420,
  });

  final Widget Function(BuildContext context, LpgMasterDetailController c)
  masterBuilder;
  final Widget Function(BuildContext context, String id) detailBuilder;
  final String? initialSelectedId;
  final String emptyMessage;
  final IconData emptyIcon;
  final double masterWidth;

  @override
  State<LpgMasterDetail> createState() => _LpgMasterDetailState();
}

class _LpgMasterDetailState extends State<LpgMasterDetail> {
  late String? _selectedId = widget.initialSelectedId;
  bool _twoPane = false;

  bool _open(String id) {
    if (!_twoPane) return false;
    setState(() => _selectedId = id);
    return true;
  }

  @override
  Widget build(BuildContext context) {
    _twoPane = LpgBreakpoints.isExpanded(context);
    final master = widget.masterBuilder(
      context,
      LpgMasterDetailController._(this),
    );
    if (!_twoPane) return master;

    final id = _selectedId;
    return Row(
      children: [
        SizedBox(width: widget.masterWidth, child: master),
        VerticalDivider(width: 1, color: context.lpgColors.borderDefault),
        Expanded(
          child: id == null
              ? LpgEmptyState(
                  message: widget.emptyMessage,
                  icon: widget.emptyIcon,
                )
              : KeyedSubtree(
                  key: ValueKey(id),
                  child: widget.detailBuilder(context, id),
                ),
        ),
      ],
    );
  }
}
