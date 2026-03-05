import apiClient from './client';
import type { NotificationListParams, NotificationListResponse } from '@/types/api';

export function listNotifications(
  params: NotificationListParams,
): Promise<NotificationListResponse> {
  return apiClient.get('/notifications', { params }).then((r) => r.data);
}

export function getUnreadCount(): Promise<{ count: number }> {
  return apiClient.get('/notifications/unread-count').then((r) => r.data);
}

export function markRead(id: number): Promise<void> {
  return apiClient.patch(`/notifications/${id}/read`).then((r) => r.data);
}

export function markAllRead(): Promise<void> {
  return apiClient.post('/notifications/mark-all-read').then((r) => r.data);
}
