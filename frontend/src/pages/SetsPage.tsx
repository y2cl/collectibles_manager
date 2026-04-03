import { useState, useMemo } from 'react';
import { useNavigate } from 'react-router-dom';
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query';
import { useOwnerStore } from '../store/ownerStore';
import { setsApi } from '../api/sets';
import type { MtgSyncResult, CacheCardsResult, SportsSetRow, SportsCatalogEntry, SportsCatalogCreate, SportsCatalogUpdate } from '../api/sets';
import type { SetEntry } from '../types/settings';

// ─── Tab config ────────────────────────────────────────────────────────────────

type Tab = 'all' | 'mtg' | 'pokemon' | 'sports';

const TABS: { id: Tab; label: string; apiGame?: string }[] = [
  { id: 'all',     label: 'All' },
  { id: 'mtg',     label: '🧙 Magic: The Gathering', apiGame: 'Magic: The Gathering' },
  { id: 'pokemon', label: '⚡ Pokémon',               apiGame: 'Pokémon' },
  { id: 'sports',  label: '🏆 Sports Cards',          apiGame: 'Sports Cards' },
];

const MTG_SET_TYPES = ['All', 'core', 'expansion', 'masters', 'draft_innovation', 'commander', 'promo'];

// ─── Sorting ───────────────────────────────────────────────────────────────────

type SortKey = 'name' | 'code' | 'game' | 'year' | 'set_type' | 'card_count' | 'owned';
type SortDir = 'asc' | 'desc';

function sortSets(
  sets: SetEntry[],
  key: SortKey,
  dir: SortDir,
  ownedCounts: Record<string, number> = {},
): SetEntry[] {
  return [...sets].sort((a, b) => {
    if (key === 'owned') {
      const av = ownedCounts[a.code] ?? -1;
      const bv = ownedCounts[b.code] ?? -1;
      return dir === 'asc' ? av - bv : bv - av;
    }
    if (key === 'year') {
      const ad = a.released_at || a.year || '';
      const bd = b.released_at || b.year || '';
      const cmp = ad.localeCompare(bd);
      return dir === 'asc' ? cmp : -cmp;
    }
    if (key === 'card_count') {
      const av = parseInt(String(a[key] ?? ''), 10) || 0;
      const bv = parseInt(String(b[key] ?? ''), 10) || 0;
      return dir === 'asc' ? av - bv : bv - av;
    }
    const av = String((a[key] ?? '') as string);
    const bv = String((b[key] ?? '') as string);
    const cmp = av.localeCompare(bv, undefined, { sensitivity: 'base' });
    return dir === 'asc' ? cmp : -cmp;
  });
}

// ─── Small shared components ───────────────────────────────────────────────────

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (v: boolean) => void }) {
  return (
    <label style={{ display: 'flex', alignItems: 'center', gap: 7, cursor: 'pointer', userSelect: 'none', fontSize: '0.82rem' }}>
      <span
        onClick={() => onChange(!checked)}
        style={{
          position: 'relative', display: 'inline-block',
          width: 36, height: 20, borderRadius: 10,
          background: checked ? '#4c6ef5' : '#ccc', transition: 'background 0.2s', flexShrink: 0,
        }}
      >
        <span style={{
          position: 'absolute', top: 3, left: checked ? 19 : 3,
          width: 14, height: 14, borderRadius: '50%',
          background: '#fff', boxShadow: '0 1px 3px rgba(0,0,0,0.25)', transition: 'left 0.2s',
        }} />
      </span>
      <span style={{ color: checked ? '#3b5bdb' : '#666', fontWeight: checked ? 600 : 400 }}>{label}</span>
    </label>
  );
}

function SortableTh({ label, sortKey, current, dir, onSort, style }: {
  label: string; sortKey: SortKey; current: SortKey; dir: SortDir;
  onSort: (k: SortKey) => void; style?: React.CSSProperties;
}) {
  const active = sortKey === current;
  return (
    <th onClick={() => onSort(sortKey)} style={{
      padding: '6px 8px', cursor: 'pointer', userSelect: 'none', whiteSpace: 'nowrap',
      color: active ? '#4c6ef5' : 'inherit', ...style,
    }}>
      {label}
      <span style={{ marginLeft: 4, opacity: active ? 1 : 0.25, fontSize: '0.75em' }}>
        {active ? (dir === 'asc' ? '▲' : '▼') : '▲'}
      </span>
    </th>
  );
}

// ─── Sync status pill ─────────────────────────────────────────────────────────

