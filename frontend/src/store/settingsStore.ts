import { create } from 'zustand';
import { persist } from 'zustand/middleware';

interface UiSettings {
  viewMode: 'grid' | 'list';
  cardsPerRow: number;
  imageWidth: number;
  compactMode: boolean;
  setViewMode: (mode: 'grid' | 'list') => void;
  setCardsPerRow: (n: number) => void;
  setImageWidth: (n: number) => void;
  setCompactMode: (v: boolean) => void;
}

export const useSettingsStore = create<UiSettings>()(
  persist(
    (set) => ({
      viewMode: 'grid',
      cardsPerRow: 4,
      imageWidth: 200,
      compactMode: false,
      setViewMode: (mode) => set({ viewMode: mode }),
      setCardsPerRow: (n) => set({ cardsPerRow: n }),
      setImageWidth: (n) => set({ imageWidth: n }),
      setCompactMode: (v) => set({ compactMode: v }),
    }),
    { name: 'collectibles-ui-settings' }
  )
);
