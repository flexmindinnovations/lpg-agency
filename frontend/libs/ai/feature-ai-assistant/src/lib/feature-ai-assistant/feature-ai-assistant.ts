import { HeaderPortalDirective, HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import { MarkdownPipe } from '@lpg/shared/ui';
import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  effect,
  inject,
  signal,
  viewChild,
} from '@angular/core';
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
 * AI Command Center (ADR-045) — a read-only operations assistant, styled as
 * a chat thread (chronological, pinned composer, auto-scroll) in the shape
 * of Claude/Gemini/ChatGPT. Each question is still independent (no
 * cross-request conversation memory) — the thread below is purely
 * client-side, for the viewer's own convenience while they're on this page;
 * "Clear conversation" only resets that local view, nothing server-side.
 */
@Component({
  selector: 'lpg-feature-ai-assistant',
  standalone: true,
  imports: [
    HeaderTitlePortalDirective,
    HeaderPortalDirective,
    FormsModule,
    ButtonDirective,
    ButtonIcon,
    ButtonLabel,
    Message,
    MarkdownPipe,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './feature-ai-assistant.html',
  styleUrl: './feature-ai-assistant.css',
})
export class FeatureAiAssistant {
  private readonly aiAssistantService = inject(AiAssistantService);
  private readonly threadEl = viewChild<ElementRef<HTMLElement>>('threadEl');

  protected readonly question = signal('');
  protected readonly asking = signal(false);
  protected readonly history = signal<QaEntry[]>([]);
  /** The just-sent question, shown as its own bubble immediately (before
   * the response arrives) — a real chat thread shows what you sent right
   * away, not only once the answer lands next to it. Cleared once the
   * matching entry is pushed onto `history`. */
  protected readonly pendingQuestion = signal<string | null>(null);

  protected readonly disabledReasonMessages = DISABLED_REASON_MESSAGES;

  constructor() {
    // Scroll the thread to the newest message whenever it changes (a new
    // question, a new answer, or the "thinking" indicator appearing) — the
    // same behavior as every chat product this page is modeled on. Runs
    // after the DOM has actually updated, not just after the signal write.
    effect(() => {
      this.history();
      this.asking();
      this.pendingQuestion();
      const el = this.threadEl()?.nativeElement;
      if (!el) return;
      queueMicrotask(() => {
        el.scrollTop = el.scrollHeight;
      });
    });
  }

  protected ask(): void {
    const question = this.question().trim();
    if (!question || this.asking()) return;

    this.asking.set(true);
    this.question.set('');
    this.pendingQuestion.set(question);
    this.aiAssistantService.ask(question).subscribe({
      next: (response) => {
        this.asking.set(false);
        this.pendingQuestion.set(null);
        this.history.update((entries) => [...entries, { question, response, error: false }]);
      },
      error: () => {
        this.asking.set(false);
        this.pendingQuestion.set(null);
        this.history.update((entries) => [
          ...entries,
          { question, response: null, error: true },
        ]);
      },
    });
  }

  protected onQuestionKeydown(event: KeyboardEvent): void {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault();
      this.ask();
    }
  }

  protected clearConversation(): void {
    this.history.set([]);
  }
}
