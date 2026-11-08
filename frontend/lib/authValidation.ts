/** Form checks for sign in / sign up. Pure functions so they can be tested without a browser. Author: Saamarth Attray */

export interface FieldErrors {
  name?: string;
  email?: string;
  password?: string;
}

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

export const MIN_PASSWORD = 8;

export function validateEmail(value: string): string | undefined {
  const email = value.trim();
  if (!email) return "Enter your email address.";
  if (!EMAIL.test(email)) return "That email doesn't look right. Use the form name@example.com.";
  return undefined;
}

export function validateSignIn(input: { email: string; password: string }): FieldErrors {
  const errors: FieldErrors = {};
  const email = validateEmail(input.email);
  if (email) errors.email = email;
  if (!input.password) errors.password = "Enter your password.";
  return errors;
}

export function validateSignUp(input: { name: string; email: string; password: string }): FieldErrors {
  const errors: FieldErrors = {};
  if (input.name.trim().length < 2) errors.name = "Enter your name so we know what to call you.";
  const email = validateEmail(input.email);
  if (email) errors.email = email;
  if (input.password.length < MIN_PASSWORD) errors.password = `Use at least ${MIN_PASSWORD} characters.`;
  return errors;
}

/** 0 (nothing typed) to 4. Length matters most; mixing character types helps. */
export function passwordStrength(password: string): { score: 0 | 1 | 2 | 3 | 4; hint: string } {
  if (!password) return { score: 0, hint: `Use at least ${MIN_PASSWORD} characters.` };
  let score = 0;
  if (password.length >= MIN_PASSWORD) score++;
  if (password.length >= 12) score++;
  if (/[a-z]/.test(password) && /[A-Z]/.test(password)) score++;
  if (/\d/.test(password) || /[^A-Za-z0-9]/.test(password)) score++;
  if (password.length < MIN_PASSWORD) return { score: 1, hint: `${MIN_PASSWORD - password.length} more characters to go.` };
  const hints = ["", "Add a number or symbol to make it stronger.", "Getting there. A longer password is stronger.", "Good.", "Strong."];
  return { score: Math.min(4, score) as 1 | 2 | 3 | 4, hint: hints[Math.min(4, score)] };
}