import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface OwnerState {
  currentOwnerId: string | null;
  currentProfileId: string;
  setOwner: (ownerId: string) => void;
  setProfile: (profileId: string) => void;
  reset: () => void;
}

export const useOwnerStore = create<OwnerState>()(
  persist(
    (set) => ({
      currentOwnerId: null,
      currentProfileId: 'default',
      setOwner: (ownerId) => set({ currentOwnerId: ownerId, currentProfileId: 'default' }),
      setProfile: (profileId) => set({ currentProfileId: profileId }),
      reset: () => set({ currentOwnerId: null, currentProfileId: 'default' }),
    }),
    { name: 'collectibles-owner' }
  )
);
