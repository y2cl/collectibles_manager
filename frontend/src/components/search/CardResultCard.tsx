import { useState, useEffect } from 'react';
import CardImage from '../shared/CardImage';
import AddToCollectionButton from '../shared/AddToCollectionButton';
import CardDetailModal from '../shared/CardDetailModal';
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

// NGC/coin grade ordering — lower number = lower grade
const COIN_GRADE_PREFIX_ORDER: Record<string, number> = {
  AG: 0, G: 1, VG: 2, F: 3, VF: 4, EF: 5, XF: 5, AU: 6,
  MS: 7, SP: 7, SMS: 7, PR: 8, PF: 8,
};

function coinGradeSort(a: string, b: string): number {
  const matchA = a.match(/^([A-Z]+)-?(\d+)?$/);
  const matchB = b.match(/^([A-Z]+)-?(\d+)?$/);
  const prefA = matchA ? (COIN_GRADE_PREFIX_ORDER[matchA[1]] ?? 99) : 99;
  const prefB = matchB ? (COIN_GRADE_PREFIX_ORDER[matchB[1]] ?? 99) : 99;
  if (prefA !== prefB) return prefA - prefB;
  const numA = matchA?.[2] ? parseInt(matchA[2]) : 0;
  const numB = matchB?.[2] ? parseInt(matchB[2]) : 0;
  return numA - numB;
}

function coinGrades(card: CardResult): string[] {
  if (!card.prices_map) return [];
  return Object.keys(card.prices_map).sort(coinGradeSort);
}

function coinGradePrice(card: CardResult, grade: string): number | null {
  const entry = card.prices_map?.[grade];
  if (entry == null) return null;
  if (typeof entry === 'number') return entry > 0 ? entry : null;
  // shouldn't happen for coins, but handle object format gracefully
  const obj = entry as { low: number; mid: number; market: number };
  const price = obj.market || obj.mid || obj.low;
  return price > 0 ? price : null;
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
  if (!entry || typeof entry === 'number') return null;
  const price = entry.market || entry.mid || entry.low;
  return price > 0 ? price : null;
}

