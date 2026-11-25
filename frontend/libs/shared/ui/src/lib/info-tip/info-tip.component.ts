import {
  ChangeDetectionStrategy,
  Component,
  DestroyRef,
  ElementRef,
  inject,
  input,
  signal,
  viewChild,
} from '@angular/core';
import { Tooltip } from 'primeng/tooltip';

/**
 * The info icon: a button that shows a short explanation, by touch as well as
 * by mouse and keyboard. Use it for every "what is this?" icon instead of
 * putting `pTooltip` on an `<i>`.
 *
 * A tap or click opens it and keeps it open until it is pressed again, the user
 * presses somewhere else or presses Escape, or the page scrolls. Hovering and
 * tabbing to it show it while the pointer or focus stays.
 *
 * It opens and closes `pTooltip` itself. With `tooltipEvent="focus"` PrimeNG
 * adds no hover, touch or click handlers: its touch handling hides the tooltip
 * as soon as the finger lifts, and its click handler hides it too.
 */
@Component({
  selector: 'lpg-info-tip',
  standalone: true,
  imports: [Tooltip],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <button
      #trigger
      type="button"
      class="info-tip"
      [pTooltip]="text()"
      tooltipEvent="focus"
      [tooltipPosition]="position()"
      [attr.aria-label]="text()"
      [attr.aria-expanded]="isOpen()"
      (click)="onClick($event)"
      (pointerenter)="onPointerEnter($event)"
      (pointerleave)="onPointerLeave($event)"
      (focus)="open()"
      (blur)="close()"
      (keydown.escape)="onEscape($event)"
    >
      <i class="pi pi-info-circle" aria-hidden="true"></i>
    </button>
  `,
  styles: [
    `
      :host {
        display: inline-flex;
        flex-shrink: 0;
      }

      /* At least 24px (WCAG 2.2 target size), without growing the row. */
      .info-tip {
        position: relative;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        inline-size: 1.5rem;
        block-size: 1.5rem;
        margin: 0;
        padding: 0;
        background: transparent;
        border: none;
        border-radius: var(--radius-sm);
        font: inherit;
        line-height: 1;
        color: var(--color-text-secondary);
        cursor: pointer;
        touch-action: manipulation;
        transition: color var(--motion-duration-fast) var(--motion-easing-standard);
      }

      .info-tip:hover,
      .info-tip:focus-visible,
      .info-tip[aria-expanded='true'] {
        color: var(--color-action-primary);
      }

      .info-tip:focus-visible {
        outline: none;
        box-shadow: 0 0 0 2px var(--color-action-primary);
      }

      /* A finger needs more room than the icon shows. */
      @media (pointer: coarse) {
        .info-tip::after {
          content: '';
          position: absolute;
          inset: -0.5rem;
        }
      }
    `,
  ],
})
export class InfoTipComponent {
  readonly text = input.required<string>();
  readonly position = input<'top' | 'bottom' | 'left' | 'right'>('top');

  protected readonly isOpen = signal(false);
  private readonly tooltip = viewChild.required(Tooltip);
  private readonly host: ElementRef<HTMLElement> = inject(ElementRef);

  /** Opened by a press, so it stays when the pointer moves away. */
  private pinned = false;
  private listeners: AbortController | null = null;

  constructor() {
    inject(DestroyRef).onDestroy(() => this.close());
  }

  protected onClick(event: Event): void {
    // The icon often sits in something clickable, such as a grid row.
    event.stopPropagation();
    if (this.pinned) {
      this.close();
    } else {
      this.open();
      this.pinned = true;
    }
  }

  protected onPointerEnter(event: PointerEvent): void {
    if (event.pointerType === 'mouse') this.open();
  }

  protected onPointerLeave(event: PointerEvent): void {
    if (event.pointerType === 'mouse' && !this.pinned) this.close();
  }

  protected onEscape(event: Event): void {
    if (!this.isOpen()) return;
    // Close only the tooltip, not the drawer or dialog around it.
    event.stopPropagation();
    this.close();
  }

  protected close(): void {
    this.pinned = false;
    this.listeners?.abort();
    this.listeners = null;
    this.tooltip().deactivate();
    this.isOpen.set(false);
  }

  protected open(): void {
    const tooltip = this.tooltip();
    if (!tooltip.container) {
      // PrimeNG stays "active" after hiding itself; reset before showing.
      tooltip.deactivate();
      tooltip.activate();
    }
    this.isOpen.set(true);
    if (this.listeners) return;

    this.listeners = new AbortController();
    const options = { capture: true, signal: this.listeners.signal };
    const closeIfOutside = (event: Event) => {
      if (!this.host.nativeElement.contains(event.target as Node)) this.close();
    };
    // Capture phase: grids and overlays may stop the event before it bubbles.
    document.addEventListener('pointerdown', closeIfOutside, options);
    // PrimeNG hides the tooltip when its container scrolls; keep state in step.
    document.addEventListener('scroll', () => this.close(), options);
    window.addEventListener('resize', () => this.close(), options);
  }
}
