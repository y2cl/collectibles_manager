import client from './client';
import type { Owner, Profile, OwnerPreferences } from '../types/owner';

export const ownersApi = {
  list: () =>
    client.get<Owner[]>('/api/owners').then((r) => r.data),

  create: (name: string) =>
    client.post<Owner>('/api/owners', { name }).then((r) => r.data),

  listProfiles: (owner_id: string) =>
    client.get<Profile[]>(`/api/owners/${owner_id}/profiles`).then((r) => r.data),

  createProfile: (owner_id: string, name: string) =>
    client.post<Profile>(`/api/owners/${owner_id}/profiles`, { name }).then((r) => r.data),

  updateOwner: (owner_id: string, label: string) =>
    client.put<Owner>(`/api/owners/${owner_id}`, { label }).then((r) => r.data),

  deleteOwner: (owner_id: string) =>
    client.delete(`/api/owners/${owner_id}`).then((r) => r.data),

  updateProfile: (owner_id: string, profile_id: string, new_profile_id: string) =>
    client.put<Profile>(`/api/owners/${owner_id}/profiles/${profile_id}`, { profile_id: new_profile_id }).then((r) => r.data),

  deleteProfile: (owner_id: string, profile_id: string) =>
    client.delete(`/api/owners/${owner_id}/profiles/${profile_id}`).then((r) => r.data),

  getPreferences: () =>
    client.get<OwnerPreferences>('/api/owners/preferences').then((r) => r.data),

  updatePreferences: (payload: Partial<OwnerPreferences>) =>
    client.put<OwnerPreferences>('/api/owners/preferences', payload).then((r) => r.data),
};
