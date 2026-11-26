import { ChangeDetectionStrategy, Component, computed, input } from '@angular/core';
import { InfoTipComponent } from '../info-tip/info-tip.component';

/**
 * A single label/value row inside an `<lpg-detail-list>`: the label on the
 * left, the projected value beside it. The look comes from the dashboard's
 * global `.detail-item` rules, shared with the hand-written rows on other
 * screens, so there is only one definition.
 */
@Component({
  selector: 'lpg-detail-item',
  standalone: true,
  imports: [InfoTipComponent],
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { class: 'detail-item' },
  template: `
    @if (info(); as text) {
      <!-- The last word and the icon wrap together, so the icon is never alone. -->
      <span class="detail-label"
        >{{ words().start
        }}<span class="detail-label__tail">{{ words().last }}<lpg-info-tip [text]="text" /></span
      ></span>
    } @else {
      <span class="detail-label">{{ label() }}</span>
    }
    <span class="detail-value"><ng-content /></span>
  `,
})
export class DetailItemComponent {
  readonly label = input.required<string>();
  /** A short explanation of the label, shown from an info icon beside it. */
  readonly info = input('');

  protected readonly words = computed(() => {
    const label = this.label();
    const split = label.lastIndexOf(' ') + 1;
    return { start: label.slice(0, split), last: label.slice(split) };
  });
}
