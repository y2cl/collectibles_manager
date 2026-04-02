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

export function useUpdateOwner() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ owner_id, label }: { owner_id: string; label: string }) =>
      ownersApi.updateOwner(owner_id, label),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['owners'] });
    },
  });
}

export function useDeleteOwner() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (owner_id: string) => ownersApi.deleteOwner(owner_id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['owners'] });
    },
  });
}

export function useUpdateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ owner_id, profile_id, new_profile_id }: { owner_id: string; profile_id: string; new_profile_id: string }) =>
      ownersApi.updateProfile(owner_id, profile_id, new_profile_id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['owners'] });
      qc.invalidateQueries({ queryKey: ['collection'] });
    },
  });
}

export function useDeleteProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ owner_id, profile_id }: { owner_id: string; profile_id: string }) =>
      ownersApi.deleteProfile(owner_id, profile_id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['owners'] });
    },
  });
}
