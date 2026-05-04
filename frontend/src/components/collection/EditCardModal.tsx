import { useState } from 'react';
import type { CollectionCard } from '../../types/card';
import { gradingLookupUrl } from '../../utils/gradingLookup';

const SPORTS = [
  { value: 'baseball',   label: '⚾ Baseball' },
  { value: 'football',   label: '🏈 Football' },
  { value: 'basketball', label: '🏀 Basketball' },
  { value: 'hockey',     label: '🏒 Hockey' },
  { value: 'soccer',     label: '⚽ Soccer' },
  { value: 'other',      label: '🃏 Other' },
];

const CONDITIONS = ['New', 'Like New', 'Very Good', 'Good', 'Acceptable', 'Poor'];

const COIN_OR_BILL = ['Coin', 'Bill', 'Token', 'Medal', 'Proof Set', 'Mint Set', 'Other'];

interface Props {
  card: CollectionCard;
  onSave: (id: number, payload: Record<string, unknown>) => Promise<void>;
  onClose: () => void;
}

export default function EditCardModal({ card, onSave, onClose }: Props) {
  const isSports      = card.game === 'Sports Cards';
  const isCollectible = card.game === 'Collectibles';
  const isCoin        = card.game === 'Coins';

  const [form, setForm] = useState({
    name:            card.name ?? '',
    card_number:     card.card_number ?? '',
    set_name:        card.set_name ?? '',
    year:            card.year ?? '',
    variant:         card.variant ?? '',
    sport:           card.sport ?? 'baseball',
    manufacturer:    card.manufacturer ?? '',
    upc:             card.upc ?? '',
    print_run:       card.print_run ?? '',
    grading_company: card.grading_company ?? '',
    grade:           card.grade ?? '',
    serial_number:   card.serial_number ?? '',
    signed:          card.signed === 'true',
    rc:              card.rc ?? false,
    is_proxy:        card.is_proxy ?? false,
    image_url:       card.image_url ?? '',
    paid:            String(card.paid ?? ''),
    price_usd:       String(card.price_usd ?? ''),
    // Coin-specific
    denomination:    card.denomination ?? '',
    country:         card.country ?? 'USA',
    coin_or_bill:    card.coin_or_bill ?? 'Coin',
    silver_amount:   card.silver_amount != null ? String(Math.round(card.silver_amount * 1000) / 10) : '',
    mint_mark:       card.mint_mark ?? '',
    notes:           card.notes ?? '',
  });
  const [saving, setSaving] = useState(false);
  const [error, setError]   = useState('');

  const set = (field: string) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) => {
      const value = e.target.type === 'checkbox' ? (e.target as HTMLInputElement).checked : e.target.value;
      setForm((prev) => ({ ...prev, [field]: value }));
    };

  const handleSave = async () => {
    if (!form.name.trim()) { setError('Name is required.'); return; }
    setSaving(true);
    setError('');
    try {
      const silverVal = isCoin && form.silver_amount.trim()
        ? (parseFloat(form.silver_amount) / 100) || 0
        : undefined;
      await onSave(card.id, {
        name:            form.name.trim(),
        card_number:     form.card_number.trim() || undefined,
        set_name:        form.set_name.trim() || undefined,
        year:            form.year.trim() || undefined,
        variant:         form.variant.trim() || undefined,
        sport:           isSports ? form.sport : undefined,
        manufacturer:    (isSports || isCollectible) ? (form.manufacturer.trim() || undefined) : undefined,
        upc:             isCollectible ? (form.upc.trim() || undefined) : undefined,
        print_run:       isSports ? (form.print_run.trim() || undefined) : undefined,
        grading_company: isSports ? (form.grading_company.trim() || undefined) : undefined,
        grade:           (isSports || isCoin) ? (form.grade.trim() || undefined) : undefined,
        serial_number:   isSports ? (form.serial_number.trim() || undefined) : (isCoin ? (form.serial_number.trim() || undefined) : undefined),
        signed:          isSports ? (form.signed ? 'true' : '') : undefined,
        rc:              isSports ? (form.rc || undefined) : undefined,
        is_proxy:        form.is_proxy || undefined,
        image_url:       form.image_url.trim() || undefined,
        paid:            parseFloat(form.paid) || 0,
        price_usd:       parseFloat(form.price_usd) || undefined,
        notes:           form.notes.trim() || undefined,
        // Coin-specific
        denomination:    isCoin ? (form.denomination.trim() || undefined) : undefined,
        country:         isCoin ? (form.country.trim() || undefined) : undefined,
        coin_or_bill:    isCoin ? (form.coin_or_bill || undefined) : undefined,
        silver_amount:   silverVal,
        mint_mark:       isCoin ? (form.mint_mark.trim() || undefined) : undefined,
      });
      onClose();
    } catch {
      setError('Save failed — try again.');
      setSaving(false);
    }
  };

  const inputStyle: React.CSSProperties = {
    padding: '6px 10px', borderRadius: 4, border: '1px solid #ccc',
    fontSize: '0.9rem', width: '100%', boxSizing: 'border-box',
  };
  const labelStyle: React.CSSProperties = {
    display: 'flex', flexDirection: 'column', gap: 4,
    fontSize: '0.8rem', color: '#555', flex: 1,
  };
  const rowStyle: React.CSSProperties = { display: 'flex', gap: 12 };

  return (
    <div
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        zIndex: 1000,
      }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div style={{
        background: '#fff', borderRadius: 8, padding: '24px 28px',
        width: '100%', maxWidth: 620, maxHeight: '90vh', overflowY: 'auto',
        boxShadow: '0 8px 32px rgba(0,0,0,0.18)',
      }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <h2 style={{ margin: 0, fontSize: '1.1rem' }}>
            Edit {isSports ? 'Sports Card' : isCollectible ? 'Collectible' : isCoin ? 'Coin' : 'Card'}
          </h2>
          <button
            onClick={onClose}
            style={{ background: 'none', border: 'none', fontSize: '1.3rem', cursor: 'pointer', color: '#888', lineHeight: 1 }}
          >
            ×
          </button>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>

          {/* Sport selector — Sports Cards only */}
          {isSports && (
            <label style={{ ...labelStyle, maxWidth: 220 }}>
              Sport
              <select style={{ ...inputStyle, width: '100%' }} value={form.sport} onChange={set('sport')}>
                {SPORTS.map(({ value, label }) => <option key={value} value={value}>{label}</option>)}
              </select>
            </label>
          )}

          {/* Name row */}
          <div style={rowStyle}>
            <label style={labelStyle}>
              {isSports ? 'Player Name *' : isCoin ? 'Coin Name *' : 'Name *'}
              <input style={inputStyle} value={form.name} onChange={set('name')} />
            </label>
            {!isCollectible && (
              <label style={{ ...labelStyle, flex: '0 0 120px' }}>
                {isCoin ? 'Date / Variety' : 'Card #'}
                <input style={inputStyle} value={form.card_number} onChange={set('card_number')} />
              </label>
            )}
          </div>

          {/* Year / Set / Strike Type (coins) or Insert (MTG/Pokémon) or Condition (collectibles) */}
          <div style={rowStyle}>
            <label style={{ ...labelStyle, flex: '0 0 90px' }}>
              Year
              <input style={inputStyle} value={form.year} onChange={set('year')} />
            </label>
            <label style={labelStyle}>
              {isCollectible ? 'Line / Series' : isCoin ? 'Series' : 'Set'}
              <input style={inputStyle} value={form.set_name} onChange={set('set_name')} />
            </label>
            {isCollectible ? (
              <label style={labelStyle}>
                Condition
                <select style={inputStyle} value={form.variant} onChange={set('variant')}>
                  {CONDITIONS.map((c) => <option key={c}>{c}</option>)}
                </select>
              </label>
            ) : isCoin ? (
              <label style={{ ...labelStyle, flex: '0 0 110px' }}>
                Strike Type
                <input style={inputStyle} value={form.variant} onChange={set('variant')} placeholder="MS, MS PL, PF…" />
              </label>
            ) : (
              <label style={labelStyle}>
                Insert
                <input style={inputStyle} value={form.variant} onChange={set('variant')} />
              </label>
            )}
            {isSports && (
              <label style={{ ...labelStyle, flex: '0 0 100px' }}>
                Serial #
                <input style={inputStyle} value={form.print_run} onChange={set('print_run')} placeholder="e.g. 23/99" />
              </label>
            )}
          </div>

          {/* Manufacturer / UPC — Collectibles */}
          {isCollectible && (
            <div style={rowStyle}>
              <label style={labelStyle}>
                Manufacturer
                <input style={inputStyle} value={form.manufacturer} onChange={set('manufacturer')} />
              </label>
              <label style={labelStyle}>
                UPC
                <input style={inputStyle} value={form.upc} onChange={set('upc')} />
              </label>
            </div>
          )}

          {/* Grading Company / Grade / Cert. Number / Signed — Sports Cards */}
          {isSports && (
            <>
              <div style={rowStyle}>
                <label style={labelStyle}>
                  Grading Company
                  <input style={inputStyle} value={form.grading_company} onChange={set('grading_company')} placeholder="e.g. PSA, BGS" />
                </label>
                <label style={{ ...labelStyle, flex: '0 0 90px' }}>
                  Grade
                  <input style={inputStyle} value={form.grade} onChange={set('grade')} placeholder="e.g. 9.5" />
                </label>
                <label style={{ ...labelStyle, flex: '0 0 140px' }}>
                  Cert. Number
                  <input style={inputStyle} value={form.serial_number} onChange={set('serial_number')} placeholder="e.g. 12345678" />
                </label>
                <label style={{ display: 'flex', flexDirection: 'row', alignItems: 'center', gap: 8, fontSize: '0.9rem', color: '#555', paddingTop: 20, cursor: 'pointer', whiteSpace: 'nowrap' }}>
                  <input type="checkbox" checked={form.signed} onChange={set('signed')} style={{ width: 16, height: 16 }} />
                  Signed
                </label>
                <label style={{ display: 'flex', flexDirection: 'row', alignItems: 'center', gap: 8, fontSize: '0.9rem', color: '#555', paddingTop: 20, cursor: 'pointer', whiteSpace: 'nowrap' }}>
                  <input type="checkbox" checked={form.rc} onChange={set('rc')} style={{ width: 16, height: 16 }} />
                  RC
                </label>
              </div>
              {gradingLookupUrl(form.grading_company, form.serial_number) && (
                <div style={{ fontSize: '0.82rem' }}>
                  <a
                    href={gradingLookupUrl(form.grading_company, form.serial_number)!}
                    target="_blank"
                    rel="noreferrer"
                    style={{ color: '#4c6ef5', textDecoration: 'none' }}
                  >
                    🔍 Look up cert #{form.serial_number} on {form.grading_company} →
                  </a>
                </div>
              )}
            </>
          )}

          {/* Coin-specific fields */}
          {isCoin && (
            <>
              <div style={{ borderTop: '1px solid #eee', paddingTop: 12, marginTop: 2 }}>
                <div style={{ fontSize: '0.78rem', fontWeight: 600, color: '#888', marginBottom: 8, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  🪙 Coin Details
                </div>
                <div style={{ ...rowStyle, flexWrap: 'wrap' }}>
                  <label style={{ ...labelStyle, flex: '0 0 90px' }}>
                    Denomination
                    <input style={inputStyle} value={form.denomination} onChange={set('denomination')} placeholder="e.g. $1.00" />
                  </label>
                  <label style={{ ...labelStyle, flex: '0 0 80px' }}>
                    Mint Mark
                    <input style={inputStyle} value={form.mint_mark} onChange={set('mint_mark')} placeholder="S, D, CC…" />
                  </label>
                  <label style={{ ...labelStyle, flex: '0 0 90px' }}>
                    Silver %
                    <input
                      type="number" min={0} max={100} step={0.1}
                      style={inputStyle} value={form.silver_amount}
                      onChange={set('silver_amount')}
                      placeholder="e.g. 90"
                    />
                  </label>
                  <label style={{ ...labelStyle, flex: '0 0 100px' }}>
                    Type
                    <select style={inputStyle} value={form.coin_or_bill} onChange={set('coin_or_bill')}>
                      {COIN_OR_BILL.map((t) => <option key={t}>{t}</option>)}
                    </select>
                  </label>
                  <label style={{ ...labelStyle, flex: '0 0 90px' }}>
                    Country
                    <input style={inputStyle} value={form.country} onChange={set('country')} placeholder="USA" />
                  </label>
                  <label style={{ ...labelStyle, flex: '0 0 140px' }}>
                    NGC Cert #
                    <input style={inputStyle} value={form.serial_number} onChange={set('serial_number')} placeholder="e.g. 1234567-001" />
                  </label>
                  <label style={{ ...labelStyle, flex: '0 0 160px' }}>
                    NGC Grade
                    <input style={inputStyle} value={form.grade} onChange={set('grade')} placeholder="e.g. MS-63, MS PL-MS-63" />
                  </label>
                </div>
              </div>
              <label style={labelStyle}>
                Notes
                <textarea
                  style={{ ...inputStyle, minHeight: 56, resize: 'vertical' }}
                  value={form.notes}
                  onChange={set('notes')}
                  placeholder="Any notes about this coin…"
                />
              </label>
            </>
          )}

          {/* Price Paid / Value */}
          <div style={rowStyle}>
            <label style={{ ...labelStyle, flex: '0 0 140px' }}>
              Price Paid ($)
              <input type="number" min={0} step={0.01} style={inputStyle} value={form.paid} onChange={set('paid')} />
            </label>
            <label style={{ ...labelStyle, flex: '0 0 140px' }}>
              Value ($)
              <input type="number" min={0} step={0.01} style={inputStyle} value={form.price_usd} onChange={set('price_usd')} />
            </label>
          </div>

          {/* Image URL */}
          <label style={labelStyle}>
            Image URL
            <input style={inputStyle} value={form.image_url} onChange={set('image_url')} placeholder="https://…" />
            {form.image_url && (
              <img src={form.image_url} alt="preview" style={{ marginTop: 6, maxHeight: 80, borderRadius: 4, objectFit: 'contain', alignSelf: 'flex-start' }} />
            )}
          </label>

          {/* Proxy checkbox - all card types */}
          <label style={{ display: 'flex', flexDirection: 'row', alignItems: 'center', gap: 8, fontSize: '0.9rem', color: '#555', cursor: 'pointer', marginTop: 4 }}>
            <input type="checkbox" checked={form.is_proxy} onChange={set('is_proxy')} style={{ width: 18, height: 18 }} />
            <span style={{ fontWeight: form.is_proxy ? 600 : 400, color: form.is_proxy ? '#dc2626' : '#555' }}>
              🎭 This is a PROXY / Playtest card (not an original)
            </span>
          </label>

        </div>

        {error && <p style={{ color: '#c00', fontSize: '0.85rem', margin: '12px 0 0' }}>{error}</p>}

        <div style={{ display: 'flex', gap: 10, marginTop: 20, justifyContent: 'flex-end' }}>
          <button
            onClick={onClose}
            style={{ padding: '7px 18px', borderRadius: 4, border: '1px solid #ccc', background: '#fff', cursor: 'pointer' }}
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            style={{ padding: '7px 18px', borderRadius: 4, border: 'none', background: '#4c6ef5', color: '#fff', fontWeight: 600, cursor: 'pointer' }}
          >
            {saving ? 'Saving…' : 'Save Changes'}
          </button>
        </div>
      </div>
    </div>
  );
}
