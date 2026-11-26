import { ChangeDetectionStrategy, Component, input } from '@angular/core';

/**
 * A single label/value row inside an `<lpg-detail-list>`: the label on the
 * left, the projected value beside it. The look comes from the dashboard's
 * global `.detail-item` rules, shared with the hand-written rows on other
 * screens, so there is only one definition.
 */
@Component({
  selector: 'lpg-detail-item',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  host: { class: 'detail-item' },
  template: `
    <span class="detail-label">{{ label() }}</span>
    <span class="detail-value"><ng-content /></span>
  `,
})
export class DetailItemComponent {
  readonly label = input.required<string>();
}
