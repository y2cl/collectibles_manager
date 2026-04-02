import { useState, useRef } from 'react';
import { useOwnerStore } from '../../store/ownerStore';
import { exportApi } from '../../api/export';
import { useQueryClient } from '@tanstack/react-query';

interface Candidate {
  name?: string;
  set_name?: string;
  set_code?: string;
  card_number?: string;
  image_url?: string;
  price_usd?: number;
  price_usd_foil?: number;
  [key: string]: unknown;
}

interface Ambiguity {
  id: number;
  row_data: Record<string, unknown>;
  candidates: Candidate[];
}

export default function ImportExportTab() {
  const { currentOwnerId, currentProfileId } = useOwnerStore();
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);

  const [importing, setImporting]       = useState(false);
  const [importResult, setImportResult] = useState<{ imported: number; ambiguous: number } | null>(null);
  const [error, setError]               = useState('');

  // Ambiguity resolution state
  const [ambiguities, setAmbiguities]   = useState<Ambiguity[]>([]);
  const [selections, setSelections]     = useState<Record<number, number>>({}); // ambiguity_id → candidate index (-1 = skip)
  const [resolving, setResolving]       = useState(false);
  const [resolveMsg, setResolveMsg]     = useState('');
  const [loadingAmbig, setLoadingAmbig] = useState(false);
  const [clearingAmbig, setClearingAmbig] = useState(false);

  const btnStyle: React.CSSProperties = {
    padding: '6px 14px', borderRadius: 4, border: 'none', cursor: 'pointer', fontSize: '0.85rem',
  };

  // ── Import ────────────────────────────────────────────────────────────────
  const handleImport = async () => {
    const file = fileRef.current?.files?.[0];
    if (!file || !currentOwnerId) return;
    setImporting(true);
    setError('');
    setResolveMsg('');
    try {
      const result = await exportApi.importCsv(file, currentOwnerId, currentProfileId);
      setImportResult({ imported: result.imported, ambiguous: result.ambiguous });
      if (result.ambiguities?.length) {
        setAmbiguities(result.ambiguities as Ambiguity[]);
        setSelections({});
      } else {
        setAmbiguities([]);
      }
      qc.invalidateQueries({ queryKey: ['collection', currentOwnerId] });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Import failed');
    } finally {
      setImporting(false);
    }
  };

  // ── Clear all pending ambiguities ─────────────────────────────────────────
  const handleClearAll = async () => {
    if (!currentOwnerId) return;
    if (!window.confirm('Discard all pending cards? This cannot be undone.')) return;
    setClearingAmbig(true);
    try {
      await exportApi.clearAmbiguities(currentOwnerId, currentProfileId);
      setAmbiguities([]);
      setSelections([]);
      setResolveMsg('All pending cards cleared.');
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to clear');
    } finally {
      setClearingAmbig(false);
    }
  };

  // ── Load pending ambiguities (e.g. after navigating away) ─────────────────
  const handleLoadAmbiguities = async () => {
    if (!currentOwnerId) return;
    setLoadingAmbig(true);
    setError('');
    try {
      const data = await exportApi.getAmbiguities(currentOwnerId, currentProfileId);
      setAmbiguities((data as Ambiguity[]) ?? []);
      setSelections({});
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load pending cards');
    } finally {
      setLoadingAmbig(false);
    }
  };

  // ── Resolve ───────────────────────────────────────────────────────────────
  const handleResolve = async () => {
    if (!currentOwnerId) return;
    setResolving(true);
    setError('');
    try {
      const resolutions = Object.entries(selections)
        .map(([ambId, candidateIdx]) => {
          const amb = ambiguities.find((a) => a.id === Number(ambId))!;
          return {
            ambiguity_id:       Number(ambId),
            // null signals "skip" to the backend — it will delete the record without adding
            selected_candidate: candidateIdx >= 0 ? amb.candidates[candidateIdx] : null,
            quantity:           Number(amb.row_data.quantity) || 1,
            variant:            String(amb.row_data.variant  ?? ''),
            paid:               Number(amb.row_data.paid     ?? 0),
          };
        });

      const skipped = Object.values(selections).filter((v) => v === -1).length;
      await exportApi.resolveAmbiguities(currentOwnerId, currentProfileId, resolutions);
      setResolveMsg(
        `Added ${resolutions.length} card(s).` +
        (skipped ? ` Skipped ${skipped}.` : '')
      );
      setAmbiguities([]);
      setSelections({});
      qc.invalidateQueries({ queryKey: ['collection', currentOwnerId] });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Resolution failed');
    } finally {
      setResolving(false);
    }
  };

  const selectCandidate = (ambId: number, idx: number) =>
    setSelections((prev) => ({ ...prev, [ambId]: idx }));

  const reviewedCount = Object.keys(selections).length;

  // ── Export ────────────────────────────────────────────────────────────────
  const handleExportCsv = () => {
    if (!currentOwnerId) return;
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = '/api/export/csv';
    const addField = (name: string, value: string) => {
      const input = document.createElement('input');
      input.type = 'hidden'; input.name = name; input.value = value;
      form.appendChild(input);
    };
    addField('owner_id', currentOwnerId);
    addField('profile_id', currentProfileId);
    document.body.appendChild(form);
    form.submit();
    document.body.removeChild(form);
  };

  const MTG_TEMPLATE_HEADERS = 'Name,Set,Set Code,Collector Number,Scryfall_ID,Quantity,Foil,Etched,Signed,Altered,Notes';
  const downloadTemplate = () => {
    const blob = new Blob([MTG_TEMPLATE_HEADERS + '\n'], { type: 'text/csv' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'mtg_import_template.csv';
    a.click();
  };

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>

      {/* ── Import section ── */}
      <section>
        <h3 style={{ marginTop: 0 }}>Import CSV</h3>

        <details style={{ marginBottom: 12, fontSize: '0.82rem', color: '#555' }}>
          <summary style={{ cursor: 'pointer', fontWeight: 600, color: '#4c6ef5' }}>
            MTG import format &amp; field guide
          </summary>
          <div style={{ marginTop: 8, lineHeight: 1.6 }}>
            <code style={{ display: 'block', background: '#f5f7fb', padding: '6px 10px', borderRadius: 4, marginBottom: 8, fontSize: '0.78rem', overflowX: 'auto', whiteSpace: 'nowrap' }}>
              {MTG_TEMPLATE_HEADERS}
            </code>
            <ul style={{ margin: '0 0 8px 16px', padding: 0 }}>
              <li><strong>Scryfall_ID</strong> — the card's Scryfall UUID. When present the importer fetches the card directly and skips fuzzy matching — no disambiguation needed.</li>
              <li><strong>Foil / Etched</strong> — <em>yes</em> or <em>no</em>. Etched takes priority. Both no → variant stored as <em>nonfoil</em>.</li>
              <li><strong>Signed / Altered</strong> — <em>yes</em> or <em>no</em>. Signed auto-fills the artist name. Use <strong>Notes</strong> for details.</li>
              <li>All columns are optional except <strong>Name</strong> (or <strong>Scryfall_ID</strong>).</li>
            </ul>
            <button onClick={downloadTemplate} style={{ ...btnStyle, background: '#4c6ef5', color: '#fff', fontSize: '0.78rem' }}>
              ⬇ Download blank template
            </button>
          </div>
        </details>

        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <input type="file" accept=".csv" ref={fileRef} />
          <button onClick={handleImport} disabled={importing || !currentOwnerId}
            style={{ ...btnStyle, background: '#4c6ef5', color: '#fff' }}>
            {importing ? 'Importing…' : 'Import'}
          </button>
          <button onClick={handleLoadAmbiguities} disabled={loadingAmbig || !currentOwnerId}
            style={{ ...btnStyle, background: '#f0f2fa', color: '#4c6ef5', border: '1px solid #c5cdf5' }}>
            {loadingAmbig ? 'Loading…' : 'Load pending'}
          </button>
        </div>

        {importResult && (
          <p style={{ color: '#2b7a2b', marginTop: 8, marginBottom: 0 }}>
            ✓ Imported {importResult.imported} card(s).
            {importResult.ambiguous > 0 &&
              <span style={{ color: '#e67e22' }}> {importResult.ambiguous} card(s) need disambiguation — review below.</span>}
          </p>
        )}
        {resolveMsg && <p style={{ color: '#2b7a2b', marginTop: 4 }}>✓ {resolveMsg}</p>}
        {error && <p style={{ color: '#c0392b', marginTop: 8 }}>{error}</p>}
      </section>

      {/* ── Disambiguation section ── */}
      {ambiguities.length > 0 && (
        <section>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8, marginBottom: 12 }}>
            <h3 style={{ margin: 0 }}>
              Disambiguate Cards
              <span style={{ fontSize: '0.8rem', fontWeight: 400, color: '#888', marginLeft: 8 }}>
                {reviewedCount} / {ambiguities.length} reviewed
              </span>
            </h3>
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                onClick={handleClearAll}
                disabled={clearingAmbig}
                style={{ ...btnStyle, background: '#fff', color: '#fa5252', border: '1px solid #fa5252' }}
              >
                {clearingAmbig ? 'Clearing…' : 'Clear all'}
              </button>
              <button
                onClick={handleResolve}
                disabled={resolving || reviewedCount === 0}
                style={{ ...btnStyle, background: reviewedCount > 0 ? '#4c6ef5' : '#ccc', color: '#fff' }}
              >
                {resolving ? 'Submitting…' : `Submit ${reviewedCount} selection(s)`}
              </button>
            </div>
          </div>
          <p style={{ margin: '0 0 12px', fontSize: '0.82rem', color: '#666' }}>
            Each card below matched multiple results. Select the correct version, or skip to leave it out of your collection.
          </p>

          {ambiguities.map((amb) => {
            const selected = selections[amb.id];
            return (
              <div key={amb.id} style={{ border: '1px solid #e0e4ef', borderRadius: 6, marginBottom: 12, overflow: 'hidden' }}>
                {/* Row header */}
                <div style={{ background: '#f5f7fb', padding: '8px 12px', borderBottom: '1px solid #e0e4ef', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>
                    {String(amb.row_data.name ?? '—')}
                    {amb.row_data.set_name ? <span style={{ fontWeight: 400, color: '#888', marginLeft: 6 }}>({String(amb.row_data.set_name)})</span> : null}
                  </span>
                  <span style={{ fontSize: '0.78rem', color: '#aaa' }}>
                    {amb.candidates.length} candidate(s)
                  </span>
                </div>

                {/* Candidates */}
                <div style={{ padding: '8px 12px', display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {amb.candidates.map((c, idx) => {
                    const isSelected = selected === idx;
                    return (
                      <div
                        key={idx}
                        onClick={() => selectCandidate(amb.id, idx)}
                        style={{
                          display: 'flex', gap: 10, alignItems: 'center', padding: '6px 10px',
                          borderRadius: 5, cursor: 'pointer', transition: 'background 0.1s',
                          background: isSelected ? '#eef1fd' : '#fafbff',
                          border: `1px solid ${isSelected ? '#4c6ef5' : '#e8eaf5'}`,
                        }}
                      >
                        <input type="radio" readOnly checked={isSelected} style={{ marginTop: 1, flexShrink: 0 }} />
                        {c.image_url && (
                          <img src={c.image_url} alt={c.name} style={{ height: 48, borderRadius: 3, flexShrink: 0 }} />
                        )}
                        <div style={{ flex: 1, fontSize: '0.82rem', lineHeight: 1.5 }}>
                          <div><strong>{c.name}</strong></div>
                          <div style={{ color: '#666' }}>
                            {c.set_name}{c.set_code ? ` (${c.set_code})` : ''}
                            {c.card_number ? ` #${c.card_number}` : ''}
                          </div>
                        </div>
                        <div style={{ fontSize: '0.82rem', textAlign: 'right', flexShrink: 0 }}>
                          {(c.price_usd ?? 0) > 0 && <div style={{ color: '#2b7a2b' }}>${Number(c.price_usd).toFixed(2)}</div>}
                          {(c.price_usd_foil ?? 0) > 0 && <div style={{ color: '#6c5ce7', fontSize: '0.75rem' }}>✨ ${Number(c.price_usd_foil).toFixed(2)}</div>}
                        </div>
                      </div>
                    );
                  })}

                  {/* Skip option */}
                  <div
                    onClick={() => selectCandidate(amb.id, -1)}
                    style={{
                      padding: '5px 10px', borderRadius: 5, cursor: 'pointer',
                      fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: 6,
                      background: selected === -1 ? '#fff5f5' : 'transparent',
                      border: `1px solid ${selected === -1 ? '#fa5252' : 'transparent'}`,
                      color: selected === -1 ? '#fa5252' : '#aaa',
                    }}
                  >
                    <input type="radio" readOnly checked={selected === -1} style={{ flexShrink: 0 }} />
                    Skip — don't add this card
                  </div>
                </div>
              </div>
            );
          })}

          <button
            onClick={handleResolve}
            disabled={resolving || reviewedCount === 0}
            style={{ ...btnStyle, background: reviewedCount > 0 ? '#4c6ef5' : '#ccc', color: '#fff' }}
          >
            {resolving ? 'Submitting…' : `Submit ${reviewedCount} selection(s)`}
          </button>
        </section>
      )}

      {/* ── Export section ── */}
      <section>
        <h3 style={{ marginTop: 0 }}>Export</h3>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button onClick={handleExportCsv} disabled={!currentOwnerId}
            style={{ ...btnStyle, background: '#2b7a2b', color: '#fff' }}>
            ⬇ Export CSV
          </button>
          <button
            onClick={() => { if (currentOwnerId) window.location.href = exportApi.exportZipUrl(currentOwnerId); }}
            disabled={!currentOwnerId}
            style={{ ...btnStyle, background: '#555', color: '#fff' }}>
            ⬇ Export ZIP (all profiles)
          </button>
        </div>
      </section>
    </div>
  );
}
