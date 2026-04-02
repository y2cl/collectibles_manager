import { useState } from 'react';
import CardImage from '../shared/CardImage';
import AddToCollectionButton from '../shared/AddToCollectionButton';
import type { CardResult } from '../../types/card';

interface Props {
  card: CardResult;
  imageWidth?: number;
}

/** Price for a given MTG variant, or null if unavailable. */
function mtgVariantPrice(card: CardResult, variant: string): number | null {
  if (variant === 'nonfoil') return card.price_usd > 0 ? card.price_usd : null;
  if (variant === 'foil')    return card.price_usd_foil > 0 ? card.price_usd_foil : null;
  if (variant === 'etched')  return card.price_usd_etched > 0 ? card.price_usd_etched : null;
  return null;
}

/** All available MTG variants for this card. */
function mtgVariants(card: CardResult): string[] {
  const v: string[] = [];
  if (card.has_nonfoil)           v.push('nonfoil');
  if (card.has_foil)              v.push('foil');
  if (card.price_usd_etched > 0)  v.push('etched');
  return v;
}

/** Human-readable labels for Pokémon TCG variant keys. */
const PKMN_VARIANT_LABELS: Record<string, string> = {
  normal:               'Normal',
  holofoil:             '✨ Holofoil',
  reverseHolofoil:      '🔄 Reverse Holo',
  '1stEditionHolofoil': '⭐ 1st Ed Holo',
  '1stEdition':         '⭐ 1st Edition',
  unlimited:            'Unlimited',
  unlimitedHolofoil:    '✨ Unlimited Holo',
};

/** All available Pokémon variants from prices_map, ordered by rarity. */
const PKMN_VARIANT_ORDER = [
  'normal', 'reverseHolofoil', 'holofoil',
  'unlimited', 'unlimitedHolofoil', '1stEdition', '1stEditionHolofoil',
];

function pkmnVariants(card: CardResult): string[] {
  if (!card.prices_map) return [];
  return PKMN_VARIANT_ORDER.filter((k) => k in card.prices_map!);
}

function pkmnVariantPrice(card: CardResult, variant: string): number | null {
  const entry = card.prices_map?.[variant];
  if (!entry) return null;
  const price = entry.market || entry.mid || entry.low;
  return price > 0 ? price : null;
}

export default function CardResultCard({ card, imageWidth = 160 }: Props) {
  const isMtg  = card.game === 'Magic: The Gathering';
  const isPkmn = card.game === 'Pokémon';
  const variants = isMtg ? mtgVariants(card) : isPkmn ? pkmnVariants(card) : [];
  const isDfc = !!(card.image_url_back);

  // Default to the first available variant
  const [selectedVariant, setSelectedVariant] = useState<string>(variants[0] ?? '');
  const [showBack, setShowBack] = useState(false);

  const pillStyle = (active: boolean): React.CSSProperties => ({
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 6,
    padding: '3px 8px',
    borderRadius: 5,
    border: `1px solid ${active ? '#4c6ef5' : '#dde'}`,
    background: active ? '#eef1ff' : '#fafafa',
    cursor: 'pointer',
    fontSize: '0.78rem',
    fontWeight: active ? 700 : 400,
    color: active ? '#3b5bdb' : '#444',
    transition: 'all 0.12s',
    userSelect: 'none',
  });

  const VARIANT_LABELS: Record<string, string> = {
    // MTG
    nonfoil: 'Nonfoil',
    foil:    '✨ Foil',
    etched:  '⬡ Etched',
    // Pokémon (merged in so one map covers both)
    ...PKMN_VARIANT_LABELS,
  };

  return (
    <div style={{
      border: '1px solid #dde',
      borderRadius: 8,
      padding: '0.75rem',
      background: '#fff',
      display: 'flex',
      flexDirection: 'column',
      gap: 8,
    }}>
      {/* Card image with optional flip button */}
      <div style={{ position: 'relative', display: 'inline-block' }}>
        <CardImage
          src={showBack ? (card.image_url_back ?? '') : card.image_url}
          alt={showBack ? `${card.name} (back)` : card.name}
          width={imageWidth}
          link={card.link}
        />
        {isDfc && (
          <button
            onClick={() => setShowBack((b) => !b)}
            title={showBack ? 'Show front face' : 'Show back face'}
            style={{
              position: 'absolute',
              bottom: 6,
              right: 6,
              background: 'rgba(0,0,0,0.65)',
              color: '#fff',
              border: 'none',
              borderRadius: '50%',
              width: 28,
              height: 28,
              cursor: 'pointer',
              fontSize: '14px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              lineHeight: 1,
              backdropFilter: 'blur(2px)',
            }}
          >
            🔄
          </button>
        )}
      </div>

      <div>
        <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>{card.name}</div>
        <div style={{ fontSize: '0.75rem', color: '#666' }}>
          {card.set_code ? `[${card.set_code.toUpperCase()}] ` : ''}{card.set_name}
          {card.card_number ? ` · #${card.card_number}` : ''}
          {card.year ? ` · ${card.year}` : ''}
        </div>
        {card.artist && (
          <div style={{ fontSize: '0.7rem', color: '#999' }}>Art: {card.artist}</div>
        )}
      </div>

      {/* ── Variant price pills (MTG + Pokémon) ── */}
      {variants.length > 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          {variants.map((v) => {
            const price = isMtg ? mtgVariantPrice(card, v) : pkmnVariantPrice(card, v);
            const active = v === selectedVariant;
            return (
              <div
                key={v}
                style={pillStyle(active)}
                onClick={() => setSelectedVariant(v)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => e.key === 'Enter' && setSelectedVariant(v)}
              >
                <span>{VARIANT_LABELS[v] ?? v}</span>
                <span style={{ fontWeight: 600, color: active ? '#2a7a2a' : '#555' }}>
                  {price != null ? `$${price.toFixed(2)}` : '—'}
                </span>
              </div>
            );
          })}
        </div>
      ) : (
        <div style={{ fontSize: '0.8rem', color: '#aaa' }}>No pricing available</div>
      )}

      <div style={{ fontSize: '0.7rem', color: '#aaa' }}>{card.source}</div>

      <AddToCollectionButton
        card={card}
        selectedVariant={selectedVariant}
        onVariantChange={setSelectedVariant}
      />
    </div>
  );
}
