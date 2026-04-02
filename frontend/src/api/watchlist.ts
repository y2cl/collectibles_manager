import client from './client';
import type { WatchlistItem } from '../types/card';

export const watchlistApi = {
  list: (params: { owner_id: string; profile_id?: string }) =>
    client.get<WatchlistItem[]>('/api/watchlist', { params }).then((r) => r.data),

  add: (payload: Partial<WatchlistItem> & { owner_id: string }) =>
    client.post<WatchlistItem>('/api/watchlist', payload).then((r) => r.data),

  update: (id: number, payload: { quantity?: number; target_price?: number; notes?: string; variant?: string }) =>
    client.patch<WatchlistItem>(`/api/watchlist/${id}`, payload).then((r) => r.data),

  delete: (id: number) =>
    client.delete(`/api/watchlist/${id}`).then((r) => r.data),
};
