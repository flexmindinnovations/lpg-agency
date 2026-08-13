import { ChangeDetectionStrategy, Component, computed, inject } from '@angular/core';
import { AuthService } from '@lpg/shared/data-access';

/**
 * Read-only account summary — reachable from the profile menu's "My
 * Profile" item. No edit form yet: the identity domain has no writable
 * self-service fields today (role/tenant are admin-managed, and this app
 * has no `full_name` column to edit — see `ProfileMenuComponent`'s
 * `displayNameFromEmail` doc comment). A real destination that's honest
 * about what it can do, rather than a stub.
 */
@Component({
  selector: 'lpg-profile',
  standalone: true,
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="profile-page">
      <div class="page-header">
        <div class="page-header__text">
          <h1 class="page-title">My Profile</h1>
          <p class="page-subtitle">Your account information. Contact an administrator to update your role or email.</p>
        </div>
      </div>

      <dl class="profile-page__list">
        <div class="profile-page__row">
          <dt class="info-label">Email address</dt>
          <dd>{{ email() || 'Not set' }}</dd>
        </div>
        <div class="profile-page__row">
          <dt class="info-label">Role</dt>
          <dd class="profile-page__role">{{ role() || 'Not assigned' }}</dd>
        </div>
      </dl>
    </div>
  `,
  styles: [
    `
      .profile-page {
        max-inline-size: 480px;
      }

      .profile-page__list {
        margin: 0;
        display: flex;
        flex-direction: column;
        gap: var(--spacing-lg);
      }

      .profile-page__row {
        display: flex;
        flex-direction: column;
        gap: 2px;
      }

      .profile-page__row dd {
        margin: 0;
        font-size: var(--typography-body-small-font-size);
        color: var(--color-text-primary);
      }

      .profile-page__role {
        text-transform: capitalize;
      }
    `,
  ],
})
export class Profile {
  private readonly authService = inject(AuthService);

  protected readonly email = computed(() => this.authService.principal()?.email ?? null);
  protected readonly role = computed(() => this.authService.principal()?.role ?? '');
}
