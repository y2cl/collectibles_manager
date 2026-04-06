import client from './client';
import type { ImportCsvResponse } from '../types/settings';

export const exportApi = {
  importCsv: (file: File, owner_id: string, profile_id = 'default', columnMapping?: Record<string, string>, game?: string) => {
    const form = new FormData();
    form.append('file', file);
    form.append('owner_id', owner_id);
    form.append('profile_id', profile_id);
    if (columnMapping && Object.keys(columnMapping).length > 0) {
      form.append('column_mapping', JSON.stringify(columnMapping));
    }
    if (game) {
      form.append('game', game);
    }
    return client.post<ImportCsvResponse>('/api/import/csv', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then((r) => r.data);
  },

  getAmbiguities: (owner_id: string, profile_id = 'default') =>
    client.get(`/api/import/ambiguities/${owner_id}`, { params: { profile_id } }).then((r) => r.data),

  clearAmbiguities: (owner_id: string, profile_id = 'default') =>
    client.delete(`/api/import/ambiguities/${owner_id}`, { params: { profile_id } }).then((r) => r.data),

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

  getImportHistory: (owner_id: string, profile_id = 'default') =>
    client.get(`/api/import/history/${owner_id}`, { params: { profile_id } }).then((r) => r.data),

  deleteImport: (owner_id: string, history_id: number) =>
    client.delete(`/api/import/history/${owner_id}/${history_id}`).then((r) => r.data),

  importFileUrl: (owner_id: string, history_id: number) =>
    `/api/import/history/${owner_id}/${history_id}/file`,
};