export default function CardResultCard({ card, imageWidth = 160 }: Props) {
  const isMtg  = card.game === 'Magic: The Gathering';
  const isPkmn = card.game === 'Pokémon';
  const isCoin = card.game === 'Coins';

  const coinTypeOptions = isCoin ? (card.coin_type_options ?? []) : [];
  // Default to 'MS' (always position 0 for business-strike coins; remounting via key handles resets)
  const [selectedCoinType, setSelectedCoinType] = useState<string>(
    coinTypeOptions.find(t => t === 'MS') ?? coinTypeOptions[0] ?? ''
  );

  const [showBack, setShowBack] = useState(false);
  const [isDetailOpen, setIsDetailOpen] = useState(false);

  // For coins: use data from the selected type (MS / MS PL / MS DPL)
  const coinTypeData = isCoin && selectedCoinType
    ? card.coin_types_data?.[selectedCoinType]
    : undefined;

  const effectivePricesMap = coinTypeData?.prices_map ?? card.prices_map;
  const effectiveImageUrl   = coinTypeData?.image_url  || card.image_url;
  const effectiveImageUrlBack = coinTypeData?.image_url_back ?? card.image_url_back;
  const effectiveLink       = coinTypeData?.link        || card.link;
  const effectivePriceUsd   = coinTypeData?.price_usd   ?? card.price_usd;
  const effectivePriceLow   = coinTypeData?.price_low   ?? card.price_low;
  const effectivePriceMarket = coinTypeData?.price_market ?? card.price_market;

  // Build effective card for AddToCollectionButton
  const effectiveCard = isCoin && coinTypeData ? {
    ...card,
    prices_map:    effectivePricesMap,
    image_url:     effectiveImageUrl,
    image_url_back: effectiveImageUrlBack,
    link:          effectiveLink,
    price_usd:     effectivePriceUsd,
    price_low:     effectivePriceLow,
    price_market:  effectivePriceMarket,
  } : card;

  const effectiveCardForVariants = isCoin ? { ...card, prices_map: effectivePricesMap } : card;
  const variants = isMtg ? mtgVariants(card) : isPkmn ? pkmnVariants(card) : isCoin ? coinGrades(effectiveCardForVariants) : [];
  const isDfc = !!(isCoin ? effectiveImageUrlBack : card.image_url_back);

  // Default to the first available variant
  const [selectedVariant, setSelectedVariant] = useState<string>(variants[0] ?? '');

  // Reset grade selection when coin type changes
  useEffect(() => {
    const newGrades = coinGrades({ ...card, prices_map: effectivePricesMap });
    setSelectedVariant(newGrades[0] ?? '');
  }, [selectedCoinType]);

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

  // Calculate container width to match image + minimal padding
  const containerWidth = imageWidth + 16; // image width + padding on both sides

  // Set icon URL for MTG cards
  const setIconUrl = isMtg && card.set_code
    ? `https://svgs.scryfall.io/sets/${card.set_code.toLowerCase()}.svg`
    : null;

  return (
    <div style={{
      border: '1px solid #dde',
      borderRadius: 8,
      padding: '0.5rem',
      background: '#fff',
      display: 'flex',
      flexDirection: 'column',
      gap: 6,
      width: containerWidth,
      maxWidth: containerWidth,
      boxSizing: 'border-box',
    }}>
      {/* Card image with optional flip button */}
      <div style={{ position: 'relative', display: 'inline-block' }}>
        <div onClick={() => setIsDetailOpen(true)} style={{ cursor: 'pointer' }}>
          <CardImage
            src={showBack ? (effectiveImageUrlBack ?? '') : effectiveImageUrl}
            alt={showBack ? `${card.name} (back)` : card.name}
            width={imageWidth}
          />
        </div>
        {isDfc && (
          <button
            onClick={() => setShowBack((b) => !b)}
            title={isCoin
              ? (showBack ? 'Show obverse' : 'Show reverse')
              : (showBack ? 'Show front face' : 'Show back face')}
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
            {isCoin ? '🪙' : '🔄'}
          </button>
        )}
      </div>

      {isCoin ? (
        /* ── Coin info block ── */
        <div>
          <div style={{ fontWeight: 600, fontSize: '0.9rem' }}>
            {/* Strip year range "(1878-1921)" from series name, append the specific year */}
            {card.name.replace(/\s*\(.*?\)\s*$/, '')} {card.year}
          </div>
          {card.mint_mark && (
            <div style={{ fontSize: '0.75rem', color: '#666' }}>Mint: {card.mint_mark}</div>
          )}
          {effectiveLink && (
            <div style={{ fontSize: '0.75rem' }}>
              <a href={effectiveLink} target="_blank" rel="noreferrer"
                 style={{ color: '#4c6ef5', textDecoration: 'none' }}>
                NGC Link ↗
              </a>
            </div>
          )}
        </div>
      ) : (
        /* ── Card / other game info block ── */
        <div>
          <div style={{ fontWeight: 600, fontSize: '0.9rem', lineHeight: 1.2 }}>{card.name}</div>
          <div style={{ fontSize: '0.75rem', color: '#666', display: 'flex', alignItems: 'center', gap: 4, marginTop: 2 }}>
            {setIconUrl && (
              <img
                src={setIconUrl}
                alt={card.set_code}
                style={{ width: 16, height: 16, objectFit: 'contain' }}
                onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
              />
            )}
            <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {card.set_code ? `[${card.set_code.toUpperCase()}] ` : ''}{card.set_name}
              {card.card_number ? ` · #${card.card_number}` : ''}
              {card.year ? ` · ${card.year}` : ''}
            </span>
          </div>
          {card.artist && (
            <div style={{ fontSize: '0.7rem', color: '#999' }}>Art: {card.artist}</div>
          )}
        </div>
      )}

      {/* ── Coin type selector (MS / MS PL / MS DPL) ── */}
      {isCoin && coinTypeOptions.length > 1 && (
        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap', marginBottom: 2 }}>
          {coinTypeOptions.map((type) => (
            <button
              key={type}
              onClick={() => setSelectedCoinType(type)}
              style={{
                padding: '2px 9px',
                borderRadius: 10,
                border: `1px solid ${selectedCoinType === type ? '#4c6ef5' : '#dde'}`,
                background: selectedCoinType === type ? '#eef1ff' : '#fafafa',
                cursor: 'pointer',
                fontSize: '0.73rem',
                fontWeight: selectedCoinType === type ? 700 : 400,
                color: selectedCoinType === type ? '#3b5bdb' : '#666',
                transition: 'all 0.12s',
              }}
            >
              {type}
            </button>
          ))}
        </div>
      )}

      {/* ── Variant / grade price pills (MTG, Pokémon, Coins) ── */}
      {variants.length > 0 ? (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
          {variants.map((v) => {
            const price = isMtg ? mtgVariantPrice(card, v) : isPkmn ? pkmnVariantPrice(card, v) : coinGradePrice({ ...card, prices_map: effectivePricesMap }, v);
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
        card={effectiveCard}
        selectedVariant={selectedVariant}
        onVariantChange={setSelectedVariant}
        selectedCoinType={isCoin ? selectedCoinType : undefined}
      />

      <CardDetailModal
        card={card}
        isOpen={isDetailOpen}
        onClose={() => setIsDetailOpen(false)}
      />
    </div>
  );
}
