import { useState, useMemo } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useOwnerStore } from '../store/ownerStore';
import { setsApi } from '../api/sets';
import type { MtgSyncResult, CacheCardsResult } from '../api/sets';
import type { SetEntry } from '../types/settings';

// ─── Tab config ────────────────────────────────────────────────────────────────

type Tab = 'all' | 'mtg' | 'pokemon' | 'baseball';

const TABS: { id: Tab; label: string; apiGame?: string }[] = [
  { id: 'all',      label: 'All' },
  { id: 'mtg',      label: '🧙 Magic: The Gathering', apiGame: 'Magic: The Gathering' },
  { id: 'pokemon',  label: '⚡ Pokémon',               apiGame: 'Pokémon' },
  { id: 'baseball', label: '⚾ Baseball Cards',        apiGame: 'Baseball Cards' },
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

      {/* ── Table ── */}
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
    </div>
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
