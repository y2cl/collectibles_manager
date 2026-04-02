import client from './client';
import type { CollectionResponse, CollectionCard, CardAddRequest } from '../types/card';

export const collectionApi = {
  list: (params: { owner_id: string; profile_id?: string; game?: string }) =>
    client.get<CollectionResponse>('/api/collection', { params }).then((r) => r.data),

  addCard: (payload: CardAddRequest) =>
    client.post<CollectionCard>('/api/collection/cards', payload).then((r) => r.data),

  updateCard: (id: number, payload: Partial<CollectionCard>) =>
    client.patch<CollectionCard>(`/api/collection/cards/${id}`, payload).then((r) => r.data),

  deleteCard: (id: number) =>
    client.delete(`/api/collection/cards/${id}`).then((r) => r.data),

  bulkDelete: (owner_id: string, profile_id: string, card_ids: number[]) =>
    client.delete('/api/collection/cards', { data: { owner_id, profile_id, card_ids } }).then((r) => r.data),

  stats: (owner_id: string, profile_id: string, game?: string) =>
    client.get('/api/stats', { params: { owner_id, profile_id, game } }).then((r) => r.data),
};
