import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ownersApi } from '../api/owners';

export function useOwners() {
  return useQuery({
    queryKey: ['owners'],
    queryFn: () => ownersApi.list(),
    staleTime: 30 * 1000,
  });
}

export function useOwnerPreferences() {
  return useQuery({
    queryKey: ['owner-preferences'],
    queryFn: () => ownersApi.getPreferences(),
  });
}

export function useCreateOwner() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (name: string) => ownersApi.create(name),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['owners'] });
    },
  });
}

export function useCreateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ owner_id, name }: { owner_id: string; name: string }) =>
      ownersApi.createProfile(owner_id, name),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['owners'] });
    },
  });
}
