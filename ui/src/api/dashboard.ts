import apiClient from './client';
import type { DashboardDto } from '@/types/api';

export function getDashboard(): Promise<DashboardDto> {
  return apiClient.get('/dashboard').then((r) => r.data);
}
