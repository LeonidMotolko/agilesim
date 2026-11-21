export type FormErrors = Record<string, string>;

const EMAIL_PATTERN = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
export const MIN_PASSWORD_LENGTH = 10;
export const MAX_NAME_LENGTH = 60;

function checkEmail(email: string, errors: FormErrors): void {
  if (email.trim() === "") {
    errors.email = "Enter your email";
  } else if (!EMAIL_PATTERN.test(email.trim())) {
    errors.email = "Enter a valid email address";
  }
}

export function validateLogin(values: { email: string; password: string }): FormErrors {
  const errors: FormErrors = {};
  checkEmail(values.email, errors);
  if (values.password === "") {
    errors.password = "Enter your password";
  }
  return errors;
}

export function validateRegistration(values: {
  email: string;
  display_name: string;
  password: string;
}): FormErrors {
  const errors: FormErrors = {};
  checkEmail(values.email, errors);
  if (values.display_name.trim() === "") {
    errors.display_name = "Enter your name";
  } else if (values.display_name.trim().length > MAX_NAME_LENGTH) {
    errors.display_name = `Use at most ${MAX_NAME_LENGTH} characters`;
  }
  if (values.password.length < MIN_PASSWORD_LENGTH) {
    errors.password = `Use at least ${MIN_PASSWORD_LENGTH} characters`;
  }
  return errors;
}

/** One required name (session, team or player), at most 60 characters. */
export function validateName(value: string, label: string): string | undefined {
  const trimmed = value.trim();
  if (trimmed === "") {
    return `Enter the ${label}`;
  }
  if (trimmed.length > MAX_NAME_LENGTH) {
    return `Use at most ${MAX_NAME_LENGTH} characters`;
  }
  return undefined;
}

export function validateJoinCode(value: string): string | undefined {
  return /^[A-Za-z0-9]{6}$/.test(value.trim())
    ? undefined
    : "The join code has 6 letters or digits";
}
