import { useEffect } from 'react';
import { useAppearanceStore } from '../store/appearanceStore';

/**
 * Reads the appearance store and writes each value as a CSS custom property
 * onto document.documentElement so every CSS var() in the app updates instantly.
 * Call this once in Layout so it runs on every render while the app is mounted.
 */
export function useTheme() {
  const s = useAppearanceStore();

  useEffect(() => {
    const root = document.documentElement;
    root.style.setProperty('--font-family', s.fontFamily);
    root.style.setProperty('--bg', s.bg);
    root.style.setProperty('--text', s.text);
    root.style.setProperty('--text-muted', s.textMuted);
    root.style.setProperty('--border', s.border);
    root.style.setProperty('--accent', s.accent);
    root.style.setProperty('--accent-hover', s.accentHover);
    root.style.setProperty('--sidebar-width', `${s.sidebarWidth}px`);
    root.style.setProperty('--sidebar-bg', s.sidebarBg);
    root.style.setProperty('--sidebar-border', s.sidebarBorder);
    root.style.setProperty('--sidebar-text', s.sidebarText);
    root.style.setProperty('--sidebar-text-muted', s.sidebarTextMuted);
    root.style.setProperty('--sidebar-hover-bg', s.sidebarHoverBg);
    root.style.setProperty('--sidebar-active-bg', s.sidebarActiveBg);
    root.style.setProperty('--sidebar-active-text', s.sidebarActiveText);
    root.style.setProperty('--surface', s.surface);
    root.style.setProperty('--surface-alt', s.surfaceAlt);
  }, [
    s.fontFamily, s.bg, s.text, s.textMuted, s.border,
    s.accent, s.accentHover, s.sidebarWidth, s.sidebarBg,
    s.sidebarBorder, s.sidebarText, s.sidebarTextMuted,
    s.sidebarHoverBg, s.sidebarActiveBg, s.sidebarActiveText,
    s.surface, s.surfaceAlt,
  ]);
}
