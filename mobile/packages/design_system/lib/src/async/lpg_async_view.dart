import 'package:core/core.dart';
import 'package:flutter/material.dart';
import 'package:riverpod/riverpod.dart';

import '../components/lpg_banner.dart';
import '../components/lpg_empty_state.dart';
import '../components/lpg_skeleton.dart';
import '../layout.dart';
import '../tone.dart';
import 'lpg_error_copy.dart';
import 'quiet_when.dart';

/// Builds a custom error state; [retry] is `null` when asking again cannot
/// help (a refusal) or the screen gave no retry.
typedef LpgErrorBuilder =
    Widget Function(BuildContext context, Object error, VoidCallback? retry);

/// An [LpgErrorBuilder] for a small section of a screen: the same friendly
/// copy as the full error state, as a banner (with Retry where it can help),
/// so one failed section does not take over the whole screen.
Widget lpgErrorBanner(BuildContext context, Object error, VoidCallback? retry) {
  final code = supportCodeOf(error);
  final copy = LpgErrorCopy.of(errorKindOf(error), hasCode: code != null);
  return LpgBanner(
    tone: LpgTone.danger,
    title: copy.title,
    message: code == null ? copy.message : '${copy.message}\nCode: $code',
    actionLabel: retry == null ? null : 'Retry',
    onAction: retry,
  );
}

/// An [LpgErrorBuilder] for a screen body inside a `RefreshIndicator`: the
/// full friendly error state in a scrollable, so pulling down still refreshes.
Widget lpgScrollableError(
  BuildContext context,
  Object error,
  VoidCallback? retry,
) {
  final code = supportCodeOf(error);
  final copy = LpgErrorCopy.of(errorKindOf(error), hasCode: code != null);
  return ListView(
    physics: const AlwaysScrollableScrollPhysics(),
    padding: LpgSpacing.page,
    children: [
      LpgErrorState(
        title: copy.title,
        message: copy.message,
        supportCode: code,
        onRetry: retry,
      ),
    ],
  );
}

/// The one loading, empty, error and content switch every screen uses in
/// place of a hand-written `.when(...)`.
///
/// - **No data yet**: the [skeleton] (default: a list of cards). This also
///   covers the first quiet retry, so a blip never shows an error.
/// - **Failed** (the retry failed too): a friendly error with Retry, from the
///   error taxonomy (`ErrorKind`), never the server's own sentence.
/// - **Has data**: [data]; or [empty] when [isEmpty] says there is nothing.
///   Data stays on screen through refreshes and failed refreshes; a failed
///   refresh adds a one-line notice above it, and [offline] adds another.
///
/// Boxes: use this inside screens and sections. For a `CustomScrollView`, use
/// [SliverLpgAsyncView]. Set [expand] when [data] is itself scrollable in a
/// bounded parent (the notice is then placed above it).
class LpgAsyncView<T> extends StatelessWidget {
  const LpgAsyncView({
    super.key,
    required this.value,
    required this.data,
    this.skeleton,
    this.isEmpty,
    this.empty,
    this.onRetry,
    this.errorBuilder,
    this.offline = false,
    this.showStaleNotice = true,
    this.expand = false,
  });

  final AsyncValue<T> value;
  final Widget Function(BuildContext context, T data) data;

  /// Shown until the first answer. Should match the real layout.
  final Widget? skeleton;

  /// Whether [value]'s data means "nothing to show"; then [empty] is built.
  final bool Function(T data)? isEmpty;
  final Widget? empty;

  /// What Retry does, typically `() => ref.invalidate(provider)`.
  final VoidCallback? onRetry;

  /// Replaces the default friendly error state.
  final LpgErrorBuilder? errorBuilder;

  /// The device is offline and [data] comes from saved information.
  final bool offline;

  /// Show the one-line notice when a refresh failed behind shown data.
  final bool showStaleNotice;

  final bool expand;

