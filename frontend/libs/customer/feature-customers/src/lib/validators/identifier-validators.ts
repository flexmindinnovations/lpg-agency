import type { AbstractControl, ValidationErrors, ValidatorFn } from '@angular/forms';

/**
 * Client-side mirrors of the server's identifier rules
 * (`backend/src/lpg/domain/customer/identifiers.py`), so staff see the
 * problem while typing. The server stays the authority.
 */

const VERHOEFF_D = [
  [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
  [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
  [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
  [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
  [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
  [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
  [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
  [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
  [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
  [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
];
const VERHOEFF_P = [
  [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
  [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
  [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
  [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
  [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
  [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
  [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
  [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
];

export function verhoeffIsValid(digits: string): boolean {
  let check = 0;
  [...digits].reverse().forEach((char, position) => {
    check = VERHOEFF_D[check][VERHOEFF_P[position % 8][Number(char)]];
  });
  return check === 0;
}

/** Separators people type in document numbers. */
export function compactIdentifier(value: string): string {
  return value.replace(/[\s\-/]/g, '').toUpperCase();
}

export type KycDocType = 'aadhaar' | 'pan' | 'voter_id' | 'driving_license' | 'passport';

/** Narrows any value (OCR output, a saved draft) to a KYC type the server accepts. */
export function asKycDocType(value: unknown, fallback: KycDocType = 'aadhaar'): KycDocType {
  return typeof value === 'string' && value in KYC_DOC_TYPES ? (value as KycDocType) : fallback;
}

const KYC_DOC_TYPES: Record<KycDocType, true> = {
  aadhaar: true,
  pan: true,
  voter_id: true,
  driving_license: true,
  passport: true,
};

const KYC_RULES: Record<KycDocType, { pattern: RegExp; message: string }> = {
  aadhaar: { pattern: /^[2-9]\d{11}$/, message: 'Enter a valid 12-digit Aadhaar number.' },
  pan: {
    pattern: /^[A-Z]{3}[ABCFGHJLPT][A-Z]\d{4}[A-Z]$/,
    message: 'Enter a valid PAN, 10 characters like ABCPE1234F.',
  },
  voter_id: {
    pattern: /^[A-Z]{3}\d{7}$/,
    message: 'Enter a valid Voter ID: 3 letters followed by 7 digits.',
  },
  driving_license: {
    pattern: /^[A-Z]{2}\d{2}[A-Z0-9]{9,13}$/,
    message: 'Enter a valid driving licence number, like MH12 20110012345.',
  },
  passport: {
    pattern: /^[A-Z]\d{7}$/,
    message: 'Enter a valid passport number: 1 letter followed by 7 digits.',
  },
};

/** The error message for `number` as a `docType` document, or `null` when valid. */
export function kycNumberError(docType: string, number: string): string | null {
  const rule = KYC_RULES[docType as KycDocType];
  if (!rule || !number.trim()) return null;
  const value = compactIdentifier(number);
  if (!rule.pattern.test(value)) return rule.message;
  if (docType === 'aadhaar' && !verhoeffIsValid(value)) return rule.message;
  return null;
}

/** Validates `document_number` against the sibling `doc_type` control. */
export function kycNumberValidator(docTypeOf: () => string): ValidatorFn {
  return (control: AbstractControl): ValidationErrors | null => {
    const message = kycNumberError(docTypeOf(), String(control.value ?? ''));
    return message ? { kycNumber: message } : null;
  };
}

const GSTIN_PATTERN = /^(\d{2})[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$/;
const GSTIN_ALPHABET = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';

export function gstinIsValid(raw: string): boolean {
  const gstin = compactIdentifier(raw);
  const match = GSTIN_PATTERN.exec(gstin);
  if (!match) return false;
  const state = Number(match[1]);
  if (state < 1 || state > 38) return false;
  let total = 0;
  for (let i = 0; i < 14; i++) {
    const product = GSTIN_ALPHABET.indexOf(gstin[i]) * (i % 2 ? 2 : 1);
    total += Math.floor(product / 36) + (product % 36);
  }
  return GSTIN_ALPHABET[(36 - (total % 36)) % 36] === gstin[14];
}

/** Optional GSTIN: empty passes, anything else must be a real GSTIN. */
export const gstinValidator: ValidatorFn = (control) => {
  const value = String(control.value ?? '').trim();
  return value && !gstinIsValid(value) ? { gstin: true } : null;
};

/** 6-digit PIN code that does not start with 0. */
export const PINCODE_PATTERN = /^[1-9]\d{5}$/;

/** A calendar date as the API's `YYYY-MM-DD`, in the user's own time zone. */
export function toIsoDate(date: Date): string {
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${date.getFullYear()}-${month}-${day}`;
}

/**
 * Date inputs on customer screens show dd/mm/yyyy (DO-08). No shared
 * date-input format exists in `@lpg/shared/ui` yet, so it is kept here.
 */
export const DATE_INPUT_FORMAT = 'dd/mm/yy';
export const DATE_INPUT_PLACEHOLDER = 'dd/mm/yyyy';
