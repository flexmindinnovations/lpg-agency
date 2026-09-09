import { HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import { ChangeDetectionStrategy, Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { ButtonDirective, ButtonIcon, ButtonLabel } from 'primeng/button';
import { Message } from 'primeng/message';
import { AiAssistantService, type AskAiAssistantResponse } from '@lpg/shared/data-access';

interface QaEntry {
  question: string;
  response: AskAiAssistantResponse | null;
  error: boolean;
}

const DISABLED_REASON_MESSAGES: Record<string, string> = {
  gateway_disabled:
    "The AI Assistant isn't enabled for your organization yet — an admin can turn it on under Tenant Configuration (ai_gateway_enabled).",
  budget_exceeded: "Today's AI usage limit has been reached. Try again tomorrow.",
  provider_error: 'Something went wrong reaching the AI provider. Please try again.',
};

/**
 * AI Command Center (ADR-045) — a read-only operations assistant. Each
 * question is independent (no cross-request conversation memory); the
 * on-page history below is purely client-side, for the viewer's own
 * convenience while they're on this page.
 */
@Component({
  selector: 'lpg-feature-ai-assistant',
  standalone: true,
  imports: [HeaderTitlePortalDirective, FormsModule, ButtonDirective, ButtonIcon, ButtonLabel, Message],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './feature-ai-assistant.html',
  styleUrl: './feature-ai-assistant.css',
})
export class FeatureAiAssistant {
  private readonly aiAssistantService = inject(AiAssistantService);

  protected readonly question = signal('');
  protected readonly asking = signal(false);
  protected readonly history = signal<QaEntry[]>([]);

  protected readonly disabledReasonMessages = DISABLED_REASON_MESSAGES;

  protected ask(): void {
    const question = this.question().trim();
    if (!question || this.asking()) return;

    this.asking.set(true);
    this.aiAssistantService.ask(question).subscribe({
      next: (response) => {
        this.asking.set(false);
        this.history.update((entries) => [{ question, response, error: false }, ...entries]);
        this.question.set('');
      },
      error: () => {
        this.asking.set(false);
        this.history.update((entries) => [
          { question, response: null, error: true },
          ...entries,
        ]);
        this.question.set('');
      },
    });
  }

  protected onQuestionKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.ask();
    }
  }
}
