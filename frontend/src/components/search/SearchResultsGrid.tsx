import { useState, useMemo, useEffect } from 'react';
import CardResultCard from './CardResultCard';
import type { CardResult } from '../../types/card';
import { useSettingsStore, type SortOption } from '../../store/settingsStore';

/**
 * Returns true if a card belongs to a promo / token / memorabilia set.
 * These are sorted to the end of results.
 */
function isPromoSet(card: CardResult): boolean {
  const name = (card.set_name ?? '').toLowerCase();
  const code = (card.set_code ?? '').toLowerCase();

  if (name.includes('promo') || name.includes('token') || name.includes('memorabilia')) return true;
  // MTG: promo set codes start with 'p' (e.g. ptla, plist, parl3) but we
  // guard against common non-promo sets that coincidentally start with 'p'.
  if (/^p[a-z0-9]{2,}/.test(code) && !['por', 'pcy', 'ptk'].includes(code)) return true;

  return false;
}

function sortCards(cards: CardResult[], sortBy: SortOption): CardResult[] {
  return [...cards].sort((a, b) => {
    // Sort by selected option first
    if (sortBy === 'name') {
      return (a.name ?? '').localeCompare(b.name ?? '');
    }
    if (sortBy === 'set') {
      const setDiff = (a.set_name ?? '').localeCompare(b.set_name ?? '');
      if (setDiff !== 0) return setDiff;
      return (a.name ?? '').localeCompare(b.name ?? '');
    }
    if (sortBy === 'year') {
      const yearA = parseInt(a.year ?? '0', 10) || 0;
      const yearB = parseInt(b.year ?? '0', 10) || 0;
      if (yearA !== yearB) return yearA - yearB;
      return (a.name ?? '').localeCompare(b.name ?? '');
    }

    // Default sort: promo sets last, then by set name, then name, then number
    const aPromo = isPromoSet(a) ? 1 : 0;
    const bPromo = isPromoSet(b) ? 1 : 0;
    if (aPromo !== bPromo) return aPromo - bPromo;

    const setDiff = (a.set_name ?? '').localeCompare(b.set_name ?? '');
    if (setDiff !== 0) return setDiff;

    const nameDiff = (a.name ?? '').localeCompare(b.name ?? '');
    if (nameDiff !== 0) return nameDiff;

    const aNum = a.card_number ?? '';
    const bNum = b.card_number ?? '';
    const aInt = parseInt(aNum, 10);
    const bInt = parseInt(bNum, 10);
    if (!isNaN(aInt) && !isNaN(bInt)) return aInt - bInt;
    return aNum.localeCompare(bNum);
  });
}

interface Props {
  cards: CardResult[];
  source?: string;
  total?: number;
  loading?: boolean;
  imageWidth?: number;
  onRefreshFromApi?: () => Promise<unknown>;
}

