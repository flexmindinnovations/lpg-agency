import { ChangeDetectionStrategy, Component } from '@angular/core';

/** Placeholder landing view. Replaced by the real dashboard in a later phase. */
@Component({
  selector: 'lpg-home',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h1 class="page-title">Repository foundation</h1>
    <p class="page-lede">
      The Angular workspace, design-token system and shared libraries are in place. Business
      features have not been built yet.
    </p>

    <section class="card" aria-labelledby="foundation-heading">
      <h2 id="foundation-heading" class="card__title">What exists</h2>
      <ul class="card__list">
        <li>Nx workspace with enforced feature-library boundaries</li>
        <li>Design tokens — light, dark and high-contrast themes</li>
        <li>Shared UI, util and data-access libraries</li>
        <li>RFC 7807 error handling and correlation IDs</li>
      </ul>
    </section>
  `,
})
export class Home {}