  @override
  Widget build(BuildContext context) => value.whenQuiet(
    loading: () => skeleton ?? const LpgSkeletonList(itemCount: 4),
    error: (error, _) => _error(context, error),
    data: (data) => _content(context, data),
  );

  Widget _error(BuildContext context, Object error) {
    final code = supportCodeOf(error);
    final copy = LpgErrorCopy.of(errorKindOf(error), hasCode: code != null);
    final retry = copy.retryable ? onRetry : null;
    final custom = errorBuilder;
    if (custom != null) return custom(context, error, retry);
    return LpgErrorState(
      title: copy.title,
      message: copy.message,
      supportCode: code,
      onRetry: retry,
    );
  }

  Widget _content(BuildContext context, T loaded) {
    if (isEmpty?.call(loaded) ?? false) {
      return empty ?? const SizedBox.shrink();
    }
    final content = data(context, loaded);
    final notice = _notice(context);
    if (notice == null) return content;
    return Column(
      mainAxisSize: expand ? MainAxisSize.max : MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        notice,
        const SizedBox(height: LpgSpacing.sm),
        if (expand) Expanded(child: content) else content,
      ],
    );
  }

  Widget? _notice(BuildContext context) {
    if (offline) {
      return const LpgBanner(
        message: LpgErrorCopy.offlineNotice,
        tone: LpgTone.warning,
      );
    }
    if (showStaleNotice && value.hasError && !value.isLoading) {
      return LpgBanner(
        message: LpgErrorCopy.staleNotice,
        tone: LpgTone.warning,
        actionLabel: onRetry == null ? null : 'Retry',
        onAction: onRetry,
      );
    }
    return null;
  }
}

/// [LpgAsyncView] for a `CustomScrollView`: every state is a sliver. [data]
/// returns the content slivers.
class SliverLpgAsyncView<T> extends StatelessWidget {
  const SliverLpgAsyncView({
    super.key,
    required this.value,
    required this.data,
    this.skeleton,
    this.isEmpty,
    this.empty,
    this.onRetry,
    this.offline = false,
    this.showStaleNotice = true,
  });

  final AsyncValue<T> value;

  /// Returns a sliver (a `SliverList`, `SliverToBoxAdapter`, ...).
  final Widget Function(BuildContext context, T data) data;
  final Widget? skeleton;
  final bool Function(T data)? isEmpty;
  final Widget? empty;
  final VoidCallback? onRetry;
  final bool offline;
  final bool showStaleNotice;

  @override
  Widget build(BuildContext context) => value.whenQuiet(
    loading: () => SliverToBoxAdapter(
      child: skeleton ?? const LpgSkeletonList(itemCount: 4),
    ),
    error: (error, _) {
      final code = supportCodeOf(error);
      final copy = LpgErrorCopy.of(errorKindOf(error), hasCode: code != null);
      return SliverFillRemaining(
        hasScrollBody: false,
        child: LpgErrorState(
          title: copy.title,
          message: copy.message,
          supportCode: code,
          onRetry: copy.retryable ? onRetry : null,
        ),
      );
    },
    data: (loaded) {
      if (isEmpty?.call(loaded) ?? false) {
        return SliverFillRemaining(
          hasScrollBody: false,
          child: empty ?? const SizedBox.shrink(),
        );
      }
      final content = data(context, loaded);
      final notice = _notice();
      if (notice == null) return content;
      return SliverMainAxisGroup(
        slivers: [
          SliverToBoxAdapter(child: notice),
          content,
        ],
      );
    },
  );

  Widget? _notice() {
    if (offline) {
      return const LpgBanner(
        message: LpgErrorCopy.offlineNotice,
        tone: LpgTone.warning,
      );
    }
    if (showStaleNotice && value.hasError && !value.isLoading) {
      return LpgBanner(
        message: LpgErrorCopy.staleNotice,
        tone: LpgTone.warning,
        actionLabel: onRetry == null ? null : 'Retry',
        onAction: onRetry,
      );
    }
    return null;
  }
}
