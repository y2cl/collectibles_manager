import client from './client';
import type { AppSettings, ApiSourceConfig } from '../types/settings';

export const settingsApi = {
  get: () =>
    client.get<AppSettings>('/api/settings').then((r) => r.data),

  update: (payload: Partial<AppSettings>) =>
    client.put<AppSettings>('/api/settings', payload).then((r) => r.data),

  getApiSources: () =>
    client.get<ApiSourceConfig[]>('/api/settings/api-sources').then((r) => r.data),

  updateApiSources: (updates: Array<{ source_id: string; enabled: boolean; ebay_env?: string; pokemontcg_api?: string }>) =>
    client.put<ApiSourceConfig[]>('/api/settings/api-sources', updates).then((r) => r.data),
};
