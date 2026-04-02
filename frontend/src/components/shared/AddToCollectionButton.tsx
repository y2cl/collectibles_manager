import { useState } from 'react';
import { useAddCard } from '../../hooks/useCollection';
import { useOwnerStore } from '../../store/ownerStore';
import type { CardResult } from '../../types/card';

interface Props {
  card: CardResult;
  /** Controlled variant — supplied by CardResultCard for MTG. */
  selectedVariant?: string;
  /** Called when the user changes the variant from within this component. */
  onVariantChange?: (v: string) => void;
}


export default function AddToCollectionButton({ card, selectedVariant, onVariantChange }: Props) {
  const { currentOwnerId, currentProfileId } = useOwnerStore();
  const addCard = useAddCard();

  const isMtg = card.game === 'Magic: The Gathering';

  // Variant is controlled externally for MTG (pills in CardResultCard),
  // but we keep a local fallback for non-MTG or standalone usage.
  const [localVariant, setLocalVariant] = useState('');
  const variant = selectedVariant !== undefined ? selectedVariant : localVariant;
  const setVariant = (v: string) => {
    setLocalVariant(v);
    onVariantChange?.(v);
  };

  const [qty, setQty]   = useState(1);
  const [paid, setPaid] = useState(0);

  if (!currentOwnerId) {
    return <span style={{ color: '#999', fontSize: '0.8rem' }}>Select an owner first</span>;
  }

  const handleAdd = () => {
    addCard.mutate({
      owner_id:        currentOwnerId,
      profile_id:      currentProfileId,
      game:            card.game,
      name:            card.name,
      set_name:        card.set_name,
      set_code:        card.set_code,
      card_number:     card.card_number,
      year:            card.year,
      link:            card.link,
      image_url:       card.image_url,
      price_usd:       card.price_usd,
      price_usd_foil:  card.price_usd_foil,
      price_usd_etched:card.price_usd_etched,
      price_low:       card.price_low,
      price_mid:       card.price_mid,
      price_market:    card.price_market,
      quantity:        qty,
      variant,
      paid,
    });
  };

  const inputStyle: React.CSSProperties = {
    padding: '2px 4px', borderRadius: 4, border: '1px solid #ccc', fontSize: '0.8rem',
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 5, marginTop: 4 }}>

      {/* Variant selector — only shown for non-MTG (MTG uses pills in CardResultCard) */}
      {!isMtg && (card.has_foil || card.has_nonfoil || card.price_usd_etched > 0) && (
        <select
          value={variant}
          onChange={(e) => setVariant(e.target.value)}
          style={{ ...inputStyle, fontSize: '0.8rem', cursor: 'pointer' }}
        >
          {card.has_nonfoil           && <option value="nonfoil">Nonfoil</option>}
          {card.has_foil              && <option value="foil">Foil</option>}
          {card.price_usd_etched > 0  && <option value="etched">Etched</option>}
        </select>
      )}

      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
        <label style={{ fontSize: '0.75rem', color: '#555' }}>Qty</label>
        <input
          type="number"
          min={1}
          max={999}
          value={qty}
          onChange={(e) => setQty(Math.max(1, parseInt(e.target.value) || 1))}
          style={{ ...inputStyle, width: 48 }}
        />
        <label style={{ fontSize: '0.75rem', color: '#555' }}>Paid $</label>
        <input
          type="number"
          min={0}
          step={0.01}
          value={paid}
          onChange={(e) => setPaid(parseFloat(e.target.value) || 0)}
          style={{ ...inputStyle, width: 64 }}
        />
      </div>

      <button
        onClick={handleAdd}
        disabled={addCard.isPending}
        style={{
          padding: '4px 10px',
          background: addCard.isPending ? '#a0aee8' : '#4c6ef5',
          color: '#fff',
          border: 'none',
          borderRadius: 4,
          cursor: addCard.isPending ? 'not-allowed' : 'pointer',
          fontSize: '0.82rem',
          fontWeight: 600,
          transition: 'background 0.15s',
        }}
      >
        {addCard.isPending ? 'Adding…' : '+ Add to Collection'}
      </button>

      {addCard.isSuccess && (
        <span style={{ color: '#2a7a2a', fontSize: '0.75rem' }}>✓ Added!</span>
      )}
      {addCard.isError && (
        <span style={{ color: '#c00', fontSize: '0.75rem' }}>Error — try again</span>
      )}
    </div>
  );
}
