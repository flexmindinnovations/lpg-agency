import 'package:core/core.dart';

/// The plain-language text for each kind of failure. English for now; story
/// 2.4 moves it into the shared string catalogue. Never the server's sentence.
class LpgErrorCopy {
  const LpgErrorCopy({
    required this.title,
    required this.message,
    this.retryable = true,
  });

  final String title;
  final String message;

  /// Whether asking again can help; where it cannot, no Retry button shows.
  final bool retryable;

  /// The copy for [kind]. [hasCode] says a support code will be shown under
  /// the message, which lets the server message point at it.
  static LpgErrorCopy of(
    ErrorKind kind, {
    bool hasCode = false,
  }) => switch (kind) {
    ErrorKind.offline => const LpgErrorCopy(
      title: 'No internet',
      message: 'Check your internet connection and try again.',
    ),
    ErrorKind.busy => const LpgErrorCopy(
      title: 'We are busy right now',
      message: 'This is taking longer than usual. Try again after a minute.',
    ),
    ErrorKind.sessionExpired => const LpgErrorCopy(
      title: 'Sign in again',
      message: 'You have been signed out. Sign in to continue.',
      retryable: false,
    ),
    ErrorKind.forbidden => const LpgErrorCopy(
      title: 'This is not available for your account',
      message: 'Ask your agency if you need it.',
      retryable: false,
    ),
    ErrorKind.agencyBlocked => const LpgErrorCopy(
      title: 'Not available right now',
      message:
          "Your agency's account is not active. Please contact your agency.",
      retryable: false,
    ),
    ErrorKind.notFound => const LpgErrorCopy(
      title: 'We cannot find this',
      message: 'It may have been removed. Go back and open it again.',
      retryable: false,
    ),
    ErrorKind.rejected => const LpgErrorCopy(
      title: 'We could not accept this',
      message: 'Check what you entered and try again.',
    ),
    ErrorKind.server => LpgErrorCopy(
      title: 'We could not load this',
      message: hasCode
          ? 'The problem is with our system. Try again. If it keeps '
                'happening, tell your agency the code shown below.'
          : 'The problem is with our system. Please try again.',
    ),
    ErrorKind.unknown => const LpgErrorCopy(
      title: 'We could not load this',
      message: 'Please try again.',
    ),
  };

  /// The notice above content that is still on screen after a refresh failed.
  static const staleNotice =
      'We could not update this. You are seeing older information.';

  /// The notice above content shown from saved information while offline.
  static const offlineNotice =
      'No internet. Showing information saved on this phone.';
}
