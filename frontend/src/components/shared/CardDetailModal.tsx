import CardImage from './CardImage';

// Flexible card type that works with both CardResult and CollectionCard
interface CardDetail {
  game: string;
  name: string;
  set_name: string;
  set_code: string;
  card_number: string;
  image_url: string;
  link: string;
  // Rich MTG fields (all optional)
  mana_cost?: string;
  type_line?: string;
  oracle_text?: string;
  keywords?: string;
  power?: string;
  toughness?: string;
  rarity?: string;
  color_identity?: string;
  finish?: string;
  is_proxy?: boolean;
}

interface Props {
  card: CardDetail | null;
  isOpen: boolean;
  onClose: () => void;
}

export default function CardDetailModal({ card, isOpen, onClose }: Props) {
  if (!isOpen || !card) return null;

  const isMtg = card.game === 'Magic: The Gathering';

  // Parse keywords into array
  const keywords = card.keywords?.split(';').map(k => k.trim()).filter(Boolean) ?? [];

  // Parse color identity into symbols
  const colorSymbols: Record<string, string> = {
    W: '⚪', U: '🔵', B: '⚫', R: '🔴', G: '🟢',
  };
  const colors = card.color_identity?.split('') ?? [];

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.7)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 1000,
        padding: '1rem',
      }}
      onClick={onClose}
    >
      <div
        style={{
          background: '#fff',
          borderRadius: 12,
          maxWidth: 600,
          width: '100%',
          maxHeight: '90vh',
          overflow: 'auto',
          padding: '1.5rem',
          position: 'relative',
        }}
        onClick={e => e.stopPropagation()}
      >
        {/* Close button */}
        <button
          onClick={onClose}
          style={{
            position: 'absolute',
            top: 12,
            right: 12,
            background: 'none',
            border: 'none',
            fontSize: '1.5rem',
            cursor: 'pointer',
            color: '#666',
          }}
        >
          ×
        </button>

        {/* Header */}
        <div style={{ display: 'flex', gap: '1rem', marginBottom: '1rem' }}>
          {card.image_url && (
            <CardImage
              src={card.image_url}
              alt={card.name}
              width={200}
              isProxy={card.is_proxy}
            />
          )}
          <div style={{ flex: 1 }}>
            <h2 style={{ margin: '0 0 0.5rem', fontSize: '1.5rem' }}>
              {card.name}
            </h2>
            <div style={{ fontSize: '0.9rem', color: '#666', marginBottom: '0.5rem' }}>
              {card.set_code && `[${card.set_code.toUpperCase()}] `}
              {card.set_name}
              {card.card_number && ` · #${card.card_number}`}
            </div>
            {isMtg && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 8 }}>
                {card.mana_cost && (
                  <span style={{ fontSize: '1.1rem' }}>{card.mana_cost}</span>
                )}
                {colors.length > 0 && (
                  <span style={{ fontSize: '1.1rem' }}>
                    {colors.map(c => colorSymbols[c] || c).join(' ')}
                  </span>
                )}
              </div>
            )}
          </div>
        </div>

        {/* Card Info */}
        <div style={{ display: 'grid', gap: '0.75rem' }}>
          {/* Type Line */}
          {card.type_line && (
            <div>
              <label style={{ fontSize: '0.8rem', color: '#666', display: 'block' }}>
                Type
              </label>
              <div style={{ fontSize: '0.95rem' }}>{card.type_line}</div>
            </div>
          )}

          {/* Oracle Text */}
          {card.oracle_text && (
            <div>
              <label style={{ fontSize: '0.8rem', color: '#666', display: 'block' }}>
                Text
              </label>
              <div
                style={{
                  fontSize: '0.9rem',
                  background: '#f5f5f5',
                  padding: '0.75rem',
                  borderRadius: 6,
                  whiteSpace: 'pre-wrap',
                }}
              >
                {card.oracle_text}
              </div>
            </div>
          )}

          {/* Power/Toughness */}
          {(card.power || card.toughness) && (
            <div style={{ display: 'flex', gap: '1rem' }}>
              {card.power && (
                <div>
                  <label style={{ fontSize: '0.8rem', color: '#666' }}>Power</label>
                  <div style={{ fontSize: '1.1rem', fontWeight: 600 }}>{card.power}</div>
                </div>
              )}
              {card.toughness && (
                <div>
                  <label style={{ fontSize: '0.8rem', color: '#666' }}>Toughness</label>
                  <div style={{ fontSize: '1.1rem', fontWeight: 600 }}>{card.toughness}</div>
                </div>
              )}
            </div>
          )}

          {/* Keywords */}
          {keywords.length > 0 && (
            <div>
              <label style={{ fontSize: '0.8rem', color: '#666', display: 'block' }}>
                Keywords
              </label>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 4 }}>
                {keywords.map((kw, i) => (
                  <span
                    key={i}
                    style={{
                      background: '#e8f0fe',
                      color: '#4c6ef5',
                      padding: '2px 8px',
                      borderRadius: 12,
                      fontSize: '0.8rem',
                    }}
                  >
                    {kw}
                  </span>
                ))}
              </div>
            </div>
          )}

          {/* Rarity & Finish */}
          <div style={{ display: 'flex', gap: '1rem' }}>
            {card.rarity && (
              <div>
                <label style={{ fontSize: '0.8rem', color: '#666' }}>Rarity</label>
                <div style={{ fontSize: '0.9rem', textTransform: 'capitalize' }}>
                  {card.rarity}
                </div>
              </div>
            )}
            {card.finish && (
              <div>
                <label style={{ fontSize: '0.8rem', color: '#666' }}>Finish</label>
                <div style={{ fontSize: '0.9rem', textTransform: 'capitalize' }}>
                  {card.finish}
                </div>
              </div>
            )}
          </div>

          {/* Scryfall Link */}
          {card.link && (
            <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid #eee' }}>
              <a
                href={card.link}
                target="_blank"
                rel="noopener noreferrer"
                style={{
                  color: '#4c6ef5',
                  textDecoration: 'none',
                  display: 'inline-flex',
                  alignItems: 'center',
                  gap: 4,
                }}
              >
                View on Scryfall ↗
              </a>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
