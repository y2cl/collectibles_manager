import client from './client';
import type { ImportCsvResponse } from '../types/settings';

export const exportApi = {
  importCsv: (file: File, owner_id: string, profile_id = 'default') => {
    const form = new FormData();
    form.append('file', file);
    form.append('owner_id', owner_id);
    form.append('profile_id', profile_id);
    return client.post<ImportCsvResponse>('/api/import/csv', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then((r) => r.data);
  },

  getAmbiguities: (owner_id: string, profile_id = 'default') =>
    client.get(`/api/import/ambiguities/${owner_id}`, { params: { profile_id } }).then((r) => r.data),

  resolveAmbiguities: (owner_id: string, profile_id: string, resolutions: unknown[]) =>
    client.post('/api/import/resolve-ambiguities', { owner_id, profile_id, resolutions }).then((r) => r.data),

  exportCsvUrl: (owner_id: string, profile_id: string, game?: string) => {
    const params = new URLSearchParams({ owner_id, profile_id });
    if (game) params.set('game', game);
    return `/api/export/csv?${params}`;
  },

  exportZipUrl: (owner_id: string) =>
    `/api/export/zip?owner_id=${owner_id}`,

  triggerBackup: (owner_id: string, retention = 5) =>
    client.post('/api/backup', { owner_id, retention }).then((r) => r.data),
};
