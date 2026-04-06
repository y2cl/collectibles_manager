import { useState, useRef, useEffect } from 'react';
import { useOwnerStore } from '../../store/ownerStore';
import { exportApi } from '../../api/export';
import { useQueryClient } from '@tanstack/react-query';

// ── Target field definitions per collection type ──────────────────────────────

const MTG_TARGET_FIELDS = [
  'Name', 'Set Name', 'Set Code', 'Collector Number', 'Scryfall ID',
  'Quantity', 'Foil', 'Etched', 'Signed', 'Altered', 'Purchase Price', 'Notes',
];

const POKEMON_TARGET_FIELDS = [
  'Name', 'Set Name', 'Set Code', 'Card Number', 'Quantity', 'Variant', 'Purchase Price', 'Notes',
];

const SPORTS_TARGET_FIELDS = [
  'Name', 'Set', 'Year', 'Card Number', 'Sport', 'Insert',
  'Grading Company', 'Grade', 'Serial Number', 'Print Run', 'Rookie Card',
  'Quantity', 'Purchase Price', 'Notes',
];

const COLLECTIBLES_TARGET_FIELDS = [
  'Name', 'Series', 'Manufacturer', 'UPC', 'Condition', 'Year',
  'Quantity', 'Purchase Price', 'Notes',
];

// Scope label → game string sent to the backend
const SCOPE_TO_GAME: Record<string, string> = {
  'Magic: The Gathering': 'Magic: The Gathering',
  'Pokémon':              'Pokémon',
  'Sports Cards':         'Sports Cards',
  'Collectibles':         'Collectibles',
};

// Aliases: normalized source header → target field label
// Handles common non-obvious column name variants
const HEADER_ALIASES: Record<string, string> = {
  // MTG / Pokémon
  'cardname':         'Name',
  'set':              'Set Name',
  'setname':          'Set Name',
  'setcode':          'Set Code',
  'collectornumber':  'Collector Number',
  'cardnumber':       'Collector Number',
  'no':               'Collector Number',
  'scryfallid':       'Scryfall ID',
  'qty':              'Quantity',
  'foil':             'Foil',
  'etched':           'Etched',
  'signed':           'Signed',
  'altered':          'Altered',
  'paid':             'Purchase Price',
  'price':            'Purchase Price',
  'purchaseprice':    'Purchase Price',
  'note':             'Notes',
  'comments':         'Notes',
  'variant':          'Variant',
  'finish':           'Variant',
  // Sports Cards
  'player':           'Name',
  'playername':       'Name',
  'team':             'Set',
  'sport':            'Sport',
  'insert':           'Insert',
  'parallel':         'Insert',
  'gradingcompany':   'Grading Company',
  'grader':           'Grading Company',
  'psa':              'Grading Company',
  'bgs':              'Grading Company',
  'grade':            'Grade',
  'gradevalue':       'Grade',
  'serialnumber':     'Serial Number',
  'serial':           'Serial Number',
  'cert':             'Serial Number',
  'certnumber':       'Serial Number',
  'printrun':         'Print Run',
  'numbered':         'Print Run',
  'rookie':           'Rookie Card',
  'rc':               'Rookie Card',
  'rookiecard':       'Rookie Card',
  // Collectibles
  'series':           'Series',
  'lineseries':       'Series',
  'line':             'Series',
  'manufacturer':     'Manufacturer',
  'brand':            'Manufacturer',
  'upc':              'UPC',
  'barcode':          'UPC',
  'condition':        'Condition',
};

// ── CSV header parsing ────────────────────────────────────────────────────────

function parseCSVHeaders(text: string): string[] {
  const firstLine = text.split(/\r?\n/)[0] ?? '';
  const headers: string[] = [];
  let cur = '';
  let inQuotes = false;
  for (const ch of firstLine) {
    if (ch === '"') { inQuotes = !inQuotes; }
    else if (ch === ',' && !inQuotes) { headers.push(cur.trim()); cur = ''; }
    else { cur += ch; }
  }
  headers.push(cur.trim());
  return headers.filter((h) => h.length > 0);
}

function normalizeHeader(h: string): string {
  return h.toLowerCase().replace(/[^a-z0-9]/g, '');
}

