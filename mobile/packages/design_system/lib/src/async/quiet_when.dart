import 'package:riverpod/riverpod.dart';

/// `AsyncValue.when` that never takes data off the screen.
///
/// Riverpod's own `when` cannot express the loading rules every LPG screen
/// follows, because a provider that is quietly retrying its first load counts
/// as "reloading with an error", and the flags that keep old data on screen
/// during a refresh would show that retry as an error screen:
///
/// - **Has a value** (first load done, now refreshing, retrying a refresh, or
///   a refresh failed): show [data] with the last good value. Stale numbers
///   beat a blank screen, and the next refresh replaces them.
/// - **No value yet and still working** (first request, or its quiet retry):
///   show [loading], the skeleton.
/// - **No value and not working** (the first request and its retry both
///   failed): show [error].
extension QuietAsyncValue<T> on AsyncValue<T> {
  R whenQuiet<R>({
    required R Function() loading,
    required R Function(Object error, StackTrace stackTrace) error,
    required R Function(T data) data,
  }) {
    if (hasValue) return data(requireValue);
    if (isLoading) return loading();
    return error(this.error!, stackTrace!);
  }
}
