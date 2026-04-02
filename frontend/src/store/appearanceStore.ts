import { create } from 'zustand';
import { persist } from 'zustand/middleware';

export interface AppearanceState {
  // Typography
  fontFamily: string;
  // Page
  bg: string;
  text: string;
  textMuted: string;
  border: string;
  // Accent
  accent: string;
  accentHover: string;
  // Sidebar
  sidebarWidth: number;
  sidebarBg: string;
  sidebarBorder: string;
  sidebarText: string;
  sidebarTextMuted: string;
  sidebarHoverBg: string;
  sidebarActiveBg: string;
  sidebarActiveText: string;
  // Surfaces
  surface: string;
  surfaceAlt: string;
}

interface AppearanceStore extends AppearanceState {
  set: (patch: Partial<AppearanceState>) => void;
  reset: () => void;
}

export const DEFAULTS: AppearanceState = {
  fontFamily: 'Inter, system-ui, Avenir, Helvetica, Arial, sans-serif',
  bg: '#f0f2fa',
  text: '#1a1a2e',
  textMuted: '#666666',
  border: '#e0e4ef',
  accent: '#4c6ef5',
  accentHover: '#3b5bdb',
  sidebarWidth: 220,
  sidebarBg: '#1a1a2e',
  sidebarBorder: '#2d2d4e',
  sidebarText: '#c0c0d8',
  sidebarTextMuted: '#888888',
  sidebarHoverBg: '#2d2d4e',
  sidebarActiveBg: '#3d3d6e',
  sidebarActiveText: '#ffffff',
  surface: '#ffffff',
  surfaceAlt: '#f5f7fb',
};

export const FONT_OPTIONS = [
  { label: 'Inter (default)', value: 'Inter, system-ui, Avenir, Helvetica, Arial, sans-serif' },
  { label: 'System UI', value: 'system-ui, -apple-system, sans-serif' },
  { label: 'Georgia (serif)', value: 'Georgia, "Times New Roman", serif' },
  { label: 'Menlo (monospace)', value: 'Menlo, Monaco, "Courier New", monospace' },
  { label: 'Trebuchet MS', value: '"Trebuchet MS", Tahoma, Geneva, sans-serif' },
];

export const PRESETS: Record<string, Partial<AppearanceState>> = {
  'Dark Navy (default)': {},  // empty = pure defaults
  'Midnight Dark': {
    bg: '#0f0f0f',
    text: '#e8e8e8',
    textMuted: '#999',
    border: '#2a2a2a',
    surface: '#1a1a1a',
    surfaceAlt: '#222',
    sidebarBg: '#111',
    sidebarBorder: '#222',
    sidebarText: '#bbb',
    sidebarTextMuted: '#666',
    sidebarHoverBg: '#1e1e1e',
    sidebarActiveBg: '#2a2a2a',
    accent: '#7c3aed',
    accentHover: '#6d28d9',
  },
  'Light & Clean': {
    bg: '#f8f9fa',
    text: '#212529',
    textMuted: '#6c757d',
    border: '#dee2e6',
    surface: '#ffffff',
    surfaceAlt: '#f1f3f5',
    sidebarBg: '#343a40',
    sidebarBorder: '#495057',
    sidebarText: '#ced4da',
    sidebarTextMuted: '#adb5bd',
    sidebarHoverBg: '#495057',
    sidebarActiveBg: '#0d6efd',
    sidebarActiveText: '#ffffff',
    accent: '#0d6efd',
    accentHover: '#0a58ca',
  },
  'Forest Green': {
    bg: '#f0f4f0',
    text: '#1b2e1b',
    textMuted: '#557a55',
    border: '#c8dcc8',
    surface: '#ffffff',
    surfaceAlt: '#eaf2ea',
    sidebarBg: '#1b3a1b',
    sidebarBorder: '#2d5a2d',
    sidebarText: '#b8d4b8',
    sidebarTextMuted: '#7a9c7a',
    sidebarHoverBg: '#2d5a2d',
    sidebarActiveBg: '#3a7a3a',
    sidebarActiveText: '#ffffff',
    accent: '#2d8a2d',
    accentHover: '#227022',
  },
  'Warm Sunset': {
    bg: '#fdf6f0',
    text: '#2d1b0e',
    textMuted: '#8b5e3c',
    border: '#f0d9c8',
    surface: '#ffffff',
    surfaceAlt: '#fdf0e8',
    sidebarBg: '#2d1b0e',
    sidebarBorder: '#4a2e18',
    sidebarText: '#f0c8a0',
    sidebarTextMuted: '#a07050',
    sidebarHoverBg: '#4a2e18',
    sidebarActiveBg: '#c2440c',
    sidebarActiveText: '#ffffff',
    accent: '#c2440c',
    accentHover: '#a03008',
  },
};

export const useAppearanceStore = create<AppearanceStore>()(
  persist(
    (set) => ({
      ...DEFAULTS,
      set: (patch) => set((s) => ({ ...s, ...patch })),
      reset: () => set(() => ({ ...DEFAULTS })),
    }),
    { name: 'collectibles-appearance' }
  )
);
