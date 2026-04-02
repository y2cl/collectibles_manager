import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { collectionApi } from '../api/collection';
import type { CardAddRequest } from '../types/card';

export function useCollection(ownerId: string | null, profileId: string, game?: string) {
  return useQuery({
    queryKey: ['collection', ownerId, profileId, game],
    queryFn: () => collectionApi.list({ owner_id: ownerId!, profile_id: profileId, game }),
    enabled: !!ownerId,
  });
}

export function useAddCard() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: CardAddRequest) => collectionApi.addCard(payload),
    onSuccess: (_data, vars) => {
      qc.invalidateQueries({ queryKey: ['collection', vars.owner_id] });
    },
  });
}

export function useUpdateCard() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Record<string, unknown> }) =>
      collectionApi.updateCard(id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['collection'] });
    },
  });
}

export function useDeleteCard() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: number) => collectionApi.deleteCard(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['collection'] });
    },
  });
}

export function useBulkDeleteCards() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ owner_id, profile_id, card_ids }: { owner_id: string; profile_id: string; card_ids: number[] }) =>
      collectionApi.bulkDelete(owner_id, profile_id, card_ids),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['collection'] });
    },
  });
}
