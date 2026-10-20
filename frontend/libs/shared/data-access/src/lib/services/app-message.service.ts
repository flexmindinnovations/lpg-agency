import { Injectable } from '@angular/core';
import { MessageService, type ToastMessageOptions } from 'primeng/api';

/** How long each kind of toast stays up when the caller sets no `life`. */
const DEFAULT_LIFE_MS: Readonly<Record<string, number>> = {
  success: 4000,
  info: 4000,
  warn: 5000,
  error: 6000,
};

/**
 * The app's one `MessageService` (provided in place of PrimeNG's in
 * `app.config.ts`), so every toast behaves the same whether it came from
 * `NotifyService`, `globalErrorToastInterceptor` or a feature's own
 * `MessageService.add()` call (QA DO-21):
 *
 * - A success clears whatever was on screen first. Otherwise a stale
 *   "One or more fields failed validation." stays up next to the
 *   "Complaint raised" that proves the retry worked.
 * - A toast with no `life` gets the same per-severity lifetime as
 *   `NotifyService`, so no feature's toast lingers longer than another's.
 */
@Injectable()
export class AppMessageService extends MessageService {
  override add(message: ToastMessageOptions): void {
    if (!message) return;
    if (message.severity === 'success' && !message.key) this.clear();
    super.add(withDefaultLife(message));
  }

  override addAll(messages: ToastMessageOptions[]): void {
    if (!messages?.length) return;
    if (messages.some((m) => m.severity === 'success' && !m.key)) this.clear();
    super.addAll(messages.map(withDefaultLife));
  }
}

function withDefaultLife(message: ToastMessageOptions): ToastMessageOptions {
  if (message.sticky || message.life != null) return message;
  const life = DEFAULT_LIFE_MS[message.severity ?? ''];
  return life ? { ...message, life } : message;
}
