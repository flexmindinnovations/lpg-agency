import { ChangeDetectionStrategy, Component } from '@angular/core';
import { RouterLink } from '@angular/router';

@Component({
  selector: 'lpg-not-found',
  standalone: true,
  imports: [RouterLink],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <h1 class="page-title">Page not found</h1>
    <p class="page-lede">That route does not exist.</p>
    <a routerLink="/" class="link">Return home</a>
  `,
})
export class NotFound {}