export default function SearchResultsGrid({
  cards, source, total, loading, imageWidth = 160, onRefreshFromApi,
}: Props) {
  const settings = useSettingsStore();
  const [refreshing, setRefreshing] = useState(false);
  const [refreshMsg, setRefreshMsg] = useState('');
  const [cardsPerRow, setCardsPerRow] = useState(settings.cardsPerRow);
  const [sortBy, setSortBy] = useState<SortOption>(settings.sortBy);
  const [selectedSets, setSelectedSets] = useState<Set<string>>(new Set());
  const [selectedColors, setSelectedColors] = useState<Set<string>>(new Set());
  const [showSetDropdown, setShowSetDropdown] = useState(false);
  const [showColorDropdown, setShowColorDropdown] = useState(false);
  const [showSavedMsg, setShowSavedMsg] = useState(false);
  const [isSaving, setIsSaving] = useState(false);

  const isLocalCache = source === 'Local Cache';

  // Fetch search preferences from backend on mount
  useEffect(() => {
    settings.fetchSearchPrefs();
  }, []);

  // Sync with store defaults when they change
  useEffect(() => {
    setCardsPerRow(settings.cardsPerRow);
    setSortBy(settings.sortBy);
  }, [settings.cardsPerRow, settings.sortBy]);

  // Check if current settings differ from saved defaults
  const hasChanges = cardsPerRow !== settings.cardsPerRow || sortBy !== settings.sortBy;

  const handleSaveDefaults = async () => {
    setIsSaving(true);
    try {
      // Update local state first
      settings.setCardsPerRow(cardsPerRow);
      settings.setSortBy(sortBy);
      // Save to backend
      await settings.saveSearchPrefs();
      setShowSavedMsg(true);
      setTimeout(() => setShowSavedMsg(false), 2000);
    } catch {
      // Error already logged in store
    } finally {
      setIsSaving(false);
    }
  };

  // Extract unique sets and colors from current search results
  const availableSets = useMemo(() => {
    const sets = new Map<string, { code: string; name: string }>();
    cards.forEach(c => {
      if (c.set_code) {
        sets.set(c.set_code.toLowerCase(), { code: c.set_code, name: c.set_name || c.set_code });
      }
    });
    return Array.from(sets.values()).sort((a, b) => a.name.localeCompare(b.name));
  }, [cards]);

  const availableColors = useMemo(() => {
    const colors = new Map<string, string>();
    cards.forEach(c => {
      if (c.color_identity) {
        const colorChars = c.color_identity.split('');
        colorChars.forEach(char => {
          const colorNames: Record<string, string> = {
            W: 'White', U: 'Blue', B: 'Black', R: 'Red', G: 'Green'
          };
          if (colorNames[char]) {
            colors.set(char, colorNames[char]);
          }
        });
      }
    });
    return Array.from(colors.entries()).sort((a, b) => a[1].localeCompare(b[1]));
  }, [cards]);

  // Filter and sort cards
  const filteredCards = useMemo(() => {
    let result = cards;

    // Filter by selected sets
    if (selectedSets.size > 0) {
      result = result.filter(c => c.set_code && selectedSets.has(c.set_code.toLowerCase()));
    }

    // Filter by selected colors (card must have at least one of the selected colors)
    if (selectedColors.size > 0) {
      result = result.filter(c => {
        if (!c.color_identity) return false;
        const cardColors = c.color_identity.split('');
        return cardColors.some(color => selectedColors.has(color));
      });
    }

    return sortCards(result, sortBy);
  }, [cards, selectedSets, selectedColors, sortBy]);

  const handleRefresh = async () => {
    if (!onRefreshFromApi) return;
    setRefreshing(true);
    setRefreshMsg('');
    try {
      await onRefreshFromApi();
      setRefreshMsg('Prices updated from API.');
    } catch {
      setRefreshMsg('Failed to reach API — showing cached results.');
    } finally {
      setRefreshing(false);
      setTimeout(() => setRefreshMsg(''), 4000);
    }
  };

  if (loading) return <p style={{ color: '#888' }}>Searching…</p>;
  if (!cards.length) return null;

  return (
    <div>
      {/* Source / count bar */}
      <div style={{
        display: 'flex', alignItems: 'center', gap: 10,
        fontSize: '0.82rem', marginBottom: '0.75rem', flexWrap: 'wrap',
      }}>
        <span style={{ color: '#888' }}>
          Showing {cards.length}
          {total && total !== cards.length ? ` of ${total}` : ''} results
        </span>

        {/* Source badge */}
        {source && (
          <span style={{
            padding: '2px 8px',
            borderRadius: 10,
            fontSize: '0.78rem',
            fontWeight: 600,
            background: isLocalCache ? '#fff3cd' : '#d3f9d8',
            color: isLocalCache ? '#856404' : '#1a7a2e',
            border: `1px solid ${isLocalCache ? '#ffc107' : '#69db7c'}`,
          }}>
            {isLocalCache ? '📦 Local Cache' : `🌐 ${source}`}
          </span>
        )}

        {/* Update from API button — only shown for cache results */}
        {isLocalCache && onRefreshFromApi && (
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            style={{
              padding: '3px 10px',
              fontSize: '0.78rem',
              border: '1px solid #4c6ef5',
              borderRadius: 4,
              background: refreshing ? '#e8ecff' : '#4c6ef5',
              color: refreshing ? '#4c6ef5' : '#fff',
              cursor: refreshing ? 'not-allowed' : 'pointer',
              fontWeight: 600,
              transition: 'all 0.15s',
            }}
          >
            {refreshing ? '⏳ Updating…' : '🔄 Update from API'}
          </button>
        )}

        {refreshMsg && (
          <span style={{ color: refreshMsg.startsWith('Failed') ? '#c00' : '#1a7a2e', fontSize: '0.78rem' }}>
            {refreshMsg}
          </span>
        )}
      </div>

      {/* Filter and Sort Controls */}
      <div style={{
        display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 12,
        marginBottom: '0.75rem', padding: '0.5rem', background: '#f8f9fa', borderRadius: 6,
      }}>
        {/* Cards per row */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: '0.75rem', color: '#666' }}>Cards/row:</span>
          <select
            value={cardsPerRow}
            onChange={(e) => setCardsPerRow(Number(e.target.value))}
            style={{ padding: '2px 6px', fontSize: '0.75rem', borderRadius: 4, border: '1px solid #ccc' }}
          >
            {[2, 3, 4, 5, 6, 8].map(n => <option key={n} value={n}>{n}</option>)}
          </select>
        </div>

        {/* Sort by */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <span style={{ fontSize: '0.75rem', color: '#666' }}>Sort:</span>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as SortOption)}
            style={{ padding: '2px 6px', fontSize: '0.75rem', borderRadius: 4, border: '1px solid #ccc' }}
          >
            <option value="default">Default</option>
            <option value="name">Name</option>
            <option value="set">Set</option>
            <option value="year">Release Year</option>
          </select>
        </div>

        {/* Save as default button */}
        {hasChanges && (
          <>
            <button
              onClick={handleSaveDefaults}
              disabled={isSaving}
              style={{
                padding: '3px 10px', fontSize: '0.75rem', borderRadius: 4,
                border: '1px solid #4c6ef5', background: isSaving ? '#9ab3f5' : '#4c6ef5',
                color: '#fff', cursor: isSaving ? 'not-allowed' : 'pointer',
                fontWeight: 600, opacity: isSaving ? 0.7 : 1,
              }}
            >
              {isSaving ? '⏳ Saving...' : '💾 Save as Default'}
            </button>
            {showSavedMsg && (
              <span style={{ fontSize: '0.75rem', color: '#2a7a2a' }}>✓ Saved!</span>
            )}
          </>
        )}

        {/* Set filter dropdown */}
        {availableSets.length > 0 && (
          <div style={{ position: 'relative' }}>
            <button
              onClick={() => setShowSetDropdown(!showSetDropdown)}
              style={{
                padding: '3px 10px', fontSize: '0.75rem', borderRadius: 4,
                border: '1px solid #ccc', background: selectedSets.size > 0 ? '#e8f4f8' : '#fff',
                cursor: 'pointer',
              }}
            >
              Filter by Set {selectedSets.size > 0 && `(${selectedSets.size})`} ▼
            </button>
            {showSetDropdown && (
              <div style={{
                position: 'absolute', top: '100%', left: 0, zIndex: 100,
                background: '#fff', border: '1px solid #ccc', borderRadius: 4,
                maxHeight: 200, overflowY: 'auto', minWidth: 200,
                boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
              }}>
                <div style={{ padding: '4px 8px', borderBottom: '1px solid #eee' }}>
                  <button
                    onClick={() => setSelectedSets(new Set())}
                    style={{ fontSize: '0.7rem', color: '#666', background: 'none', border: 'none', cursor: 'pointer' }}
                  >
                    Clear all
                  </button>
                </div>
                {availableSets.map(({ code, name }) => (
                  <label key={code} style={{
                    display: 'flex', alignItems: 'center', gap: 6,
                    padding: '4px 8px', cursor: 'pointer', fontSize: '0.75rem',
                  }}>
                    <input
                      type="checkbox"
                      checked={selectedSets.has(code.toLowerCase())}
                      onChange={(e) => {
                        const newSet = new Set(selectedSets);
                        if (e.target.checked) newSet.add(code.toLowerCase());
                        else newSet.delete(code.toLowerCase());
                        setSelectedSets(newSet);
                      }}
                    />
                    <span style={{ whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                      [{code.toUpperCase()}] {name}
                    </span>
                  </label>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Color filter dropdown */}
        {availableColors.length > 0 && (
          <div style={{ position: 'relative' }}>
            <button
              onClick={() => setShowColorDropdown(!showColorDropdown)}
              style={{
                padding: '3px 10px', fontSize: '0.75rem', borderRadius: 4,
                border: '1px solid #ccc', background: selectedColors.size > 0 ? '#e8f4f8' : '#fff',
                cursor: 'pointer',
              }}
            >
              Filter by Color {selectedColors.size > 0 && `(${selectedColors.size})`} ▼
            </button>
            {showColorDropdown && (
              <div style={{
                position: 'absolute', top: '100%', left: 0, zIndex: 100,
                background: '#fff', border: '1px solid #ccc', borderRadius: 4,
                maxHeight: 200, overflowY: 'auto', minWidth: 150,
                boxShadow: '0 2px 8px rgba(0,0,0,0.1)',
              }}>
                <div style={{ padding: '4px 8px', borderBottom: '1px solid #eee' }}>
                  <button
                    onClick={() => setSelectedColors(new Set())}
                    style={{ fontSize: '0.7rem', color: '#666', background: 'none', border: 'none', cursor: 'pointer' }}
                  >
                    Clear all
                  </button>
                </div>
                {availableColors.map(([code, name]) => (
                  <label key={code} style={{
                    display: 'flex', alignItems: 'center', gap: 6,
                    padding: '4px 8px', cursor: 'pointer', fontSize: '0.75rem',
                  }}>
                    <input
                      type="checkbox"
                      checked={selectedColors.has(code)}
                      onChange={(e) => {
                        const newSet = new Set(selectedColors);
                        if (e.target.checked) newSet.add(code);
                        else newSet.delete(code);
                        setSelectedColors(newSet);
                      }}
                    />
                    <span>{name}</span>
                  </label>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Filtered count */}
        {(selectedSets.size > 0 || selectedColors.size > 0) && (
          <span style={{ fontSize: '0.75rem', color: '#666' }}>
            Showing {filteredCards.length} of {cards.length} cards
          </span>
        )}
      </div>

      {/* Results grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${cardsPerRow}, 1fr)`,
        gap: '1rem',
      }}>
        {filteredCards.map((card, i) => (
          <CardResultCard key={card.link || `${card.name}-${card.set_code}-${i}`} card={card} imageWidth={imageWidth} />
        ))}
      </div>
    </div>
  );
}
