import { ChangeDetectionStrategy, Component, OnInit, computed, inject, signal } from '@angular/core';
import { Router } from '@angular/router';
import { ButtonDirective } from 'primeng/button';
import {
  AuthService,
  AuthTokenStore,
  LicenseService,
  LicenseStatusStore,
  type LicenseLifecycleState,
} from '@lpg/shared/data-access';

/**
 * Full-screen hard gate — a shell-sibling route, same as `/login` (ADR-036),
 * so it renders with no sidebar/top-bar chrome. Reached via `licenseGuard`
 * when the tenant's license is `pending_activation`, `blocked`, or
 * `revoked`.
 *
 * Fetches its own fresh status on init rather than trusting
 * `LicenseStatusStore` alone — this page is reachable both via the guard
 * redirect (store already populated by the time this mounts) *and* via a
 * direct navigation or page reload (store may still be `null` or stale),
 * so it can't assume either path already did the fetch for it.
 */
@Component({
  selector: 'lpg-license-required',
  standalone: true,
  imports: [ButtonDirective],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <div class="license-required">
      <div class="license-required__content">
        <i class="pi pi-lock license-required__icon" aria-hidden="true"></i>

        @if (status(); as s) {
          @if (s === 'pending_activation') {
            <h1 class="license-required__title">License not yet activated</h1>
            <p class="license-required__desc">
              This tenant's license hasn't been activated yet.
              @if (canManageLicense()) {
                Enter your activation key to get started.
              } @else {
                Contact your agency administrator to get started.
              }
            </p>
          } @else {
            <h1 class="license-required__title">License expired</h1>
            <p class="license-required__desc">
              This tenant's license has expired.
              @if (canManageLicense()) {
                Renew it to restore access.
              } @else {
                Contact your agency administrator to renew it.
              }
            </p>
          }
        } @else {
          <h1 class="license-required__title">Checking license status…</h1>
        }

        <div class="license-required__actions">
          @if (canManageLicense()) {
            <button pButton type="button" (click)="goToActivation()">Manage license</button>
          }
          <button pButton type="button" severity="secondary" [loading]="checking()" (click)="recheck()">
            Check again
          </button>
          <button pButton type="button" severity="secondary" (click)="signOut()">Sign out</button>
        </div>
      </div>
    </div>
  `,
  styles: [
    `
      :host {
        display: block;
        min-block-size: 100vh;
      }

      .license-required {
        display: flex;
        align-items: center;
        justify-content: center;
        min-block-size: 100vh;
        padding: var(--spacing-lg);
        background: var(--color-surface-base);
      }

      .license-required__content {
        display: flex;
        flex-direction: column;
        align-items: center;
        text-align: center;
        gap: var(--spacing-sm);
        max-inline-size: 30rem;
      }

      .license-required__icon {
        font-size: 2.5rem;
        color: var(--color-text-secondary);
        margin-block-end: var(--spacing-sm);
      }

      .license-required__title {
        font-size: var(--typography-heading1-font-size);
        font-weight: var(--typography-heading1-font-weight);
        letter-spacing: -0.025em;
        margin: 0;
      }

      .license-required__desc {
        color: var(--color-text-secondary);
        font-size: var(--typography-body-font-size);
        margin: 0;
      }

      .license-required__actions {
        display: flex;
        flex-wrap: wrap;
        justify-content: center;
        gap: var(--spacing-sm);
        margin-block-start: var(--spacing-lg);
      }
    `,
  ],
})
export class LicenseRequired implements OnInit {
  private readonly authService = inject(AuthService);
  private readonly licenseService = inject(LicenseService);
  private readonly licenseStatusStore = inject(LicenseStatusStore);
  private readonly tokenStore = inject(AuthTokenStore);
  private readonly router = inject(Router);

  protected readonly checking = signal(false);
  protected readonly status = computed(() => this.licenseStatusStore.status()?.status ?? null);
  protected readonly canManageLicense = computed(() =>
    this.tokenStore.principal()?.permissions.has('license:manage_tenant') ?? false,
  );

  ngOnInit(): void {
    this.recheck();
  }

  protected goToActivation(): void {
    void this.router.navigateByUrl('/admin/license');
  }

  protected recheck(): void {
    this.checking.set(true);
    this.licenseService.getStatus().subscribe({
      next: (response) => {
        this.checking.set(false);
        this.licenseStatusStore.set({
          status: response.status as LicenseLifecycleState,
          planTier: response.plan_tier,
          keyPrefix: response.key_prefix,
          activatedAt: response.activated_at,
          expiresAt: response.expires_at,
          graceEndsAt: response.grace_ends_at,
        });
        if (response.status === 'active' || response.status === 'grace') {
          void this.router.navigateByUrl('/');
        }
      },
      error: () => this.checking.set(false),
    });
  }

  protected signOut(): void {
    this.authService.logout().subscribe(() => {
      void this.router.navigateByUrl('/login');
    });
  }
}
