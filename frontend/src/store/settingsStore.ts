import { create } from 'zustand';
import { persist } from 'zustand/middleware';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8002';

export type SortOption = 'default' | 'name' | 'set' | 'year';

interface UiSettings {
  viewMode: 'grid' | 'list';
  imageWidth: number;
  compactMode: boolean;
  // Search preferences (loaded from backend)
  cardsPerRow: number;
  sortBy: SortOption;
  searchPrefsLoaded: boolean;
  // Actions
  setViewMode: (mode: 'grid' | 'list') => void;
  setImageWidth: (n: number) => void;
  setCompactMode: (v: boolean) => void;
  setCardsPerRow: (n: number) => void;
  setSortBy: (sort: SortOption) => void;
  fetchSearchPrefs: () => Promise<void>;
  saveSearchPrefs: () => Promise<void>;
}

// Client-side only settings (persisted to localStorage)
const clientSettings = create<{
  viewMode: 'grid' | 'list';
  imageWidth: number;
  compactMode: boolean;
  setViewMode: (mode: 'grid' | 'list') => void;
  setImageWidth: (n: number) => void;
  setCompactMode: (v: boolean) => void;
}>()(
  persist(
    (set) => ({
      viewMode: 'grid',
      imageWidth: 200,
      compactMode: false,
      setViewMode: (mode) => set({ viewMode: mode }),
      setImageWidth: (n) => set({ imageWidth: n }),
      setCompactMode: (v) => set({ compactMode: v }),
    }),
    { name: 'collectibles-ui-settings' }
  )
);

// Main settings store combining client and server state
export const useSettingsStore = create<UiSettings>((set, get) => ({
  // Initial values
  viewMode: 'grid',
  imageWidth: 200,
  compactMode: false,
  cardsPerRow: 4,
  sortBy: 'default',
  searchPrefsLoaded: false,

  // Client-side actions (delegate to clientSettings)
  setViewMode: (mode) => {
    clientSettings.getState().setViewMode(mode);
    set({ viewMode: mode });
  },
  setImageWidth: (n) => {
    clientSettings.getState().setImageWidth(n);
    set({ imageWidth: n });
  },
  setCompactMode: (v) => {
    clientSettings.getState().setCompactMode(v);
    set({ compactMode: v });
  },

  // Server-side actions
  setCardsPerRow: (n) => set({ cardsPerRow: n }),
  setSortBy: (sort) => set({ sortBy: sort }),

  // Fetch search preferences from backend
  fetchSearchPrefs: async () => {
    try {
      const res = await fetch(`${API_BASE}/api/settings`);
      if (!res.ok) throw new Error('Failed to fetch settings');
      const data = await res.json();
      set({
        cardsPerRow: data.search_cards_per_row ?? 4,
        sortBy: (data.search_sort_by as SortOption) ?? 'default',
        searchPrefsLoaded: true,
      });
    } catch (err) {
      console.error('Failed to load search preferences:', err);
      // Keep defaults on error
      set({ searchPrefsLoaded: true });
    }
  },

  // Save search preferences to backend
  saveSearchPrefs: async () => {
    const { cardsPerRow, sortBy } = get();
    try {
      const res = await fetch(`${API_BASE}/api/settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          search_cards_per_row: cardsPerRow,
          search_sort_by: sortBy,
        }),
      });
      if (!res.ok) throw new Error('Failed to save settings');
    } catch (err) {
      console.error('Failed to save search preferences:', err);
      throw err;
    }
  },
}));

// Initialize client-side settings from localStorage on load
clientSettings.subscribe((state) => {
  useSettingsStore.setState({
    viewMode: state.viewMode,
    imageWidth: state.imageWidth,
    compactMode: state.compactMode,
  });
});

// Trigger initial load from localStorage
delete (clientSettings as unknown as { subscribe?: unknown }).subscribe;
const initialClient = clientSettings.getState();
useSettingsStore.setState({
  viewMode: initialClient.viewMode,
  imageWidth: initialClient.imageWidth,
  compactMode: initialClient.compactMode,
});
