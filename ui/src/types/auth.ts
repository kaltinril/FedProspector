/** Login request matching C# LoginRequest */
export interface LoginRequest {
  email: string;
  password: string;
}

/** Register request matching C# RegisterRequest */
export interface RegisterRequest {
  username: string;
  email: string;
  password: string;
  displayName: string;
  inviteCode: string;
}

/** Change password request matching C# ChangePasswordRequest */
export interface ChangePasswordRequest {
  currentPassword: string;
  newPassword: string;
}

/** Update profile request matching C# UpdateProfileRequest */
export interface UpdateProfileRequest {
  displayName?: string | null;
  email?: string | null;
  currentPassword?: string | null;
}

/** Auth result matching C# AuthResult */
export interface AuthResult {
  success: boolean;
  token?: string | null;
  refreshToken?: string | null;
  error?: string | null;
  userId?: number | null;
  userName?: string | null;
  expiresAt?: string | null;
  forcePasswordChange: boolean;
}

/** User profile matching C# UserProfileDto */
export interface UserProfileDto {
  userId: number;
  username: string;
  displayName: string;
  email?: string | null;
  role: string;
  isOrgAdmin: boolean;
  isSystemAdmin: boolean;
  lastLoginAt?: string | null;
  createdAt?: string | null;
  forcePasswordChange: boolean;
}
