import {
  ChangeDetectionStrategy,
  Component,
  ElementRef,
  computed,
  inject,
  input,
  output,
  signal,
  viewChild,
} from '@angular/core';
import { RouterLink } from '@angular/router';
import { Avatar } from 'primeng/avatar';
import { Popover } from 'primeng/popover';
import { ThemeService, type ThemePreference } from '@lpg/shared/design-tokens';

export function displayNameFromEmail(email: string | null, fallback: string): string {
  if (!email) return fallback || 'Account';
  const localPart = email.split('@')[0];
  if (!localPart) return email;
  const words = localPart
    .split(/[._-]+/)
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1));
  return words.length > 0 ? words.join(' ') : email;
}

function initialsFor(displayName: string): string {
  const parts = displayName.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) return '?';
  const first = parts[0]?.[0] ?? '';
  const last = parts.length > 1 ? (parts[parts.length - 1]?.[0] ?? '') : '';
  return (first + last).toUpperCase();
}

@Component({
  selector: 'lpg-profile-menu',
  standalone: true,
  imports: [RouterLink, Avatar, Popover],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <button
      #triggerEl
      type="button"
      class="profile-menu__trigger"
      [class.profile-menu__trigger--collapsed]="collapsed()"
      aria-haspopup="menu"
      [attr.aria-expanded]="isOpen()"
      [attr.aria-label]="'Account menu for ' + displayName()"
      (click)="popover.toggle($event)"
    >
      <p-avatar [label]="initials()" shape="circle" styleClass="profile-menu__avatar" />
      @if (!collapsed()) {
        <span class="profile-menu__trigger-text">
          <span class="profile-menu__trigger-name">{{ displayName() }}</span>
          @if (email()) {
            <span class="profile-menu__trigger-email">{{ email() }}</span>
          }
        </span>
        <i class="pi pi-chevron-up profile-menu__trigger-chevron" aria-hidden="true"></i>
      }
    </button>

    <p-popover #popover (onShow)="isOpen.set(true)" (onHide)="onPopoverHide()">
      <div
        #menuEl
        class="profile-menu"
        role="menu"
        tabindex="-1"
        (keydown)="onMenuKeydown($event, menuEl)"
      >
        <div class="profile-menu__header">
          <p-avatar [label]="initials()" shape="circle" size="large" />
          <div class="profile-menu__header-text">
            <span class="profile-menu__header-name">{{ displayName() }}</span>
            @if (email()) {
              <span class="profile-menu__header-email">{{ email() }}</span>
            }
          </div>
        </div>

        <div class="profile-menu__divider" role="separator"></div>

        <a
          role="menuitem"
          class="profile-menu__item"
          [routerLink]="profileRoute()"
          (click)="popover.hide()"
        >
          <i class="pi pi-user" aria-hidden="true"></i>
          <span>My Profile</span>
        </a>

        <button
          role="menuitem"
          type="button"
          class="profile-menu__item"
          (click)="onAccountSettingsClick()"
        >
          <i class="pi pi-cog" aria-hidden="true"></i>
          <span>Account Settings</span>
        </button>
        @if (accountSettingsStubVisible()) {
          <p class="profile-menu__stub-note" aria-live="polite">
            Account settings are coming soon.
          </p>
        }

        <div class="profile-menu__divider" role="separator"></div>
        <p class="profile-menu__section-label">Theme</p>
        @for (option of themeOptions; track option.value) {
          <button
            role="menuitemradio"
            type="button"
            class="profile-menu__item"
            [attr.aria-checked]="themePreference() === option.value"
            (click)="setTheme(option.value)"
          >
            <i [class]="option.icon" aria-hidden="true"></i>
            <span class="profile-menu__item-label">{{ option.label }}</span>
            @if (themePreference() === option.value) {
              <i class="pi pi-check profile-menu__item-check" aria-hidden="true"></i>
            }
          </button>
        }

        <div class="profile-menu__divider" role="separator"></div>

        <button
          role="menuitem"
          type="button"
          class="profile-menu__item profile-menu__item--danger"
          (click)="onSignOutClick()"
        >
          <i class="pi pi-sign-out" aria-hidden="true"></i>
          <span>Sign Out</span>
        </button>
      </div>
    </p-popover>
  `,
  styles: [
    `
      :host {
        display: block;
        inline-size: 100%;
      }

      .profile-menu__trigger {
        display: flex;
        align-items: center;
        gap: var(--spacing-sm);
        inline-size: 100%;
        margin-block-start: auto;
        padding: var(--spacing-sm);
        border: none;
        border-radius: var(--radius-md);
        background: transparent;
        color: var(--color-text-primary);
        cursor: pointer;
        text-align: start;
        transition: background-color var(--motion-duration-small)
          var(--motion-easing-standard);
      }

      .profile-menu__trigger--collapsed {
        justify-content: center;
      }

      .profile-menu__trigger:hover {
        background: var(--color-surface-overlay);
      }

      .profile-menu__trigger-text {
        display: flex;
        flex-direction: column;
        overflow: hidden;
        flex: 1;
        min-inline-size: 0;
      }

      .profile-menu__trigger-name {
        font-size: var(--typography-body-small-font-size);
        font-weight: var(--typography-label-font-weight);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .profile-menu__trigger-email {
        font-size: var(--typography-caption-font-size);
        color: var(--color-text-secondary);
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
      }

      .profile-menu__trigger-chevron {
        color: var(--color-text-secondary);
        font-size: 10px;
        flex-shrink: 0;
        opacity: 0.5;
      }

      /* ---- Popover Menu ---- */

      .profile-menu {
        inline-size: var(--component-profile-menu-width);
        padding: var(--spacing-xs);
        display: flex;
        flex-direction: column;
      }

      .profile-menu__header {
        display: flex;
        align-items: center;
        gap: var(--spacing-sm);
        padding: var(--spacing-sm);
      }

      .profile-menu__header-text {
        display: flex;
        flex-direction: column;
        overflow: hidden;
      }

      .profile-menu__header-name {
        font-weight: var(--typography-label-font-weight);
        font-size: var(--typography-body-small-font-size);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .profile-menu__header-email {
        font-size: var(--typography-caption-font-size);
        color: var(--color-text-secondary);
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }

      .profile-menu__item {
        display: flex;
        align-items: center;
        gap: var(--spacing-sm);
        inline-size: 100%;
        padding: 6px var(--spacing-sm);
        border: none;
        background: transparent;
        border-radius: var(--radius-md);
        color: var(--color-text-primary);
        text-decoration: none;
        font-size: var(--typography-body-small-font-size);
        cursor: pointer;
        transition: background-color var(--motion-duration-small)
          var(--motion-easing-standard);
      }

      .profile-menu__item:hover {
        background: var(--color-surface-overlay);
      }

      .profile-menu__item i {
        inline-size: 1.25rem;
        text-align: center;
        flex-shrink: 0;
        font-size: 13px;
        opacity: 0.6;
      }

      .profile-menu__item--danger {
        color: var(--color-status-danger);
      }

      .profile-menu__item--danger i {
        opacity: 0.8;
      }

      .profile-menu__item-label {
        flex: 1;
        text-align: start;
      }

      .profile-menu__item-check {
        color: var(--color-action-primary);
        opacity: 1 !important;
      }

      .profile-menu__section-label {
        margin: 0;
        padding: var(--spacing-xs) var(--spacing-sm);
        font-size: 11px;
        font-weight: var(--typography-label-font-weight);
        color: var(--color-text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.06em;
        opacity: 0.7;
      }

      .profile-menu__stub-note {
        margin: 0;
        padding: 0 var(--spacing-sm) var(--spacing-xs);
        font-size: var(--typography-caption-font-size);
        color: var(--color-text-secondary);
      }

      .profile-menu__divider {
        block-size: var(--border-width);
        background: var(--color-border-default);
        margin-block: var(--spacing-xs);
      }
    `,
  ],
})
export class ProfileMenuComponent {
  private readonly themeService = inject(ThemeService);

  readonly email = input<string | null>(null);
  readonly role = input('');
  readonly collapsed = input(false);
  readonly profileRoute = input('/profile');

  readonly signOut = output<void>();

  protected readonly displayName = computed(() => displayNameFromEmail(this.email(), this.role()));
  protected readonly initials = computed(() => initialsFor(this.displayName()));

  private static readonly THEME_ICONS: Record<ThemePreference, string> = {
    system: 'pi pi-desktop',
    light: 'pi pi-sun',
    dark: 'pi pi-moon',
    'high-contrast': 'pi pi-eye',
  };

  protected readonly themePreference = this.themeService.preference;
  protected readonly themeOptions: ReadonlyArray<{
    value: ThemePreference;
    label: string;
    icon: string;
  }> = (['system', ...this.themeService.availableThemes] as readonly ThemePreference[]).map(
    (value) => ({
      value,
      label:
        value === 'high-contrast'
          ? 'High contrast'
          : value.charAt(0).toUpperCase() + value.slice(1),
      icon: ProfileMenuComponent.THEME_ICONS[value],
    }),
  );

  protected readonly isOpen = signal(false);
  protected readonly accountSettingsStubVisible = signal(false);

  private readonly triggerEl = viewChild<ElementRef<HTMLButtonElement>>('triggerEl');

  protected onPopoverHide(): void {
    this.isOpen.set(false);
    this.accountSettingsStubVisible.set(false);
    this.triggerEl()?.nativeElement.focus();
  }

  protected onAccountSettingsClick(): void {
    this.accountSettingsStubVisible.set(true);
  }

  protected setTheme(preference: ThemePreference): void {
    this.themeService.setPreference(preference);
  }

  protected onSignOutClick(): void {
    this.signOut.emit();
  }

  protected onMenuKeydown(event: KeyboardEvent, menuEl: HTMLElement): void {
    if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return;
    event.preventDefault();
    const focusable = Array.from(
      menuEl.querySelectorAll<HTMLElement>(
        'a[role="menuitem"], button[role="menuitem"], button[role="menuitemradio"]',
      ),
    );
    if (focusable.length === 0) return;
    const currentIndex = focusable.indexOf(document.activeElement as HTMLElement);
    const nextIndex =
      event.key === 'ArrowDown'
        ? (currentIndex + 1) % focusable.length
        : (currentIndex - 1 + focusable.length) % focusable.length;
    focusable[nextIndex]?.focus();
  }
}
