import type { AbstractControl, ValidationErrors } from '@angular/forms';

/**
 * Like `Validators.required`, but also refuses whitespace-only text — the
 * API trims names and rejects blanks, so the form should say so first.
 * Reports the `required` key so existing "is required" messages apply.
 */
export function notBlank(control: AbstractControl): ValidationErrors | null {
  const value: unknown = control.value;
  return typeof value === 'string' && value.trim() === '' ? { required: true } : null;
}

/** Records that can be picked in a form: active, with a non-blank name. */
export function selectableByName<T extends { is_active: boolean; name: string }>(
  items: readonly T[],
): T[] {
  return items.filter((item) => item.is_active && item.name.trim() !== '');
}
