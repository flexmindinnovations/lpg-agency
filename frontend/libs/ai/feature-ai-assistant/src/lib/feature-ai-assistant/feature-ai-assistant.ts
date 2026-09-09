import { HeaderPortalDirective, HeaderTitlePortalDirective } from '@lpg/shared/ui/app-shell';
import { HasPermissionDirective, MarkdownPipe, StatCardComponent, type StatTone } from '@lpg/shared/ui';
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
import { catchError, of } from 'rxjs';
import { ButtonDirective, ButtonIcon, ButtonLabel } from 'primeng/button';
import { Message } from 'primeng/message';
import { AiAssistantService, DashboardService, type AskAiAssistantResponse } from '@lpg/shared/data-access';

interface QaEntry {
  question: string;
  response: AskAiAssistantResponse | null;
  error: boolean;
}

interface QuickKpi {
  title: string;
  value: string;
  icon: string;
  tone: StatTone;
  permission: string;
}

interface SuggestedPrompt {
  label: string;
  question: string;
  icon: string;
}

const DISABLED_REASON_MESSAGES: Record<string, string> = {
  gateway_disabled:
    "The AI Assistant isn't enabled for your organization yet — an admin can turn it on under Tenant Configuration (ai_gateway_enabled).",
  budget_exceeded: "Today's AI usage limit has been reached. Try again tomorrow.",
  provider_error: 'Something went wrong reaching the AI provider. Please try again.',
};

/** Starter questions covering each of the three tools the assistant can
 * actually call (`get_today_delivery_status`, `get_inventory_overview`,
 * `get_open_complaints_summary`, ADR-045) plus one that exercises all
 * three together — a fixed, code-defined list (no backend endpoint of its
 * own), same "static and reviewed, not dynamically generated" spirit as
 * the tool registry itself. */
const SUGGESTED_PROMPTS: readonly SuggestedPrompt[] = [
  {
    label: "Today's inventory",
    question: "What's today's inventory situation across all locations?",
    icon: 'pi pi-box',
  },
  {
    label: 'Open complaints',
    question: 'Are there any open complaints right now?',
    icon: 'pi pi-exclamation-circle',
  },
  {
    label: 'Delivery delays',
    question: 'Why might deliveries be delayed today?',
    icon: 'pi pi-clock',
  },
  {
    label: "Today's summary",
    question: "Give me a summary of today's operations: orders, inventory, and complaints.",
    icon: 'pi pi-sparkles',
  },
];

/**
 * AI Command Center (ADR-045) — a read-only operations assistant, styled as
 * a chat thread (chronological, pinned composer, auto-scroll) in the shape
 * of Claude/Gemini/ChatGPT. Each question is still independent (no
 * cross-request conversation memory) — the thread below is purely
 * client-side, for the viewer's own convenience while they're on this page;
 * "Clear conversation" only resets that local view, nothing server-side.
 *
 * The empty state also shows a small live KPI snapshot and a few starter
 * questions — both purely a landing-state convenience, gone the moment a
 * real conversation starts. The KPI snapshot reuses the same
 * `DashboardService.getSummary()` the Agency Overview page calls (every
 * `ai:read` holder already holds the `reports:read` permission that
 * endpoint requires — confirmed against the role grants, not a new
 * permission or endpoint).
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
    StatCardComponent,
    HasPermissionDirective,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  templateUrl: './feature-ai-assistant.html',
  styleUrl: './feature-ai-assistant.css',
})
export class FeatureAiAssistant {
  private readonly aiAssistantService = inject(AiAssistantService);
  private readonly dashboardService = inject(DashboardService);
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
  protected readonly suggestedPrompts = SUGGESTED_PROMPTS;

  protected readonly kpisLoading = signal(true);
  protected readonly kpis = signal<QuickKpi[]>([]);

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

    this.dashboardService
      .getSummary()
      .pipe(catchError(() => of(null)))
      .subscribe((summary) => {
        const inventory = summary?.inventory_by_status ?? {};
        const filled = inventory['filled'] ?? 0;
        const needingAttention =
          (inventory['damaged'] ?? 0) + (inventory['leakage'] ?? 0) + (inventory['quarantine'] ?? 0);

        this.kpis.set([
          {
            title: 'Filled Cylinders',
            value: filled.toLocaleString(),
            icon: 'pi pi-box',
            tone: 'success',
            permission: 'inventory:read',
          },
          {
            title: 'Needing Attention',
            value: needingAttention.toLocaleString(),
            icon: 'pi pi-exclamation-triangle',
            tone: 'danger',
            permission: 'inventory:read',
          },
          {
            title: 'Total Customers',
            value: (summary?.customer_count ?? 0).toLocaleString(),
            icon: 'pi pi-users',
            tone: 'info',
            permission: 'customers:read',
          },
          {
            title: 'Fleet Vehicles',
            value: (summary?.vehicle_count ?? 0).toLocaleString(),
            icon: 'pi pi-truck',
            tone: 'warning',
            permission: 'vehicles:read',
          },
        ]);
        this.kpisLoading.set(false);
      });
  }

  protected ask(text?: string): void {
    const question = (text ?? this.question()).trim();
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
