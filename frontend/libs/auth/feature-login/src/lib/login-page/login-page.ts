import { ChangeDetectionStrategy, Component, inject, signal, viewChild } from '@angular/core';
import { NonNullableFormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { Router, RouterLink } from '@angular/router';
import { ButtonDirective } from 'primeng/button';
import { InputText } from 'primeng/inputtext';
import { InputPassword } from 'primeng/inputpassword';
import { Message } from 'primeng/message';
import { AuthService, type AppError } from '@lpg/shared/data-access';
import { FormFieldComponent } from '@lpg/shared/ui';
import { AuthShell } from '../auth-shell/auth-shell';

function isAppError(value: unknown): value is AppError {
  return typeof value === 'object' && value !== null && 'errorCode' in value;
}

function errorMessageFor(error: unknown): string {
  switch (isAppError(error) ? error.errorCode : null) {
    case 'INVALID_CREDENTIALS':
      return 'Incorrect email or password.';
    case 'ACCOUNT_LOCKED':
      return 'This account is temporarily locked after too many failed attempts. Try again later.';
    case 'TENANT_SUSPENDED':
      return 'This agency has been suspended. Contact support for assistance.';
    default:
      return 'Something went wrong signing in. Please try again.';
  }
}

/**
 * Staff password login — Dashboard users primarily authenticate this way
 * (OTP login is the Customer/Driver mobile path, `mobile/packages/auth`).
 *
 * First use of Reactive Forms in this codebase (`06-authentication-
 * authorization` PLAN, Frontend Patterns): validated, submit-disabled-while-
 * pending, server errors surfaced via `p-message` rather than a raw
 * `AppError` dump.
 */
@Component({
  selector: 'lpg-login-page',
  standalone: true,
  imports: [
    ReactiveFormsModule,
    RouterLink,
    ButtonDirective,
    InputText,
    InputPassword,
    Message,
    FormFieldComponent,
    AuthShell,
  ],
  changeDetection: ChangeDetectionStrategy.OnPush,
  template: `
    <lpg-auth-shell>
      <form [formGroup]="form" (ngSubmit)="submit()" novalidate>
        <div class="login-card__header">
          <h1 class="login-card__title">Sign in</h1>
          <p class="login-card__lede">Welcome back. Enter your details to continue.</p>
        </div>

        @if (errorMessage(); as message) {
          <p-message severity="error">{{ message }}</p-message>
        }

        <div class="login-card__body">
          <lpg-form-field
            label="Email"
            for="login-email"
            [control]="form.controls.email"
            [messages]="{ required: 'Enter a valid email address.', email: 'Enter a valid email address.' }"
          >
            <input
              pInputText
              id="login-email"
              type="email"
              formControlName="email"
              autocomplete="username"
              class="login-card__input"
              [fluid]="true"
            />
          </lpg-form-field>

          <lpg-form-field
            label="Password"
            for="login-password"
            [control]="form.controls.password"
            [messages]="{ required: 'Password is required.', minlength: 'Password must be at least 12 characters.' }"
          >
            <div class="password-field">
              <input
                #passwordInput
                pInputPassword
                id="login-password"
                type="password"
                formControlName="password"
                autocomplete="current-password"
                class="login-card__input password-field__input"
                [fluid]="true"
              />
              <button
                type="button"
                class="password-field__toggle"
                tabindex="-1"
                (click)="togglePasswordVisibility()"
                [attr.aria-label]="passwordVisible() ? 'Hide password' : 'Show password'"
              >
                <i class="pi" [class.pi-eye]="!passwordVisible()" [class.pi-eye-slash]="passwordVisible()"></i>
              </button>
            </div>
          </lpg-form-field>
        </div>

        <div class="login-card__footer">
          <button pButton type="submit" [disabled]="submitting()" class="login-card__submit">
            {{ submitting() ? 'Signing in…' : 'Sign in' }}
          </button>
          <a class="login-card__forgot" routerLink="/login/forgot-password"
            >Forgot your password?</a
          >
        </div>
      </form>
    </lpg-auth-shell>
  `,
  styles: [
    `
      .login-card__header {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-xs);
        margin-block-end: var(--spacing-xl);
      }

      .login-card__title {
        margin: 0;
        font-size: var(--typography-display-font-size);
        font-weight: var(--typography-display-font-weight);
        letter-spacing: -0.02em;
        color: var(--color-text-primary);
      }

      .login-card__lede {
        margin: 0;
        color: var(--color-text-secondary);
        font-size: var(--typography-body-font-size);
      }

      p-message {
        display: block;
        margin-block-end: var(--spacing-lg);
      }

      .login-card__body {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-md);
      }

      .login-card__input {
        width: 100%;
      }

      .password-field {
        position: relative;
      }

      .password-field__input {
        padding-inline-end: 2.5rem;
      }

      .password-field__toggle {
        position: absolute;
        inset-inline-end: var(--spacing-sm);
        top: 50%;
        transform: translateY(-50%);
        display: inline-flex;
        align-items: center;
        justify-content: center;
        background: none;
        border: none;
        padding: 0;
        color: var(--color-text-secondary);
        cursor: pointer;
        z-index: 1;
      }

      .password-field__toggle:hover {
        color: var(--color-text-primary);
      }

      .login-card__footer {
        display: flex;
        flex-direction: column;
        gap: var(--spacing-md);
        margin-block-start: var(--spacing-xl);
      }

      .login-card__submit {
        width: 100%;
        transition: transform var(--motion-duration-micro) var(--motion-easing-standard);
      }

      .login-card__submit:active:not(:disabled) {
        transform: translateY(1px);
      }

      .login-card__forgot {
        align-self: center;
        color: var(--color-action-primary);
        font-size: var(--typography-body-small-font-size);
        text-decoration: none;
        font-weight: var(--typography-label-font-weight);
      }

      .login-card__forgot:hover {
        text-decoration: underline;
      }
    `,
  ],
})
export class LoginPage {
  private readonly formBuilder = inject(NonNullableFormBuilder);
  private readonly authService = inject(AuthService);
  private readonly router = inject(Router);

  protected readonly submitting = signal(false);
  protected readonly errorMessage = signal<string | null>(null);

  // `pInputPassword` is a bare directive with no `exportAs`, so a template
  // reference variable (`#passwordInput`) resolves to the native element —
  // `read: InputPassword` is what actually gets the directive instance
  // (and its `mask`/`toggleMask()` state) off that same element.
  private readonly passwordInput = viewChild('passwordInput', { read: InputPassword });

  protected readonly form = this.formBuilder.group({
    email: ['', [Validators.required, Validators.email]],
    password: ['', [Validators.required, Validators.minLength(12)]],
  });

  protected passwordVisible(): boolean {
    return this.passwordInput()?.mask() === false;
  }

  protected togglePasswordVisibility(): void {
    this.passwordInput()?.toggleMask();
  }

  protected submit(): void {
    if (this.submitting()) {
      return;
    }
    if (this.form.invalid) {
      this.form.markAllAsTouched();
      return;
    }

    this.submitting.set(true);
    this.errorMessage.set(null);
    const { email, password } = this.form.getRawValue();

    this.authService.login(email, password).subscribe({
      next: () => {
        // A genuine `super_admin` session has no tenant dashboard to land
        // on (D-01) — default it into the Platform Console instead. Anyone
        // else holding `ai:read` lands on the AI Command Center instead of
        // the Agency Overview dashboard, per the user's own request — it's
        // the page most of this feature's audience actually wants first.
        // Always this smart default now, never a preserved `redirectTo` —
        // `authGuard` deliberately stopped setting one (see its own
        // docstring): it can't tell "session just expired mid-use" apart
        // from "never authenticated, deep link", and bouncing back to
        // whatever page triggered a forced re-login was the wrong default
        // for the former.
        const principal = this.authService.principal();
        const isPlatformSession = principal?.role === 'super_admin';
        const isAiEligible = !isPlatformSession && !!principal?.permissions.has('ai:read');
        const defaultRoute = isPlatformSession ? '/platform' : isAiEligible ? '/ai-assistant' : '/';
        void this.router.navigateByUrl(defaultRoute);
      },
      error: (error: unknown) => {
        this.submitting.set(false);
        this.errorMessage.set(errorMessageFor(error));
      },
    });
  }
}