function SyncStatus({ result, error }: { result: MtgSyncResult | null; error: string }) {
  if (error) return <span style={{ fontSize: '0.78rem', color: '#c00' }}>❌ {error}</span>;
  if (!result) return null;
  return (
    <span style={{
      fontSize: '0.78rem', color: '#1a7a2e', fontWeight: 500,
      background: '#d3f9d8', border: '1px solid #69db7c', borderRadius: 6, padding: '3px 10px',
    }}>
      ✅ {result.total.toLocaleString()} sets · {result.added} new · {result.updated} updated · {result.unchanged} unchanged
    </span>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function SetsPage() {
  const { currentOwnerId, currentProfileId } = useOwnerStore();
  const qc = useQueryClient();
  const navigate = useNavigate();

  // Tab
  const [activeTab, setActiveTab] = useState<Tab>('mtg');
  const tabCfg = TABS.find((t) => t.id === activeTab)!;

  // Shared filters
  const [search, setSearch] = useState('');
  const [setType, setSetType] = useState('All');
  const [year, setYear] = useState('');

  // MTG-only toggles
  const [showTokens, setShowTokens] = useState(false);
  const [showMemorabilia, setShowMemorabilia] = useState(false);
  const [showDigital, setShowDigital] = useState(false);

  // Sorting
  const [sortKey, setSortKey] = useState<SortKey>('year');
  const [sortDir, setSortDir] = useState<SortDir>('desc');
  const [ownedCounts, setOwnedCounts] = useState<Record<string, number>>({});

  const handleSort = (key: SortKey) => {
    if (key === sortKey) setSortDir((d) => (d === 'asc' ? 'desc' : 'asc'));
    else { setSortKey(key); setSortDir('asc'); }
  };

  const handleOwnedLoaded = (code: string, count: number) => {
    setOwnedCounts((prev) => (prev[code] === count ? prev : { ...prev, [code]: count }));
  };

  // MTG sync
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<MtgSyncResult | null>(null);
  const [syncError, setSyncError] = useState('');

  const handleSyncMtg = async () => {
    setSyncing(true); setSyncResult(null); setSyncError('');
    try {
      const r = await setsApi.syncMtgSets();
      setSyncResult(r);
      qc.invalidateQueries({ queryKey: ['sets'] });
    } catch (e: unknown) { setSyncError(e instanceof Error ? e.message : 'Sync failed'); }
    finally { setSyncing(false); }
  };

  // Pokémon sync
  const [syncingPkmn, setSyncingPkmn] = useState(false);
  const [syncResultPkmn, setSyncResultPkmn] = useState<MtgSyncResult | null>(null);
  const [syncErrorPkmn, setSyncErrorPkmn] = useState('');

  const handleSyncPkmn = async () => {
    setSyncingPkmn(true); setSyncResultPkmn(null); setSyncErrorPkmn('');
    try {
      const r = await setsApi.syncPokemonSets();
      setSyncResultPkmn(r);
      qc.invalidateQueries({ queryKey: ['sets'] });
    } catch (e: unknown) { setSyncErrorPkmn(e instanceof Error ? e.message : 'Sync failed'); }
    finally { setSyncingPkmn(false); }
  };

  // Sports filter
  const [sportFilter, setSportFilter] = useState('all');
  const SPORTS_FILTERS = [
    { value: 'all', label: 'All Sports' },
    { value: 'baseball',   label: '⚾ Baseball' },
    { value: 'football',   label: '🏈 Football' },
    { value: 'basketball', label: '🏀 Basketball' },
    { value: 'hockey',     label: '🏒 Hockey' },
    { value: 'soccer',     label: '⚽ Soccer' },
    { value: 'other',      label: '🃏 Other' },
  ];

  // Sports catalog modal state
  const [catalogModal, setCatalogModal] = useState<{
    open: boolean;
    entry?: SportsCatalogEntry | null;   // null = create, object = edit
    prefill?: Partial<SportsCatalogEntry>;
  }>({ open: false });

  const invalidateSports = () => {
    qc.invalidateQueries({ queryKey: ['sets', 'sports-summary'] });
  };

  const createMutation = useMutation({
    mutationFn: (payload: SportsCatalogCreate) => setsApi.createSportsSet(payload),
    onSuccess: invalidateSports,
  });
  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: SportsCatalogUpdate }) => setsApi.updateSportsSet(id, payload),
    onSuccess: invalidateSports,
  });
  const deleteMutation = useMutation({
    mutationFn: (id: number) => setsApi.deleteSportsSet(id),
    onSuccess: invalidateSports,
  });

  const handleCatalogSave = async (payload: SportsCatalogCreate | SportsCatalogUpdate, id?: number) => {
    if (id) {
      await updateMutation.mutateAsync({ id, payload: payload as SportsCatalogUpdate });
    } else {
      await createMutation.mutateAsync(payload as SportsCatalogCreate);
    }
  };

  const handleDeleteSet = (id: number) => {
    if (window.confirm('Delete this set from the catalog?')) {
      deleteMutation.mutate(id);
    }
  };

  const handleViewCards = (setName: string, insert?: string) => {
    const params = new URLSearchParams({ scope: 'Sports Cards', set: setName });
    if (insert) params.set('insert', insert);
    navigate(`/collection?${params.toString()}`);
  };

  // Sports summary query (only runs on sports tab)
  const { data: sportsData, isLoading: sportsLoading } = useQuery({
    queryKey: ['sets', 'sports-summary', currentOwnerId, currentProfileId, sportFilter],
    queryFn: () => setsApi.sportsSummary(currentOwnerId!, currentProfileId, sportFilter),
    enabled: activeTab === 'sports' && !!currentOwnerId,
    staleTime: 2 * 60 * 1000,
  });

  // Data queries
  const { data, isLoading } = useQuery({
    queryKey: ['sets', tabCfg.apiGame, search, setType, year],
    queryFn: () => setsApi.list({
      game: tabCfg.apiGame,
      search: search || undefined,
      set_type: activeTab === 'mtg' && setType !== 'All' ? setType : undefined,
      year: year || undefined,
      limit: 5000,
    }),
    staleTime: 10 * 60 * 1000,
  });

  const { data: cacheSummary } = useQuery({
    queryKey: ['sets', 'cache-summary'],
    queryFn: () => setsApi.cacheSummary(),
    staleTime: 60 * 1000,
  });
  const mtgCounts  = cacheSummary?.mtg     ?? {};
  const pkmnCounts = cacheSummary?.pokemon  ?? {};

  // Filter + sort
  const rawSets: SetEntry[] = data?.sets ?? [];
  const sets = useMemo(() => {
    const filtered = rawSets.filter((s) => {
      if (activeTab === 'mtg') {
        const t = (s.set_type ?? '').toLowerCase();
        const g = (s.game_type ?? '').toLowerCase();
        if (!showTokens && t === 'token') return false;
        if (!showMemorabilia && t === 'memorabilia') return false;
        if (!showDigital && g === 'digital') return false;
      }
      return true;
    });
    return sortSets(filtered, sortKey, sortDir, ownedCounts);
  }, [rawSets, sortKey, sortDir, ownedCounts, activeTab, showTokens, showMemorabilia, showDigital]);

  const showGameCol = activeTab === 'all';
  const showOwnedCol = !!currentOwnerId;

  const inputStyle: React.CSSProperties = {
    padding: '6px 10px', borderRadius: 4, border: '1px solid #ccc', fontSize: '0.9rem',
  };

  const syncBtnStyle = (color: string, loading: boolean): React.CSSProperties => ({
    padding: '6px 14px', fontSize: '0.85rem', fontWeight: 600,
    border: `1px solid ${color}`, borderRadius: 6,
    background: loading ? `${color}22` : color,
    color: loading ? color : '#fff',
    cursor: loading ? 'not-allowed' : 'pointer', whiteSpace: 'nowrap',
  });

  return (
    <div>
      <h1 style={{ margin: '0 0 1rem' }}>Sets Browser</h1>

      {/* ── Tabs ── */}
      <div style={{ display: 'flex', borderBottom: '2px solid #e0e4f0', marginBottom: '1rem', gap: 2 }}>
        {TABS.map((t) => (
          <button
            key={t.id}
            onClick={() => { setActiveTab(t.id); setSetType('All'); }}
            style={{
              padding: '8px 18px', fontSize: '0.88rem', fontWeight: activeTab === t.id ? 700 : 400,
              border: 'none', borderBottom: activeTab === t.id ? '3px solid #4c6ef5' : '3px solid transparent',
              background: 'none', color: activeTab === t.id ? '#4c6ef5' : '#555',
              cursor: 'pointer', marginBottom: -2, borderRadius: '4px 4px 0 0',
              transition: 'color 0.15s',
            }}
          >
            {t.label}
          </button>
        ))}
        <span style={{ marginLeft: 'auto', alignSelf: 'center', fontSize: '0.82rem', color: '#aaa', paddingRight: 4 }}>
          {sets.length.toLocaleString()} sets
        </span>
      </div>

      {/* ── Tab-specific controls ── */}
      {activeTab === 'mtg' && (
        <div style={{ marginBottom: '1rem', display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
            <button onClick={handleSyncMtg} disabled={syncing} style={syncBtnStyle('#4c6ef5', syncing)}>
              {syncing ? '⏳ Syncing…' : '☁️ Sync MTG Sets from Scryfall'}
            </button>
            {syncing && <span style={{ fontSize: '0.75rem', color: '#888' }}>This takes 10–30 seconds…</span>}
            <SyncStatus result={syncResult} error={syncError} />
          </div>
          <div style={{ display: 'flex', gap: 16, alignItems: 'center', flexWrap: 'wrap' }}>
            <span style={{ fontSize: '0.8rem', color: '#888', fontWeight: 500 }}>Show:</span>
            <Toggle label="Tokens"      checked={showTokens}      onChange={setShowTokens} />
            <Toggle label="Memorabilia" checked={showMemorabilia} onChange={setShowMemorabilia} />
            <Toggle label="Digital"     checked={showDigital}     onChange={setShowDigital} />
          </div>
        </div>
      )}

      {activeTab === 'pokemon' && (
        <div style={{ marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
          <button onClick={handleSyncPkmn} disabled={syncingPkmn} style={syncBtnStyle('#e53935', syncingPkmn)}>
            {syncingPkmn ? '⏳ Syncing…' : '☁️ Sync Pokémon Sets'}
          </button>
          {syncingPkmn && <span style={{ fontSize: '0.75rem', color: '#888' }}>Fetching all sets…</span>}
          <SyncStatus result={syncResultPkmn} error={syncErrorPkmn} />
        </div>
      )}

      {/* ── Shared filters ── */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: '1rem' }}>
        <input
          placeholder="Search sets…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ ...inputStyle, flex: '1 1 200px' }}
        />
        {activeTab === 'mtg' && (
          <select value={setType} onChange={(e) => setSetType(e.target.value)} style={inputStyle}>
            {MTG_SET_TYPES.map((t) => <option key={t}>{t}</option>)}
          </select>
        )}
        <input
          placeholder="Year (e.g. 2023)"
          value={year}
          onChange={(e) => setYear(e.target.value)}
          style={{ ...inputStyle, width: 130 }}
        />
      </div>

      {/* ── Sports Sets Table ── */}
      {activeTab === 'sports' && (
        <>
          <div style={{ marginBottom: '1rem', display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
            <select value={sportFilter} onChange={(e) => setSportFilter(e.target.value)} style={inputStyle}>
              {SPORTS_FILTERS.map(({ value, label }) => <option key={value} value={value}>{label}</option>)}
            </select>
            {currentOwnerId && (
              <button
                onClick={() => setCatalogModal({ open: true, entry: null })}
                style={{ padding: '6px 14px', fontSize: '0.85rem', fontWeight: 600, borderRadius: 6, border: '1px solid #4c6ef5', background: '#4c6ef5', color: '#fff', cursor: 'pointer' }}
              >
                + Add Set
              </button>
            )}
            {!currentOwnerId && (
              <span style={{ fontSize: '0.85rem', color: '#888' }}>Select an owner to see your sets.</span>
            )}
          </div>

          {sportsLoading && <p style={{ color: '#888' }}>Loading…</p>}
          {!sportsLoading && (sportsData?.sets.length ?? 0) === 0 && currentOwnerId && (
            <p style={{ color: '#888' }}>No Sports Cards sets found. Add cards on the Add to Collection page or click <strong>+ Add Set</strong> to define sets manually.</p>
          )}
          {(sportsData?.sets.length ?? 0) > 0 && (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
              <thead>
                <tr style={{ background: '#f5f7fb', textAlign: 'left' }}>
                  <th style={{ padding: '6px 8px', width: 24 }}></th>
                  <th style={{ padding: '6px 8px' }}>Set</th>
                  <th style={{ padding: '6px 8px' }}>Year</th>
                  <th style={{ padding: '6px 8px', textAlign: 'right' }}># in Set</th>
                  <th style={{ padding: '6px 8px', textAlign: 'right' }}># Owned</th>
                  <th style={{ padding: '6px 8px', textAlign: 'right' }}>Paid</th>
                  <th style={{ padding: '6px 8px', textAlign: 'right' }}>Value</th>
                  <th style={{ padding: '6px 8px', width: 90 }}></th>
                </tr>
              </thead>
              <tbody>
                {sportsData!.sets.map((s) => (
                  <SportsSetRow
                    key={`${s.set_name}-${s.year}`}
                    row={s}
                    onViewCards={handleViewCards}
                    onEdit={(row) => setCatalogModal({
                      open: true,
                      entry: row.catalog_id ? {
                        id: row.catalog_id,
                        sport: sportFilter !== 'all' ? sportFilter : null,
                        set_name: row.set_name, insert_name: '', year: row.year,
                        card_count: row.card_count, link: row.link, notes: row.notes,
                      } : undefined,
                      prefill: !row.catalog_id ? {
                        set_name: row.set_name, year: row.year,
                      } : undefined,
                    })}
                    onEditInsert={(row, ins) => setCatalogModal({
                      open: true,
                      entry: ins.catalog_id ? {
                        id: ins.catalog_id,
                        sport: sportFilter !== 'all' ? sportFilter : null,
                        set_name: row.set_name, insert_name: ins.insert, year: ins.year,
                        card_count: ins.card_count, link: ins.link, notes: ins.notes,
                      } : undefined,
                      prefill: !ins.catalog_id ? {
                        set_name: row.set_name, insert_name: ins.insert, year: ins.year,
                      } : undefined,
                    })}
                    onDelete={handleDeleteSet}
                    onDeleteInsert={handleDeleteSet}
                  />
                ))}
              </tbody>
            </table>
          )}

          {catalogModal.open && currentOwnerId && (
            <SportsCatalogModal
              entry={catalogModal.entry}
              prefill={catalogModal.prefill}
              ownerId={currentOwnerId}
              profileId={currentProfileId}
              defaultSport={sportFilter !== 'all' ? sportFilter : 'baseball'}
              onSave={handleCatalogSave}
              onClose={() => setCatalogModal({ open: false })}
            />
          )}
        </>
      )}

      {/* ── MTG / Pokémon / All Table ── */}
      {activeTab !== 'sports' && (
        <>
          {isLoading && <p style={{ color: '#888' }}>Loading sets…</p>}

          {!isLoading && sets.length === 0 && (
            <p style={{ color: '#888' }}>
              {activeTab === 'mtg'
                ? <>No sets found. Use <strong>☁️ Sync MTG Sets from Scryfall</strong> above to download the full set list.</>
                : activeTab === 'pokemon'
                ? <>No sets found. Use <strong>☁️ Sync Pokémon Sets</strong> above to download the full set list.</>
                : 'No sets found.'}
            </p>
          )}

          {sets.length > 0 && (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
              <thead>
                <tr style={{ background: '#f5f7fb', textAlign: 'left' }}>
                  <SortableTh label="Name"  sortKey="name"       current={sortKey} dir={sortDir} onSort={handleSort} />
                  <SortableTh label="Code"  sortKey="code"       current={sortKey} dir={sortDir} onSort={handleSort} />
                  {showGameCol && <SortableTh label="Game" sortKey="game" current={sortKey} dir={sortDir} onSort={handleSort} />}
                  <SortableTh label="Year"  sortKey="year"       current={sortKey} dir={sortDir} onSort={handleSort} />
                  <SortableTh label="Type"  sortKey="set_type"   current={sortKey} dir={sortDir} onSort={handleSort} />
                  <SortableTh label="Cards" sortKey="card_count" current={sortKey} dir={sortDir} onSort={handleSort} />
                  {showOwnedCol && (
                    <SortableTh label="Owned" sortKey="owned" current={sortKey} dir={sortDir} onSort={handleSort} />
                  )}
                  <th style={{ padding: '6px 8px', width: 150 }}>Cache</th>
                </tr>
              </thead>
              <tbody>
                {sets.map((s) => (
                  <SetRow
                    key={`${s.game}-${s.code}`}
                    set={s}
                    ownerId={currentOwnerId ?? ''}
                    profileId={currentProfileId}
                    showOwnedCol={showOwnedCol}
                    showGameCol={showGameCol}
                    onOwnedLoaded={handleOwnedLoaded}
                    cachedCount={
                      s.game === 'Magic: The Gathering'
                        ? (mtgCounts[s.code.toLowerCase()] ?? 0)
                        : (pkmnCounts[s.code.toLowerCase()] ?? 0)
                    }
                    onCached={() => qc.invalidateQueries({ queryKey: ['sets', 'cache-summary'] })}
                  />
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
    </div>
  );
}

// ─── SportsCatalogModal ───────────────────────────────────────────────────────

const SPORTS_OPTIONS = [
  { value: 'baseball',   label: '⚾ Baseball' },
  { value: 'football',   label: '🏈 Football' },
  { value: 'basketball', label: '🏀 Basketball' },
  { value: 'hockey',     label: '🏒 Hockey' },
  { value: 'soccer',     label: '⚽ Soccer' },
  { value: 'other',      label: '🃏 Other' },
];

interface ModalProps {
  entry?: SportsCatalogEntry | null;               // null/undefined = create mode
  prefill?: Partial<SportsCatalogEntry>;           // defaults for create mode
  ownerId: string;
  profileId: string;
  defaultSport?: string;
  onSave: (payload: SportsCatalogCreate | SportsCatalogUpdate, id?: number) => Promise<void>;
  onClose: () => void;
}

function SportsCatalogModal({ entry, prefill, ownerId, profileId, defaultSport, onSave, onClose }: ModalProps) {
  const isEdit = !!entry;
  const src = entry ?? prefill ?? {};
  const [form, setForm] = useState({
    sport:       (src as SportsCatalogEntry).sport ?? defaultSport ?? 'baseball',
    set_name:    src.set_name ?? '',
    insert_name: src.insert_name ?? '',
    year:        src.year ?? '',
    card_count:  src.card_count != null ? String(src.card_count) : '',
    link:        src.link ?? '',
    notes:       src.notes ?? '',
  });
  const [saving, setSaving] = useState(false);
  const [error, setError]   = useState('');

  const set = (field: string) =>
    (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement>) =>
      setForm((prev) => ({ ...prev, [field]: e.target.value }));

  const handleSave = async () => {
    if (!form.set_name.trim()) { setError('Set name is required.'); return; }
    setSaving(true); setError('');
    try {
      const cardCount = form.card_count.trim() ? parseInt(form.card_count, 10) || null : null;
      if (isEdit) {
        await onSave({
          sport:       form.sport || undefined,
          set_name:    form.set_name.trim(),
          insert_name: form.insert_name.trim(),
          year:        form.year.trim(),
          card_count:  cardCount,
          link:        form.link.trim(),
          notes:       form.notes.trim(),
        } as SportsCatalogUpdate, entry!.id);
      } else {
        await onSave({
          owner_id:    ownerId,
          profile_id:  profileId,
          sport:       form.sport || undefined,
          set_name:    form.set_name.trim(),
          insert_name: form.insert_name.trim(),
          year:        form.year.trim(),
          card_count:  cardCount,
          link:        form.link.trim(),
          notes:       form.notes.trim(),
        } as SportsCatalogCreate);
      }
      onClose();
    } catch {
      setError('Save failed — try again.');
      setSaving(false);
    }
  };

  const inp: React.CSSProperties = {
    padding: '6px 10px', borderRadius: 4, border: '1px solid #ccc',
    fontSize: '0.9rem', width: '100%', boxSizing: 'border-box',
  };
  const lbl: React.CSSProperties = {
    display: 'flex', flexDirection: 'column', gap: 4,
    fontSize: '0.8rem', color: '#555', flex: 1,
  };

  return (
    <div
      style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 }}
      onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
    >
      <div style={{ background: '#fff', borderRadius: 8, padding: '24px 28px', width: '100%', maxWidth: 560, maxHeight: '90vh', overflowY: 'auto', boxShadow: '0 8px 32px rgba(0,0,0,0.18)' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <h2 style={{ margin: 0, fontSize: '1.1rem' }}>{isEdit ? 'Edit Set' : 'Add Set'}</h2>
          <button onClick={onClose} style={{ background: 'none', border: 'none', fontSize: '1.3rem', cursor: 'pointer', color: '#888', lineHeight: 1 }}>×</button>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          {/* Sport */}
          <label style={{ ...lbl, maxWidth: 220 }}>
            Sport
            <select style={inp} value={form.sport} onChange={set('sport')}>
              {SPORTS_OPTIONS.map(({ value, label }) => <option key={value} value={value}>{label}</option>)}
            </select>
          </label>

          {/* Set name + Insert */}
          <div style={{ display: 'flex', gap: 12 }}>
            <label style={lbl}>
              Set Name *
              <input style={inp} value={form.set_name} onChange={set('set_name')} placeholder="e.g. Topps, Bowman Chrome" />
            </label>
            <label style={lbl}>
              Insert
              <input style={inp} value={form.insert_name} onChange={set('insert_name')} placeholder="e.g. Refractor, Auto (blank = base)" />
            </label>
          </div>

          {/* Year + # Cards in Set */}
          <div style={{ display: 'flex', gap: 12 }}>
            <label style={{ ...lbl, flex: '0 0 100px' }}>
              Year
              <input style={inp} value={form.year} onChange={set('year')} placeholder="e.g. 2021" />
            </label>
            <label style={{ ...lbl, flex: '0 0 130px' }}>
              # Cards in Set
              <input type="number" min={0} style={inp} value={form.card_count} onChange={set('card_count')} placeholder="e.g. 660" />
            </label>
          </div>

          {/* Link */}
          <label style={lbl}>
            Link (URL)
            <input style={inp} value={form.link} onChange={set('link')} placeholder="https://…" />
          </label>

          {/* Notes */}
          <label style={lbl}>
            Notes
            <textarea
              style={{ ...inp, resize: 'vertical', minHeight: 60 }}
              value={form.notes}
              onChange={set('notes')}
              placeholder="Any additional notes about this set…"
            />
          </label>
        </div>

        {error && <p style={{ color: '#c00', fontSize: '0.85rem', margin: '12px 0 0' }}>{error}</p>}

        <div style={{ display: 'flex', gap: 10, marginTop: 20, justifyContent: 'flex-end' }}>
          <button onClick={onClose} style={{ padding: '7px 18px', borderRadius: 4, border: '1px solid #ccc', background: '#fff', cursor: 'pointer' }}>
            Cancel
          </button>
          <button onClick={handleSave} disabled={saving} style={{ padding: '7px 18px', borderRadius: 4, border: 'none', background: '#4c6ef5', color: '#fff', fontWeight: 600, cursor: 'pointer' }}>
            {saving ? 'Saving…' : isEdit ? 'Save Changes' : 'Add Set'}
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── SportsSetRow ─────────────────────────────────────────────────────────────

function SportsSetRow({ row, onEdit, onEditInsert, onDelete, onDeleteInsert, onViewCards }: {
  row: SportsSetRow;
  onEdit: (row: SportsSetRow) => void;
  onEditInsert: (row: SportsSetRow, ins: typeof row.inserts[number]) => void;
  onDelete: (id: number) => void;
  onDeleteInsert: (id: number) => void;
  onViewCards: (setName: string, insert?: string) => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const hasInserts = row.inserts.length > 0;

  const cellNum: React.CSSProperties = { padding: '5px 8px', textAlign: 'right' };
  const cellStr: React.CSSProperties = { padding: '5px 8px' };
  const actBtn: React.CSSProperties = {
    padding: '2px 8px', fontSize: '0.75rem', borderRadius: 4, cursor: 'pointer', border: '1px solid',
  };

  return (
    <>
      <tr style={{ borderBottom: '1px solid #eee', background: '#fff' }}>
        <td style={{ padding: '5px 8px', width: 24 }}>
          {hasInserts && (
            <button
              onClick={() => setExpanded((v) => !v)}
              style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '0.8rem', color: '#4c6ef5', padding: 0, lineHeight: 1 }}
              title={expanded ? 'Collapse inserts' : 'Expand inserts'}
            >
              {expanded ? '▼' : '▶'}
            </button>
          )}
        </td>
        <td style={cellStr}>
          {row.link
            ? <a href={row.link} target="_blank" rel="noreferrer" style={{ color: '#4c6ef5', fontWeight: 600 }}>{row.set_name || '—'}</a>
            : <strong>{row.set_name || '—'}</strong>
          }
          {row.notes && <span style={{ marginLeft: 6, fontSize: '0.75rem', color: '#999' }} title={row.notes}>📝</span>}
        </td>
        <td style={cellStr}>{row.year || '—'}</td>
        <td style={cellNum}>{row.card_count ?? '—'}</td>
        <td style={cellNum}>{row.owned}</td>
        <td style={cellNum}>${row.paid.toFixed(2)}</td>
        <td style={cellNum}>${row.value.toFixed(2)}</td>
        <td style={{ padding: '5px 8px', whiteSpace: 'nowrap' }}>
          {row.owned > 0 && (
            <button onClick={() => onViewCards(row.set_name)} style={{ ...actBtn, borderColor: '#2b7a2b', color: '#2b7a2b', background: '#fff', marginRight: 4 }}>View</button>
          )}
          <button onClick={() => onEdit(row)} style={{ ...actBtn, borderColor: '#4c6ef5', color: '#4c6ef5', background: '#fff', marginRight: 4 }}>Edit</button>
          {row.catalog_id && (
            <button onClick={() => onDelete(row.catalog_id!)} style={{ ...actBtn, borderColor: '#c00', color: '#c00', background: '#fff' }}>Del</button>
          )}
        </td>
      </tr>
      {expanded && row.inserts.map((ins) => (
        <tr key={ins.insert} style={{ borderBottom: '1px solid #f0f0f0', background: '#f8f9ff' }}>
          <td style={{ padding: '4px 8px' }}></td>
          <td style={{ padding: '4px 8px 4px 24px', color: '#555', fontStyle: 'italic' }}>
            {ins.link
              ? <a href={ins.link} target="_blank" rel="noreferrer" style={{ color: '#4c6ef5' }}>↳ {ins.insert}</a>
              : <>↳ {ins.insert}</>
            }
            {ins.notes && <span style={{ marginLeft: 6, fontSize: '0.75rem', color: '#999' }} title={ins.notes}>📝</span>}
          </td>
          <td style={{ padding: '4px 8px', color: '#777' }}>{ins.year || '—'}</td>
          <td style={{ ...cellNum, color: '#555' }}>{ins.card_count ?? '—'}</td>
          <td style={{ ...cellNum, color: '#555' }}>{ins.owned}</td>
          <td style={{ ...cellNum, color: '#555' }}>${ins.paid.toFixed(2)}</td>
          <td style={{ ...cellNum, color: '#555' }}>${ins.value.toFixed(2)}</td>
          <td style={{ padding: '4px 8px', whiteSpace: 'nowrap' }}>
            {ins.owned > 0 && (
              <button onClick={() => onViewCards(row.set_name, ins.insert)} style={{ ...actBtn, borderColor: '#2b7a2b', color: '#2b7a2b', background: '#fff', marginRight: 4 }}>View</button>
            )}
            <button onClick={() => onEditInsert(row, ins)} style={{ ...actBtn, borderColor: '#4c6ef5', color: '#4c6ef5', background: '#fff', marginRight: 4 }}>Edit</button>
            {ins.catalog_id && (
              <button onClick={() => onDeleteInsert(ins.catalog_id!)} style={{ ...actBtn, borderColor: '#c00', color: '#c00', background: '#fff' }}>Del</button>
            )}
          </td>
        </tr>
      ))}
    </>
  );
}


// ─── SetRow ───────────────────────────────────────────────────────────────────

function SetRow({
  set, ownerId, profileId, showOwnedCol, showGameCol, onOwnedLoaded, cachedCount, onCached,
}: {
  set: SetEntry;
  ownerId: string;
  profileId: string;
  showOwnedCol: boolean;
  showGameCol: boolean;
  onOwnedLoaded: (code: string, count: number) => void;
  cachedCount: number;
  onCached: () => void;
}) {
  const { data: owned } = useQuery({
    queryKey: ['sets', set.code, 'owned', ownerId, profileId],
    queryFn: () => setsApi.ownedCount(set.code, ownerId, profileId),
    enabled: !!ownerId && (set.game === 'Magic: The Gathering' || set.game === 'Pokémon'),
    staleTime: 5 * 60 * 1000,
  });

  const ownedCount = owned?.owned_count;
  useMemo(() => {
    if (ownedCount !== undefined) onOwnedLoaded(set.code, ownedCount);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [set.code, ownedCount]);

  const isMtg  = set.game === 'Magic: The Gathering';
  const isPkmn = set.game === 'Pokémon';
  const canCache  = isMtg || isPkmn;
  const gameParam: 'mtg' | 'pokemon' = isPkmn ? 'pokemon' : 'mtg';
  const totalCards   = parseInt(set.card_count, 10) || 0;
  const isFullyCached = totalCards > 0 && cachedCount >= totalCards;

  const [caching, setCaching]       = useState(false);
  const [cacheResult, setCacheResult] = useState<CacheCardsResult | null>(null);
  const [cacheError, setCacheError]   = useState('');

  const handleCache = async () => {
    setCaching(true); setCacheResult(null); setCacheError('');
    try {
      const result = await setsApi.cacheSetCards(set.code.toLowerCase(), gameParam);
      setCacheResult(result);
      onCached();
    } catch (err: unknown) {
      setCacheError(err instanceof Error ? err.message : 'Failed');
    } finally {
      setCaching(false);
    }
  };

  return (
    <tr style={{ borderBottom: '1px solid #eee' }}>
      <td style={{ padding: '5px 8px' }}>
        {set.icon_url && (
          <img src={set.icon_url} alt="" width={16} height={16} style={{ marginRight: 6, verticalAlign: 'middle' }} />
        )}
        {set.scryfall_uri ? (
          <a href={set.scryfall_uri} target="_blank" rel="noreferrer" style={{ color: '#4c6ef5' }}>{set.name}</a>
        ) : set.name}
      </td>
      <td style={{ fontFamily: 'monospace', fontSize: '0.8rem' }}>{set.code}</td>
      {showGameCol && <td>{set.game}</td>}
      <td>{set.year}</td>
      <td>{set.set_type}</td>
      <td>{set.card_count || '—'}</td>
      {showOwnedCol && <td>{owned?.owned_count ?? '—'}</td>}

      <td style={{ padding: '4px 6px', whiteSpace: 'nowrap' }}>
        {canCache ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 2, alignItems: 'flex-start' }}>
            <button
              onClick={handleCache}
              disabled={caching}
              title={isFullyCached
                ? `${cachedCount} / ${totalCards} cached — click to update`
                : `${cachedCount} / ${totalCards || '?'} cached — click to download`}
              style={{
                padding: '2px 8px', fontSize: '0.75rem', fontWeight: 600, borderRadius: 4,
                border: `1px solid ${isFullyCached ? '#2a7a2a' : '#4c6ef5'}`,
                background: caching ? '#e8ecff' : isFullyCached ? '#ebfbee' : '#fff',
                color: caching ? '#4c6ef5' : isFullyCached ? '#2a7a2a' : '#4c6ef5',
                cursor: caching ? 'not-allowed' : 'pointer', whiteSpace: 'nowrap',
              }}
            >
              {caching ? '⏳ Working…' : isFullyCached ? '🔄 Update Card Info' : '📥 Download Card Info'}
            </button>
            {!caching && cachedCount > 0 && (
              <span style={{ fontSize: '0.68rem', color: '#888' }}>
                {cachedCount}{totalCards ? ` / ${totalCards}` : ''} cached
              </span>
            )}
            {cacheResult && !caching && (
              <span style={{ fontSize: '0.68rem', color: '#555' }}>
                +{cacheResult.stored} new · {cacheResult.skipped} skip
              </span>
            )}
            {cacheError && (
              <span style={{ fontSize: '0.68rem', color: '#c00' }} title={cacheError}>❌ Error</span>
            )}
          </div>
        ) : (
          <span style={{ color: '#ccc', fontSize: '0.75rem' }}>—</span>
        )}
      </td>
    </tr>
  );
}
