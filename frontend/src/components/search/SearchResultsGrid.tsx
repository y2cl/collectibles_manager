import { useState } from 'react';
import CardResultCard from './CardResultCard';
import type { CardResult } from '../../types/card';

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

function sortCards(cards: CardResult[]): CardResult[] {
  return [...cards].sort((a, b) => {
    const aPromo = isPromoSet(a) ? 1 : 0;
    const bPromo = isPromoSet(b) ? 1 : 0;

    // Promo sets always go last
    if (aPromo !== bPromo) return aPromo - bPromo;

    // Within same promo/non-promo group → sort by set name
    const setDiff = (a.set_name ?? '').localeCompare(b.set_name ?? '');
    if (setDiff !== 0) return setDiff;

    // Within the same set → sort by card name
    const nameDiff = (a.name ?? '').localeCompare(b.name ?? '');
    if (nameDiff !== 0) return nameDiff;

    // Same name → sort by collector number (numeric-aware)
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
  cardsPerRow?: number;
  imageWidth?: number;
  onRefreshFromApi?: () => Promise<unknown>;
}

export default function SearchResultsGrid({
  cards, source, total, loading, cardsPerRow = 4, imageWidth = 160, onRefreshFromApi,
}: Props) {
  const [refreshing, setRefreshing] = useState(false);
  const [refreshMsg, setRefreshMsg] = useState('');

  const isLocalCache = source === 'Local Cache';

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

      {/* Results grid */}
      <div style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${cardsPerRow}, 1fr)`,
        gap: '1rem',
      }}>
        {sortCards(cards).map((card, i) => (
          <CardResultCard key={`${card.name}-${card.set_code}-${i}`} card={card} imageWidth={imageWidth} />
        ))}
      </div>
    </div>
  );
}
