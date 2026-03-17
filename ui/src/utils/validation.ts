/**
 * Shared form validation utilities.
 */

/**
 * Check whether a password meets complexity requirements:
 * at least 8 chars, one uppercase, one lowercase, one digit.
 */
export function passwordMeetsRequirements(pw: string): boolean {
  return pw.length >= 8 && /[A-Z]/.test(pw) && /[a-z]/.test(pw) && /\d/.test(pw);
}

/**
 * Check whether a password-change form has valid inputs.
 * Used by both ProfilePage and ChangePasswordPage.
 */
export function isPasswordChangeValid(
  currentPassword: string,
  newPassword: string,
  confirmPassword: string,
): boolean {
  return (
    currentPassword.length > 0 &&
    passwordMeetsRequirements(newPassword) &&
    newPassword === confirmPassword
  );
}