function buildAutoMap(sourceHeaders: string[], targetFields: string[]): Record<string, string> {
  const usedSources = new Set<string>();
  const map: Record<string, string> = {};
  for (const field of targetFields) {
    const normField = normalizeHeader(field);
    let matched = '';
    for (const h of sourceHeaders) {
      if (usedSources.has(h)) continue;
      const normH = normalizeHeader(h);
      if (normH === normField || HEADER_ALIASES[normH] === field) {
        matched = h;
        break;
      }
    }
    map[field] = matched;
    if (matched) usedSources.add(matched);
  }
  return map;
}

// ── Types ─────────────────────────────────────────────────────────────────────

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

interface Props {
  scope: string;
}

// ── Component ─────────────────────────────────────────────────────────────────

export default function ImportExportTab({ scope }: Props) {
  const { currentOwnerId, currentProfileId } = useOwnerStore();
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);

  const [importing, setImporting]         = useState(false);
  const [importResult, setImportResult]   = useState<{ imported: number; ambiguous: number } | null>(null);
  const [error, setError]                 = useState('');

  // Streaming progress state
  interface ImportProgress {
    current: number;
    total: number;
    name: string;
    status: 'fetching' | 'searching' | 'imported' | 'ambiguous' | 'skipped' | 'error' | '';
  }
  const [importProgress, setImportProgress] = useState<ImportProgress | null>(null);

  // Header mapper state
  const [sourceHeaders, setSourceHeaders] = useState<string[]>([]);
  const [headerMap, setHeaderMap]         = useState<Record<string, string>>({});

  // Ambiguity resolution state
  const [ambiguities, setAmbiguities]     = useState<Ambiguity[]>([]);
  const [selections, setSelections]       = useState<Record<number, number>>({});
  const [resolving, setResolving]         = useState(false);
  const [resolveMsg, setResolveMsg]       = useState('');
  const [loadingAmbig, setLoadingAmbig]   = useState(false);
  const [clearingAmbig, setClearingAmbig] = useState(false);

  // Inner sub-tab: 'import' | 'history'
  const [innerTab, setInnerTab] = useState<'import' | 'history'>('import');

  // Previous imports state
  interface ImportHistoryRow {
    id: number;
    filename: string;
    game: string;
    imported_count: number;
    ambiguous_count: number;
    card_count: number;
    timestamp: string | null;
  }
  const [historyRows, setHistoryRows]         = useState<ImportHistoryRow[]>([]);
  const [historyLoading, setHistoryLoading]   = useState(false);
  const [historyError, setHistoryError]       = useState('');
  const [deletingId, setDeletingId]           = useState<number | null>(null);

  const loadHistory = async () => {
    if (!currentOwnerId) return;
    setHistoryLoading(true);
    setHistoryError('');
    try {
      const data = await exportApi.getImportHistory(currentOwnerId, currentProfileId);
      setHistoryRows(data as ImportHistoryRow[]);
    } catch (e: unknown) {
      setHistoryError(e instanceof Error ? e.message : 'Failed to load history');
    } finally {
      setHistoryLoading(false);
    }
  };

  const handleDeleteImport = async (row: ImportHistoryRow) => {
    if (!currentOwnerId) return;
    const msg = `Delete this import and remove ${row.card_count} card(s) from your collection?\n\n"${row.filename}" — ${row.card_count} card(s)\n\nThis cannot be undone.`;
    if (!window.confirm(msg)) return;
    setDeletingId(row.id);
    try {
      await exportApi.deleteImport(currentOwnerId, row.id);
      setHistoryRows((prev) => prev.filter((r) => r.id !== row.id));
      qc.invalidateQueries({ queryKey: ['collection', currentOwnerId] });
    } catch (e: unknown) {
      setHistoryError(e instanceof Error ? e.message : 'Failed to delete import');
    } finally {
      setDeletingId(null);
    }
  };

  // Reload history whenever the user switches to the history sub-tab
  useEffect(() => {
    if (innerTab === 'history') {
      void loadHistory();
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [innerTab, currentOwnerId, currentProfileId]);

  // Reset inner tab on scope change
  useEffect(() => {
    setInnerTab('import');
  }, [scope]);

  const isMtg         = scope === 'Magic: The Gathering';
  const isSportsCards = scope === 'Sports Cards';

  const targetFields = isMtg
    ? MTG_TARGET_FIELDS
    : scope === 'Pokémon'
      ? POKEMON_TARGET_FIELDS
      : isSportsCards
        ? SPORTS_TARGET_FIELDS
        : COLLECTIBLES_TARGET_FIELDS;

  // Reset mapper when scope changes
  useEffect(() => {
    setSourceHeaders([]);
    setHeaderMap({});
    setImportResult(null);
    setImportProgress(null);
    setError('');
    if (fileRef.current) fileRef.current.value = '';
  }, [scope]);

  const btnStyle: React.CSSProperties = {
    padding: '6px 14px', borderRadius: 4, border: 'none', cursor: 'pointer', fontSize: '0.85rem',
  };

  // ── File selection: parse headers and auto-map ─────────────────────────────
  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setImportResult(null);
    setError('');
    setResolveMsg('');
    const file = e.target.files?.[0];
    if (!file) {
      setSourceHeaders([]);
      setHeaderMap({});
      return;
    }
    const reader = new FileReader();
    reader.onload = (ev) => {
      const text = (ev.target?.result as string) ?? '';
      const headers = parseCSVHeaders(text);
      setSourceHeaders(headers);
      setHeaderMap(buildAutoMap(headers, targetFields));
    };
    reader.readAsText(file);
  };

  // ── Import (streaming SSE) ─────────────────────────────────────────────────
  const handleImport = async () => {
    const file = fileRef.current?.files?.[0];
    if (!file || !currentOwnerId) return;
    setImporting(true);
    setImportProgress(null);
    setImportResult(null);
    setError('');
    setResolveMsg('');

    try {
      const form = new FormData();
      form.append('file', file);
      form.append('owner_id', currentOwnerId);
      form.append('profile_id', currentProfileId);
      const activeMapping = Object.fromEntries(
        Object.entries(headerMap).filter(([, v]) => v !== '')
      );
      if (Object.keys(activeMapping).length > 0) {
        form.append('column_mapping', JSON.stringify(activeMapping));
      }
      const game = SCOPE_TO_GAME[scope];
      if (game) form.append('game', game);

      const response = await fetch('/api/import/csv/stream', { method: 'POST', body: form });
      if (!response.ok) throw new Error(`Server error ${response.status}`);
      if (!response.body) throw new Error('Streaming not supported');

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      // eslint-disable-next-line no-constant-condition
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        // SSE lines end with \n; events separated by \n\n
        const lines = buffer.split('\n');
        buffer = lines.pop() ?? '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const event = JSON.parse(line.slice(6)) as {
              type: string;
              total?: number;
              current?: number;
              name?: string;
              status?: ImportProgress['status'];
              imported?: number;
              ambiguous?: number;
              ambiguities?: Ambiguity[];
              message?: string;
            };

            if (event.type === 'start') {
              setImportProgress({ current: 0, total: event.total ?? 0, name: '', status: '' });

            } else if (event.type === 'progress') {
              setImportProgress({
                current: event.current ?? 0,
                total:   event.total   ?? 0,
                name:    event.name    ?? '',
                status:  event.status  ?? '',
              });

            } else if (event.type === 'done') {
              setImportResult({ imported: event.imported ?? 0, ambiguous: event.ambiguous ?? 0 });
              if (event.ambiguities?.length) {
                setAmbiguities(event.ambiguities);
                setSelections({});
              } else {
                setAmbiguities([]);
              }
              qc.invalidateQueries({ queryKey: ['collection', currentOwnerId] });

            } else if (event.type === 'error') {
              setError(event.message ?? 'Import error');
            }
          } catch { /* malformed event line — skip */ }
        }
      }
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Import failed');
    } finally {
      setImporting(false);
      setImportProgress(null);
    }
  };

  // ── Clear all pending ambiguities ──────────────────────────────────────────
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

  // ── Load pending ambiguities ───────────────────────────────────────────────
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

  // ── Resolve ────────────────────────────────────────────────────────────────
  const handleResolve = async () => {
    if (!currentOwnerId) return;
    setResolving(true);
    setError('');
    try {
      const resolutions = Object.entries(selections).map(([ambId, candidateIdx]) => {
        const amb = ambiguities.find((a) => a.id === Number(ambId))!;
        return {
          ambiguity_id:       Number(ambId),
          selected_candidate: candidateIdx >= 0 ? amb.candidates[candidateIdx] : null,
          quantity:           Number(amb.row_data.quantity) || 1,
          variant:            String(amb.row_data.variant  ?? ''),
          paid:               Number(amb.row_data.paid     ?? 0),
        };
      });
      const skipped = Object.values(selections).filter((v) => v === -1).length;
      await exportApi.resolveAmbiguities(currentOwnerId, currentProfileId, resolutions);
      setResolveMsg(
        `Added ${resolutions.length} card(s).` + (skipped ? ` Skipped ${skipped}.` : '')
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

  // ── Export ─────────────────────────────────────────────────────────────────
  const handleExportManabox = () => {
    if (!currentOwnerId) return;
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = '/api/export/manabox';
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

  const MTG_TEMPLATE_HEADERS      = 'Name,Set,Set Code,Collector Number,Scryfall_ID,Quantity,Foil,Etched,Signed,Altered,Notes';
  const POKEMON_TEMPLATE_HEADERS  = 'Name,Set Name,Set Code,Card Number,Quantity,Variant,Purchase Price,Notes';
  const SPORTS_TEMPLATE_HEADERS   = 'Name,Set,Year,Card Number,Sport,Insert,Grading Company,Grade,Serial Number,Print Run,Rookie Card,Quantity,Purchase Price,Notes';
  const COLLECT_TEMPLATE_HEADERS  = 'Name,Series,Manufacturer,UPC,Condition,Year,Quantity,Purchase Price,Notes';

  const downloadTemplate = (headers: string, filename: string) => {
    const blob = new Blob([headers + '\n'], { type: 'text/csv' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = filename;
    a.click();
  };

  // ── Render ─────────────────────────────────────────────────────────────────
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>

      {/* ── Inner sub-tab switcher ── */}
      <div style={{ display: 'flex', gap: 0, borderBottom: '2px solid #e0e4ef', marginBottom: -8 }}>
        {(['import', 'history'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setInnerTab(tab)}
            style={{
              padding: '7px 18px',
              background: 'none',
              border: 'none',
              borderBottom: innerTab === tab ? '2px solid #4c6ef5' : '2px solid transparent',
              marginBottom: -2,
              cursor: 'pointer',
              fontWeight: innerTab === tab ? 700 : 400,
              color: innerTab === tab ? '#4c6ef5' : '#666',
              fontSize: '0.88rem',
            }}
          >
            {tab === 'import' ? 'Import / Export' : '📋 Previous Imports'}
          </button>
        ))}
      </div>

      {/* ── Previous Imports panel ── */}
      {innerTab === 'history' && (
        <section>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
            <h3 style={{ margin: 0 }}>Previous Imports</h3>
            <button
              onClick={() => void loadHistory()}
              disabled={historyLoading}
              style={{ ...btnStyle, background: '#f0f2fa', color: '#4c6ef5', border: '1px solid #c5cdf5', fontSize: '0.78rem' }}
            >
              {historyLoading ? 'Loading…' : '↺ Refresh'}
            </button>
          </div>

          {historyError && <p style={{ color: '#c0392b', marginBottom: 12 }}>{historyError}</p>}

          {!historyLoading && historyRows.length === 0 && (
            <p style={{ color: '#888', fontSize: '0.85rem' }}>No imports recorded yet.</p>
          )}

          {historyRows.length > 0 && (
            <div style={{ border: '1px solid #e0e4ef', borderRadius: 6, overflow: 'hidden', fontSize: '0.83rem' }}>
              {/* Header row */}
              <div style={{
                display: 'grid',
                gridTemplateColumns: '1fr 110px 70px 70px 140px 130px',
                background: '#f5f7fb',
                padding: '7px 12px',
                borderBottom: '1px solid #e0e4ef',
                fontWeight: 600,
                color: '#555',
                gap: 8,
              }}>
                <span>File</span>
                <span>Game</span>
                <span style={{ textAlign: 'center' }}>Cards</span>
                <span style={{ textAlign: 'center' }}>Pending</span>
                <span>Date</span>
                <span></span>
              </div>

              {historyRows.map((row, i) => (
                <div
                  key={row.id}
                  style={{
                    display: 'grid',
                    gridTemplateColumns: '1fr 110px 70px 70px 140px 130px',
                    padding: '8px 12px',
                    alignItems: 'center',
                    gap: 8,
                    background: i % 2 === 0 ? '#fff' : '#fafbff',
                    borderBottom: i < historyRows.length - 1 ? '1px solid #f0f2fa' : undefined,
                  }}
                >
                  <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', color: '#333' }} title={row.filename}>
                    {row.filename || '(unnamed)'}
                  </span>
                  <span style={{ color: '#555', fontSize: '0.78rem' }}>{row.game || '—'}</span>
                  <span style={{ textAlign: 'center', color: '#2b7a2b', fontWeight: 600 }}>{row.card_count}</span>
                  <span style={{ textAlign: 'center', color: row.ambiguous_count > 0 ? '#e67e22' : '#aaa' }}>
                    {row.ambiguous_count > 0 ? row.ambiguous_count : '—'}
                  </span>
                  <span style={{ color: '#666', fontSize: '0.78rem' }}>
                    {row.timestamp ? new Date(row.timestamp).toLocaleString() : '—'}
                  </span>
                  <div style={{ display: 'flex', gap: 6 }}>
                    <a
                      href={exportApi.importFileUrl(currentOwnerId ?? '', row.id)}
                      download={row.filename || 'import.csv'}
                      style={{
                        ...btnStyle,
                        background: '#f0f2fa',
                        color: '#4c6ef5',
                        border: '1px solid #c5cdf5',
                        textDecoration: 'none',
                        display: 'inline-block',
                        fontSize: '0.78rem',
                        padding: '4px 10px',
                      }}
                      title="Download original import file"
                    >
                      ⬇
                    </a>
                    <button
                      onClick={() => handleDeleteImport(row)}
                      disabled={deletingId === row.id}
                      style={{
                        ...btnStyle,
                        background: '#fff',
                        color: '#fa5252',
                        border: '1px solid #fa5252',
                        fontSize: '0.78rem',
                        padding: '4px 10px',
                        opacity: deletingId === row.id ? 0.5 : 1,
                      }}
                      title={`Undo import — removes ${row.card_count} card(s)`}
                    >
                      {deletingId === row.id ? '…' : '✕ Undo'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      )}

      {/* ── Import / Export panel ── */}
      {innerTab === 'import' && (
      <><section>
        <h3 style={{ marginTop: 0 }}>Import CSV</h3>

        {/* Per-scope format guides */}
        {isMtg && (
          <>
            <details style={{ marginBottom: 12, fontSize: '0.82rem', color: '#555' }}>
              <summary style={{ cursor: 'pointer', fontWeight: 600, color: '#4c6ef5' }}>
                Standard MTG import format &amp; field guide
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
                <button onClick={() => downloadTemplate(MTG_TEMPLATE_HEADERS, 'mtg_import_template.csv')} style={{ ...btnStyle, background: '#4c6ef5', color: '#fff', fontSize: '0.78rem' }}>
                  ⬇ Download blank template
                </button>
              </div>
            </details>

            <details style={{ marginBottom: 12, fontSize: '0.82rem', color: '#555' }}>
              <summary style={{ cursor: 'pointer', fontWeight: 600, color: '#4c6ef5' }}>
                Manabox import format
              </summary>
              <div style={{ marginTop: 8, lineHeight: 1.6 }}>
                <p style={{ margin: '0 0 6px' }}>
                  Export your Manabox collection as CSV and upload it here. The importer uses the
                  Scryfall ID column for fast, unambiguous matching.
                </p>
                <ul style={{ margin: '0 0 8px 16px', padding: 0 }}>
                  <li><strong>Name / Set code / Collector number</strong> — used as fallback when Scryfall ID is absent.</li>
                  <li><strong>Foil</strong> — Manabox "foil"/"normal" values are handled automatically.</li>
                  <li><strong>Purchase price</strong> — stored as the <em>Paid</em> field.</li>
                  <li><strong>Altered</strong> — Manabox "altered"/"normal" values are handled automatically.</li>
                  <li>Rarity, Language, Condition, ManaBox ID, and Purchase price currency are ignored.</li>
                </ul>
                <code style={{ display: 'block', background: '#f5f7fb', padding: '6px 10px', borderRadius: 4, fontSize: '0.78rem', overflowX: 'auto', whiteSpace: 'nowrap' }}>
                  Name,Set code,Set name,Collector number,Foil,Rarity,Quantity,ManaBox ID,Scryfall ID,Purchase price,Misprint,Altered,Condition,Language,Purchase price currency
                </code>
              </div>
            </details>
          </>
        )}

        {scope === 'Pokémon' && (
          <details style={{ marginBottom: 12, fontSize: '0.82rem', color: '#555' }}>
            <summary style={{ cursor: 'pointer', fontWeight: 600, color: '#4c6ef5' }}>
              Pokémon import format &amp; field guide
            </summary>
            <div style={{ marginTop: 8, lineHeight: 1.6 }}>
              <code style={{ display: 'block', background: '#f5f7fb', padding: '6px 10px', borderRadius: 4, marginBottom: 8, fontSize: '0.78rem', overflowX: 'auto', whiteSpace: 'nowrap' }}>
                {POKEMON_TEMPLATE_HEADERS}
              </code>
              <ul style={{ margin: '0 0 8px 16px', padding: 0 }}>
                <li><strong>Name</strong> — card name (required), e.g. <em>Charizard</em>.</li>
                <li><strong>Set Name / Set Code</strong> — e.g. <em>Base Set</em> / <em>base1</em>. Providing both improves match accuracy.</li>
                <li><strong>Card Number</strong> — the collector number printed on the card, e.g. <em>4/102</em>.</li>
                <li><strong>Variant</strong> — e.g. <em>holofoil</em>, <em>reverse holo</em>, <em>normal</em>.</li>
                <li><strong>Purchase Price</strong> — what you paid; stored in the Paid field.</li>
                <li>All columns are optional except <strong>Name</strong>.</li>
              </ul>
              <button onClick={() => downloadTemplate(POKEMON_TEMPLATE_HEADERS, 'pokemon_import_template.csv')} style={{ ...btnStyle, background: '#4c6ef5', color: '#fff', fontSize: '0.78rem' }}>
                ⬇ Download blank template
              </button>
            </div>
          </details>
        )}

        {scope === 'Sports Cards' && (
          <details style={{ marginBottom: 12, fontSize: '0.82rem', color: '#555' }}>
            <summary style={{ cursor: 'pointer', fontWeight: 600, color: '#4c6ef5' }}>
              Sports Cards import format &amp; field guide
            </summary>
            <div style={{ marginTop: 8, lineHeight: 1.6 }}>
              <code style={{ display: 'block', background: '#f5f7fb', padding: '6px 10px', borderRadius: 4, marginBottom: 8, fontSize: '0.78rem', overflowX: 'auto', whiteSpace: 'nowrap' }}>
                {SPORTS_TEMPLATE_HEADERS}
              </code>
              <ul style={{ margin: '0 0 8px 16px', padding: 0 }}>
                <li><strong>Name</strong> — player name (required), e.g. <em>Mike Trout</em>.</li>
                <li><strong>Set</strong> — product/set name, e.g. <em>2021 Topps Chrome</em>.</li>
                <li><strong>Sport</strong> — <em>baseball</em>, <em>football</em>, <em>basketball</em>, <em>hockey</em>, <em>soccer</em>, or <em>other</em>.</li>
                <li><strong>Insert</strong> — parallel or insert name, e.g. <em>Refractor</em>, <em>Gold</em>.</li>
                <li><strong>Grading Company</strong> — e.g. <em>PSA</em>, <em>BGS</em>, <em>SGC</em>. Leave blank for raw cards.</li>
                <li><strong>Grade</strong> — numeric grade, e.g. <em>9</em>, <em>9.5</em>, <em>10</em>.</li>
                <li><strong>Serial Number</strong> — grading certification number.</li>
                <li><strong>Print Run</strong> — serialized print run, e.g. <em>23/99</em>.</li>
                <li><strong>Rookie Card</strong> — <em>yes</em> or <em>no</em>.</li>
                <li><strong>Purchase Price</strong> — what you paid; stored in the Paid field.</li>
                <li>All columns are optional except <strong>Name</strong>.</li>
              </ul>
              <button onClick={() => downloadTemplate(SPORTS_TEMPLATE_HEADERS, 'sports_cards_import_template.csv')} style={{ ...btnStyle, background: '#4c6ef5', color: '#fff', fontSize: '0.78rem' }}>
                ⬇ Download blank template
              </button>
            </div>
          </details>
        )}

        {scope === 'Collectibles' && (
          <details style={{ marginBottom: 12, fontSize: '0.82rem', color: '#555' }}>
            <summary style={{ cursor: 'pointer', fontWeight: 600, color: '#4c6ef5' }}>
              Collectibles import format &amp; field guide
            </summary>
            <div style={{ marginTop: 8, lineHeight: 1.6 }}>
              <code style={{ display: 'block', background: '#f5f7fb', padding: '6px 10px', borderRadius: 4, marginBottom: 8, fontSize: '0.78rem', overflowX: 'auto', whiteSpace: 'nowrap' }}>
                {COLLECT_TEMPLATE_HEADERS}
              </code>
              <ul style={{ margin: '0 0 8px 16px', padding: 0 }}>
                <li><strong>Name</strong> — item name (required), e.g. <em>Optimus Prime G1</em>.</li>
                <li><strong>Series</strong> — product line or series, e.g. <em>Generation 1</em>.</li>
                <li><strong>Manufacturer</strong> — brand or maker, e.g. <em>Hasbro</em>.</li>
                <li><strong>UPC</strong> — barcode / UPC or EAN number.</li>
                <li><strong>Condition</strong> — e.g. <em>New</em>, <em>Like New</em>, <em>Very Good</em>, <em>Good</em>, <em>Acceptable</em>, <em>Poor</em>.</li>
                <li><strong>Year</strong> — release or production year.</li>
                <li><strong>Purchase Price</strong> — what you paid; stored in the Paid field.</li>
                <li>All columns are optional except <strong>Name</strong>.</li>
              </ul>
              <button onClick={() => downloadTemplate(COLLECT_TEMPLATE_HEADERS, 'collectibles_import_template.csv')} style={{ ...btnStyle, background: '#4c6ef5', color: '#fff', fontSize: '0.78rem' }}>
                ⬇ Download blank template
              </button>
            </div>
          </details>
        )}

        {/* File picker */}
        <div style={{ marginBottom: 12 }}>
          <input type="file" accept=".csv" ref={fileRef} onChange={handleFileChange} />
        </div>

        {/* ── Header mapper ── */}
        {sourceHeaders.length > 0 && (
          <div style={{ marginBottom: 12 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
              <span style={{ fontSize: '0.82rem', fontWeight: 600, color: '#444' }}>
                Column Mapping
                <span style={{ fontSize: '0.75rem', fontWeight: 400, color: '#888', marginLeft: 6 }}>
                  — map your file's columns to the expected fields
                </span>
              </span>
              <button
                onClick={() => setHeaderMap(buildAutoMap(sourceHeaders, targetFields))}
                style={{ ...btnStyle, fontSize: '0.75rem', background: '#f0f2fa', color: '#4c6ef5', border: '1px solid #c5cdf5', padding: '3px 10px' }}
              >
                Auto-detect
              </button>
            </div>
            <div style={{ border: '1px solid #e0e4ef', borderRadius: 6, overflow: 'hidden', fontSize: '0.82rem' }}>
              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', background: '#f5f7fb', padding: '6px 10px', borderBottom: '1px solid #e0e4ef', fontWeight: 600, color: '#555' }}>
                <span>Target Field</span>
                <span>Source Column</span>
              </div>
              {targetFields.map((field, i) => {
                const mapped = !!headerMap[field];
                return (
                  <div
                    key={field}
                    style={{
                      display: 'grid', gridTemplateColumns: '1fr 1fr',
                      padding: '5px 10px', alignItems: 'center',
                      background: i % 2 === 0 ? '#fff' : '#fafbff',
                      borderBottom: i < targetFields.length - 1 ? '1px solid #f0f2fa' : undefined,
                    }}
                  >
                    <span style={{ color: '#333' }}>
                      {field}
                      {field === 'Name' && <span style={{ color: '#fa5252', marginLeft: 2 }}>*</span>}
                    </span>
                    <select
                      value={headerMap[field] ?? ''}
                      onChange={(e) => setHeaderMap((prev) => ({ ...prev, [field]: e.target.value }))}
                      style={{
                        padding: '3px 6px', borderRadius: 4, fontSize: '0.8rem',
                        border: `1px solid ${mapped ? '#b2d8b2' : '#ddd'}`,
                        background: mapped ? '#f6fff6' : '#fafafa',
                        color: mapped ? '#1a5c1a' : '#aaa',
                      }}
                    >
                      <option value="">— not mapped —</option>
                      {sourceHeaders.map((h) => (
                        <option key={h} value={h}>{h}</option>
                      ))}
                    </select>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Import / load-pending buttons */}
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <button
            onClick={handleImport}
            disabled={importing || !currentOwnerId || sourceHeaders.length === 0}
            style={{ ...btnStyle, background: sourceHeaders.length > 0 ? '#4c6ef5' : '#aaa', color: '#fff' }}
          >
            {importing ? 'Importing…' : 'Import'}
          </button>
          <button onClick={handleLoadAmbiguities} disabled={loadingAmbig || !currentOwnerId}
            style={{ ...btnStyle, background: '#f0f2fa', color: '#4c6ef5', border: '1px solid #c5cdf5' }}>
            {loadingAmbig ? 'Loading…' : 'Load pending'}
          </button>
        </div>

        {/* ── Progress bar ── */}
        {importing && importProgress && (
          <div style={{ marginTop: 12 }}>
            {/* Bar */}
            <div style={{
              background: '#e8ecf8', borderRadius: 6, height: 10, overflow: 'hidden', marginBottom: 6,
            }}>
              <div style={{
                height: '100%',
                borderRadius: 6,
                transition: 'width 0.12s ease',
                width: importProgress.total > 0
                  ? `${Math.round((importProgress.current / importProgress.total) * 100)}%`
                  : '0%',
                background: importProgress.status === 'error'     ? '#fa5252'
                          : importProgress.status === 'ambiguous' ? '#f59f00'
                          : '#4c6ef5',
              }} />
            </div>
            {/* Label row */}
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.78rem', color: '#555' }}>
              <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '70%' }}>
                {importProgress.status === 'fetching'  && '🔍 Fetching from Scryfall: '}
                {importProgress.status === 'searching' && '🔍 Searching: '}
                {importProgress.status === 'imported'  && '✓ '}
                {importProgress.status === 'ambiguous' && '⚠ Needs review: '}
                {importProgress.status === 'skipped'   && '— '}
                {importProgress.status === 'error'     && '✕ Error on: '}
                {importProgress.status === ''          && '⏳ '}
                <strong>{importProgress.name || '…'}</strong>
              </span>
              <span style={{ flexShrink: 0, marginLeft: 8, color: '#888' }}>
                {importProgress.current} / {importProgress.total}
                {importProgress.total > 0 &&
                  ` (${Math.round((importProgress.current / importProgress.total) * 100)}%)`}
              </span>
            </div>
          </div>
        )}

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
        <section style={{ marginTop: '1.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8, marginBottom: 12 }}>
            <h3 style={{ margin: 0 }}>
              Disambiguate Cards
              <span style={{ fontSize: '0.8rem', fontWeight: 400, color: '#888', marginLeft: 8 }}>
                {reviewedCount} / {ambiguities.length} reviewed
              </span>
            </h3>
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={handleClearAll} disabled={clearingAmbig}
                style={{ ...btnStyle, background: '#fff', color: '#fa5252', border: '1px solid #fa5252' }}>
                {clearingAmbig ? 'Clearing…' : 'Clear all'}
              </button>
              <button onClick={handleResolve} disabled={resolving || reviewedCount === 0}
                style={{ ...btnStyle, background: reviewedCount > 0 ? '#4c6ef5' : '#ccc', color: '#fff' }}>
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
                <div style={{ background: '#f5f7fb', padding: '8px 12px', borderBottom: '1px solid #e0e4ef', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>
                    {String(amb.row_data.name ?? '—')}
                    {amb.row_data.set_name
                      ? <span style={{ fontWeight: 400, color: '#888', marginLeft: 6 }}>({String(amb.row_data.set_name)})</span>
                      : null}
                  </span>
                  <span style={{ fontSize: '0.78rem', color: '#aaa' }}>{amb.candidates.length} candidate(s)</span>
                </div>
                <div style={{ padding: '8px 12px', display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {amb.candidates.map((c, idx) => {
                    const isSelected = selected === idx;
                    return (
                      <div key={idx} onClick={() => selectCandidate(amb.id, idx)}
                        style={{
                          display: 'flex', gap: 10, alignItems: 'center', padding: '6px 10px',
                          borderRadius: 5, cursor: 'pointer', transition: 'background 0.1s',
                          background: isSelected ? '#eef1fd' : '#fafbff',
                          border: `1px solid ${isSelected ? '#4c6ef5' : '#e8eaf5'}`,
                        }}
                      >
                        <input type="radio" readOnly checked={isSelected} style={{ marginTop: 1, flexShrink: 0 }} />
                        {c.image_url && <img src={c.image_url} alt={c.name} style={{ height: 48, borderRadius: 3, flexShrink: 0 }} />}
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
                  <div onClick={() => selectCandidate(amb.id, -1)}
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

          <button onClick={handleResolve} disabled={resolving || reviewedCount === 0}
            style={{ ...btnStyle, background: reviewedCount > 0 ? '#4c6ef5' : '#ccc', color: '#fff' }}>
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
          {isMtg && (
            <button onClick={handleExportManabox} disabled={!currentOwnerId}
              style={{ ...btnStyle, background: '#6c5ce7', color: '#fff' }}>
              ⬇ Export for Manabox
            </button>
          )}
          <button
            onClick={() => { if (currentOwnerId) window.location.href = exportApi.exportZipUrl(currentOwnerId); }}
            disabled={!currentOwnerId}
            style={{ ...btnStyle, background: '#555', color: '#fff' }}>
            ⬇ Export ZIP (all profiles)
          </button>
        </div>
      </section>
      </>) } {/* end innerTab === 'import' */}
    </div>
  );
}
