import { Injectable, inject } from '@angular/core';
import { MessageService } from 'primeng/api';

/**
 * Thin, app-wide wrapper over PrimeNG's `MessageService`.
 *
 * The one place every feature should reach for toast feedback — not a
 * direct `MessageService.add()` call, which is how this codebase ended
 * up with ~18 hand-rolled `{ severity: 'error', summary: 'Error', ... }`
 * call sites and 3 features with no toast feedback at all. Errors on
 * mutating requests are usually covered automatically by
 * `globalErrorToastInterceptor`; this is for the paths that still need
 * an explicit call — success messages (never auto-generated) and the
 * couple of read requests deliberately excluded from the interceptor.
 */
@Injectable({ providedIn: 'root' })
export class NotifyService {
  private readonly messageService = inject(MessageService);

  success(detail: string, summary = 'Success'): void {
    this.messageService.add({ severity: 'success', summary, detail, life: 4000 });
  }

  info(detail: string, summary = 'Info'): void {
    this.messageService.add({ severity: 'info', summary, detail, life: 4000 });
  }

  warn(detail: string, summary = 'Warning'): void {
    this.messageService.add({ severity: 'warn', summary, detail, life: 5000 });
  }

  error(detail: string, summary = 'Error'): void {
    this.messageService.add({ severity: 'error', summary, detail, life: 6000 });
  }
}
