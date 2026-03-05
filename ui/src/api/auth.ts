import apiClient from './client';
import type { LoginRequest, RegisterRequest, ChangePasswordRequest, UpdateProfileRequest, AuthResult, UserProfileDto } from '@/types/auth';

export function login(data: LoginRequest): Promise<AuthResult> {
  return apiClient.post('/auth/login', data).then((r) => r.data);
}

export function register(data: RegisterRequest): Promise<AuthResult> {
  return apiClient.post('/auth/register', data).then((r) => r.data);
}

export function logout(): Promise<void> {
  return apiClient.post('/auth/logout').then((r) => r.data);
}

export function me(): Promise<UserProfileDto> {
  return apiClient.get('/auth/me').then((r) => r.data);
}

export function refresh(): Promise<void> {
  return apiClient.post('/auth/refresh').then((r) => r.data);
}

export function changePassword(data: ChangePasswordRequest): Promise<void> {
  return apiClient.post('/auth/change-password', data).then((r) => r.data);
}

export function updateProfile(data: UpdateProfileRequest): Promise<UserProfileDto> {
  return apiClient.patch('/auth/me', data).then((r) => r.data);
}
