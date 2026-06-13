/**
 * Auth Validators
 *
 * Email domain validation and password policy rules.
 * Used by Login form (email validation) and PasswordChange form (live checklist).
 * Password rules follow OWASP 2025 recommendations (min 12 chars).
 */

export interface PasswordRule {
  id: string;
  label: string;
  test: (password: string) => boolean;
}

/** Password rules matching UI-SPEC copywriting contract */
export const PASSWORD_RULES: PasswordRule[] = [
  { id: 'length', label: 'At least 12 characters', test: (password) => password.length >= 12 },
  { id: 'uppercase', label: 'One uppercase letter', test: (password) => /[A-Z]/.test(password) },
  { id: 'lowercase', label: 'One lowercase letter', test: (password) => /[a-z]/.test(password) },
  { id: 'digit', label: 'One digit', test: (password) => /\d/.test(password) },
  {
    id: 'special',
    label: 'One special character (!@#$%^&*)',
    test: (password) => /[!@#$%^&*()_+\-=[\]{};':"\\|,.<>/?]/.test(password),
  },
];

/** Check all password rules. Returns array of { rule, met } */
export function validatePassword(password: string): { rule: PasswordRule; met: boolean }[] {
  return PASSWORD_RULES.map((rule) => ({ rule, met: rule.test(password) }));
}

/** Check if all password rules pass */
export function isPasswordValid(password: string): boolean {
  return PASSWORD_RULES.every((rule) => rule.test(password));
}

/** Validate @wipro.com email domain */
export function validateEmail(email: string): string | null {
  const trimmed = email.trim().toLowerCase();
  if (!trimmed) return 'Email is required';
  if (!trimmed.endsWith('@wipro.com')) return 'Must be a @wipro.com email address';
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(trimmed)) return 'Invalid email format';
  return null;
}
