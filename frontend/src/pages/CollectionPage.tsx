import { useState, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useOwnerStore } from '../store/ownerStore';
import { useCollection, useUpdateCard, useBulkDeleteCards, useBulkMoveCards, useBulkRefreshCards } from '../hooks/useCollection';
import { useOwners } from '../hooks/useOwners';
import StatCard from '../components/shared/StatCard';
import CardImage from '../components/shared/CardImage';
import InvestmentTab from '../components/collection/InvestmentTab';
import WatchlistTab from '../components/collection/WatchlistTab';
import ImportExportTab from '../components/collection/ImportExportTab';
import ManagementTab from '../components/collection/ManagementTab';
import EditCardModal from '../components/collection/EditCardModal';
import type { CollectionCard } from '../types/card';

const GAMES = ['All', 'Magic: The Gathering', 'Pokémon', 'Sports Cards', 'Collectibles'];
const TABS = ['🗂️ Collection', '🖼️ Gallery', '📈 Investment', '⭐ Watchlist', '⬇️⬆️ Import/Export', '🧭 Management'];

const SPORTS = [
  { value: 'all',        label: 'All Sports' },
  { value: 'baseball',   label: '⚾ Baseball' },
  { value: 'football',   label: '🏈 Football' },
  { value: 'basketball', label: '🏀 Basketball' },
  { value: 'hockey',     label: '🏒 Hockey' },
  { value: 'soccer',     label: '⚽ Soccer' },
  { value: 'other',      label: '🃏 Other' },
];

export default function CollectionPage() {
  const { currentOwnerId, currentProfileId } = useOwnerStore();
  const [searchParams, setSearchParams] = useSearchParams();

  // Initialize from URL query params (e.g. from Sets page "View Cards" link)
  const [scope, setScope] = useState(() => searchParams.get('scope') || 'All');
  const [sportFilter, setSportFilter] = useState('all');
  const [setFilter, setSetFilter] = useState(() => searchParams.get('set') || '');
  const [insertFilter, setInsertFilter] = useState(() => searchParams.get('insert') || '');
  const [playerFilter, setPlayerFilter] = useState('');
  const [yearFilter, setYearFilter] = useState('');

  const [activeTab, setActiveTab] = useState(0);
  const [editId, setEditId] = useState<number | null>(null);
  const [editCard, setEditCard] = useState<CollectionCard | null>(null);
  const [sortKey, setSortKey] = useState<string>('timestamp');
  const [sortDir, setSortDir] = useState<'asc' | 'desc'>('desc');

  const DEFAULT_COL_WIDTHS: Record<string, number> = {
    checkbox: 28, name: 180, set_name: 150, card_number: 60,
    game: 110, year: 60, quantity: 50, variant: 110, price_usd: 80, paid: 80, actions: 60,
  };
  const [colWidths, setColWidths] = useState<Record<string, number>>(DEFAULT_COL_WIDTHS);

  const startResize = useCallback((col: string, e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    const startX = e.clientX;
    const startW = colWidths[col] ?? DEFAULT_COL_WIDTHS[col] ?? 100;
    const onMove = (ev: MouseEvent) => {
      setColWidths((prev) => ({ ...prev, [col]: Math.max(40, startW + ev.clientX - startX) }));
    };
    const onUp = () => {
      document.removeEventListener('mousemove', onMove);
      document.removeEventListener('mouseup', onUp);
    };
    document.addEventListener('mousemove', onMove);
    document.addEventListener('mouseup', onUp);
  }, [colWidths]);

  // Selection state
  const [selectedIds, setSelectedIds] = useState<Set<number>>(new Set());

  // Move panel state
  const [showMovePanel, setShowMovePanel] = useState(false);
  const [moveTargetOwner, setMoveTargetOwner] = useState('');
  const [moveTargetProfile, setMoveTargetProfile] = useState('default');

  // Status message
  const [actionMsg, setActionMsg] = useState('');

  const game = scope === 'All' ? undefined : scope;
  const { data, isLoading } = useCollection(currentOwnerId, currentProfileId, game);
  const { data: owners = [] } = useOwners();
  const updateCard = useUpdateCard();
  const bulkDelete = useBulkDeleteCards();
  const bulkMove = useBulkMoveCards();
  const bulkRefresh = useBulkRefreshCards();

  if (!currentOwnerId) {
    return <div style={{ padding: '2rem', color: '#666' }}>Please select an owner in the sidebar to view your collection.</div>;
  }

  const cards: CollectionCard[] = data?.cards ?? [];
  const stats = data?.stats;
  const filtered = cards.filter((c) => {
    if (scope === 'Sports Cards' && sportFilter !== 'all' && c.sport !== sportFilter) return false;
    if (playerFilter && !c.name.toLowerCase().includes(playerFilter.toLowerCase())) return false;
    if (setFilter && !(c.set_name || '').toLowerCase().includes(setFilter.toLowerCase())) return false;
    if (insertFilter && !(c.variant || '').toLowerCase().includes(insertFilter.toLowerCase())) return false;
    if (yearFilter && !(c.year || '').includes(yearFilter)) return false;
    return true;
  });

  const sorted = [...filtered].sort((a, b) => {
    let av: string | number = '';
    let bv: string | number = '';
    switch (sortKey) {
      case 'name':      av = a.name?.toLowerCase() ?? '';        bv = b.name?.toLowerCase() ?? ''; break;
      case 'set_name':  av = a.set_name?.toLowerCase() ?? '';    bv = b.set_name?.toLowerCase() ?? ''; break;
      case 'game':      av = (a.sport || a.game)?.toLowerCase() ?? ''; bv = (b.sport || b.game)?.toLowerCase() ?? ''; break;
      case 'quantity':  av = a.quantity ?? 0;                    bv = b.quantity ?? 0; break;
      case 'variant':   av = a.variant?.toLowerCase() ?? '';     bv = b.variant?.toLowerCase() ?? ''; break;
      case 'price_usd': av = a.price_usd ?? 0;                   bv = b.price_usd ?? 0; break;
      case 'paid':      av = a.paid ?? 0;                        bv = b.paid ?? 0; break;
      case 'year':      av = a.year ?? '';                       bv = b.year ?? ''; break;
      case 'card_number': av = a.card_number ?? '';              bv = b.card_number ?? ''; break;
      default:          av = a.timestamp ?? '';                  bv = b.timestamp ?? ''; break;
    }
    if (av < bv) return sortDir === 'asc' ? -1 : 1;
    if (av > bv) return sortDir === 'asc' ? 1 : -1;
    return 0;
  });

  const allFilteredIds = filtered.map((c) => c.id);
  const allSelected = allFilteredIds.length > 0 && allFilteredIds.every((id) => selectedIds.has(id));

  const toggleSelect = (id: number) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      next.has(id) ? next.delete(id) : next.add(id);
      return next;
    });
  };

  const toggleSelectAll = () => {
    if (allSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(allFilteredIds));
    }
  };

  const clearSelection = (preserveMsg = false) => {
    setSelectedIds(new Set());
    setShowMovePanel(false);
    if (!preserveMsg) setActionMsg('');
  };

  const selectedList = [...selectedIds];

  const handleDelete = async () => {
    if (!window.confirm(`Delete ${selectedList.length} card(s)? This cannot be undone.`)) return;
    await bulkDelete.mutateAsync({ owner_id: currentOwnerId, profile_id: currentProfileId, card_ids: selectedList });
    setActionMsg(`Deleted ${selectedList.length} card(s).`);
    clearSelection(true);
  };

  const handleRefresh = async () => {
    setActionMsg('Refreshing prices…');
    try {
      const result = await bulkRefresh.mutateAsync(selectedList) as { updated: number; errors: string[] };
      const errNote = result.errors.length ? ` Errors: ${result.errors.join('; ')}` : '';
      setActionMsg(`Updated prices for ${result.updated} card(s).${errNote}`);
    } catch {
      setActionMsg('Price refresh failed — check console.');
    }
    clearSelection(true);
  };

  const handleMove = async () => {
    if (!moveTargetOwner) return;
    await bulkMove.mutateAsync({ card_ids: selectedList, target_owner_id: moveTargetOwner, target_profile_id: moveTargetProfile });
    setActionMsg(`Moved ${selectedList.length} card(s) to ${moveTargetOwner} / ${moveTargetProfile}.`);
    clearSelection(true);
  };

  const moveOwnerProfiles = owners.find((o) => o.owner_id === moveTargetOwner)?.profiles ?? [];

  const handleSort = (key: string) => {
    if (sortKey === key) {
      setSortDir((d) => d === 'asc' ? 'desc' : 'asc');
    } else {
      setSortKey(key);
      setSortDir('asc');
    }
  };
  const sortIndicator = (key: string) => sortKey === key ? (sortDir === 'asc' ? ' ▲' : ' ▼') : '';

  const resizeHandle = (col: string) => (
    <div
      onMouseDown={(e) => startResize(col, e)}
      style={{
        position: 'absolute', right: 0, top: 0, bottom: 0, width: 5,
        cursor: 'col-resize', zIndex: 1,
        borderRight: '2px solid transparent',
      }}
      onMouseEnter={(e) => (e.currentTarget.style.borderRightColor = '#4c6ef5')}
      onMouseLeave={(e) => (e.currentTarget.style.borderRightColor = 'transparent')}
    />
  );

  const thSort = (col: string, sortKey_: string = col): React.CSSProperties => ({
    padding: '6px 8px', cursor: 'pointer', userSelect: 'none', whiteSpace: 'nowrap',
    position: 'relative', width: colWidths[col] ?? DEFAULT_COL_WIDTHS[col],
    overflow: 'hidden',
  });

  const tabBarStyle: React.CSSProperties = {
    display: 'flex', gap: '0.25rem', borderBottom: '2px solid #e0e4ef',
    marginBottom: '1rem', flexWrap: 'wrap',
  };
  const tabBtn = (active: boolean): React.CSSProperties => ({
    padding: '6px 12px', border: 'none', borderRadius: '4px 4px 0 0',
    background: active ? '#4c6ef5' : '#f0f2fa',
    color: active ? '#fff' : '#333',
    fontWeight: active ? 700 : 400,
    cursor: 'pointer', fontSize: '0.85rem',
  });
  const actionBtn = (bg: string): React.CSSProperties => ({
    padding: '5px 12px', border: 'none', borderRadius: 4,
    background: bg, color: '#fff', cursor: 'pointer', fontSize: '0.82rem', fontWeight: 600,
  });

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap', gap: 8 }}>
        <div>
          <h1 style={{ margin: 0 }}>💳 My Collection</h1>
          <p style={{ margin: '4px 0 0', color: '#888', fontSize: '0.85rem' }}>
            {currentOwnerId} · {currentProfileId}
          </p>
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <select
            value={scope}
            onChange={(e) => { setScope(e.target.value); setSportFilter('all'); setPlayerFilter(''); setSetFilter(''); setInsertFilter(''); setYearFilter(''); }}
            style={{ padding: '6px 10px', borderRadius: 4, border: '1px solid #ccc', fontSize: '0.9rem' }}
          >
            {GAMES.map((g) => <option key={g}>{g}</option>)}
          </select>
          {scope === 'Sports Cards' && (
            <select
              value={sportFilter}
              onChange={(e) => setSportFilter(e.target.value)}
              style={{ padding: '6px 10px', borderRadius: 4, border: '1px solid #ccc', fontSize: '0.9rem' }}
            >
              {SPORTS.map(({ value, label }) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          )}
        </div>
      </div>

      {/* Stats row */}
      {stats && (
        <div style={{ display: 'flex', gap: 12, margin: '1rem 0', flexWrap: 'wrap' }}>
          <StatCard label="Total Cards" value={stats.total_cards} />
          <StatCard label="Unique Cards" value={stats.unique_cards} />
          <StatCard label="Unique Sets" value={stats.unique_sets} />
          <StatCard label="Total Value" value={`$${stats.total_value.toFixed(2)}`} />
        </div>
      )}

      <hr />

      {/* Tab bar */}
      <div style={tabBarStyle}>
        {TABS.map((label, i) => (
          <button key={i} style={tabBtn(activeTab === i)} onClick={() => setActiveTab(i)}>{label}</button>
        ))}
      </div>

      {/* Collection tab */}
      {activeTab === 0 && (
        <div>
          {/* Filter bar */}
          <div style={{ display: 'flex', gap: 8, marginBottom: '1rem', flexWrap: 'wrap' }}>
            <input
              placeholder={scope === 'Sports Cards' ? 'Player…' : 'Card Name…'}
              value={playerFilter}
              onChange={(e) => setPlayerFilter(e.target.value)}
              style={{ padding: '6px 10px', borderRadius: 4, border: '1px solid #ccc', fontSize: '0.85rem', flex: '1 1 150px', minWidth: 120 }}
            />
            <input
              placeholder="Set…"
              value={setFilter}
              onChange={(e) => setSetFilter(e.target.value)}
              style={{ padding: '6px 10px', borderRadius: 4, border: '1px solid #ccc', fontSize: '0.85rem', flex: '1 1 160px', minWidth: 120 }}
            />
            <input
              placeholder={scope === 'Sports Cards' ? 'Insert…' : 'Variant…'}
              value={insertFilter}
              onChange={(e) => setInsertFilter(e.target.value)}
              style={{ padding: '6px 10px', borderRadius: 4, border: '1px solid #ccc', fontSize: '0.85rem', flex: '1 1 140px', minWidth: 100 }}
            />
            <input
              placeholder="Year…"
              value={yearFilter}
              onChange={(e) => setYearFilter(e.target.value)}
              style={{ padding: '6px 10px', borderRadius: 4, border: '1px solid #ccc', fontSize: '0.85rem', width: 90 }}
            />
            {(playerFilter || setFilter || insertFilter || yearFilter) && (
              <button
                onClick={() => { setPlayerFilter(''); setSetFilter(''); setInsertFilter(''); setYearFilter(''); setSearchParams({}); }}
                style={{ padding: '6px 10px', borderRadius: 4, border: '1px solid #ccc', background: '#fff', cursor: 'pointer', fontSize: '0.82rem', color: '#888', whiteSpace: 'nowrap' }}
              >
                Clear
              </button>
            )}
          </div>

          {/* Bulk action toolbar */}
          {selectedIds.size > 0 && (
            <div style={{ background: '#f0f2fa', border: '1px solid #d0d5ee', borderRadius: 6, padding: '8px 12px', marginBottom: '0.75rem', display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
              <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#4c6ef5' }}>
                {selectedIds.size} selected
              </span>
              <button
                style={actionBtn('#4c6ef5')}
                onClick={() => { setShowMovePanel((v) => !v); setMoveTargetOwner(''); setMoveTargetProfile('default'); }}
              >
                Move
              </button>
              <button
                style={actionBtn('#2b7a2b')}
                onClick={handleRefresh}
                disabled={bulkRefresh.isPending}
              >
                {bulkRefresh.isPending ? 'Refreshing…' : 'Update Information'}
              </button>
              <button
                style={actionBtn('#fa5252')}
                onClick={handleDelete}
                disabled={bulkDelete.isPending}
              >
                Delete
              </button>
              <button
                style={{ padding: '5px 10px', border: '1px solid #ccc', borderRadius: 4, background: '#fff', cursor: 'pointer', fontSize: '0.82rem' }}
                onClick={clearSelection}
              >
                Clear
              </button>
              {actionMsg && <span style={{ fontSize: '0.8rem', color: '#555', marginLeft: 4 }}>{actionMsg}</span>}
            </div>
          )}

          {/* Move panel */}
          {showMovePanel && selectedIds.size > 0 && (
            <div style={{ background: '#fff', border: '1px solid #d0d5ee', borderRadius: 6, padding: '10px 14px', marginBottom: '0.75rem', display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
              <span style={{ fontSize: '0.82rem', fontWeight: 600 }}>Move to:</span>
              <select
                value={moveTargetOwner}
                onChange={(e) => { setMoveTargetOwner(e.target.value); setMoveTargetProfile('default'); }}
                style={{ padding: '4px 8px', borderRadius: 4, border: '1px solid #ccc', fontSize: '0.82rem' }}
              >
                <option value="">— Select owner —</option>
                {owners.map((o) => (
                  <option key={o.owner_id} value={o.owner_id}>{o.label}</option>
                ))}
              </select>
              {moveOwnerProfiles.length > 0 && (
                <select
                  value={moveTargetProfile}
                  onChange={(e) => setMoveTargetProfile(e.target.value)}
                  style={{ padding: '4px 8px', borderRadius: 4, border: '1px solid #ccc', fontSize: '0.82rem' }}
                >
                  {moveOwnerProfiles.map((p) => (
                    <option key={p.profile_id} value={p.profile_id}>{p.profile_id}</option>
                  ))}
                </select>
              )}
              <button
                style={actionBtn('#4c6ef5')}
                onClick={handleMove}
                disabled={!moveTargetOwner || bulkMove.isPending}
              >
                {bulkMove.isPending ? 'Moving…' : 'Confirm Move'}
              </button>
              <button
                style={{ padding: '5px 10px', border: '1px solid #ccc', borderRadius: 4, background: '#fff', cursor: 'pointer', fontSize: '0.82rem' }}
                onClick={() => setShowMovePanel(false)}
              >
                Cancel
              </button>
            </div>
          )}

          {isLoading && <p>Loading…</p>}
          {!isLoading && filtered.length === 0 && <p style={{ color: '#888' }}>No cards in this collection yet.</p>}
          <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem', tableLayout: 'fixed' }}>
            <thead>
              <tr style={{ background: '#f5f7fb', textAlign: 'left' }}>
                <th style={{ padding: '6px 8px', width: colWidths.checkbox, position: 'relative' }}>
                  <input type="checkbox" checked={allSelected} onChange={toggleSelectAll} title="Select all" />
                  {resizeHandle('checkbox')}
                </th>
                <th style={thSort('name')} onClick={() => handleSort('name')}>Name{sortIndicator('name')}{resizeHandle('name')}</th>
                <th style={thSort('set_name')} onClick={() => handleSort('set_name')}>{scope === 'Collectibles' ? 'Line / Series' : 'Set'}{sortIndicator('set_name')}{resizeHandle('set_name')}</th>
                <th style={thSort('card_number')} onClick={() => handleSort('card_number')}>{scope === 'Collectibles' ? 'Manufacturer' : '#'}{sortIndicator('card_number')}{resizeHandle('card_number')}</th>
                {(scope === 'All' || scope === 'Sports Cards' || scope === 'Collectibles') && (
                  <th style={thSort('game')} onClick={() => handleSort('game')}>{scope === 'All' ? 'Collection' : scope === 'Sports Cards' ? 'Sport' : 'Game'}{sortIndicator('game')}{resizeHandle('game')}</th>
                )}
                <th style={thSort('year')} onClick={() => handleSort('year')}>Year{sortIndicator('year')}{resizeHandle('year')}</th>
                <th style={thSort('quantity')} onClick={() => handleSort('quantity')}>Qty{sortIndicator('quantity')}{resizeHandle('quantity')}</th>
                <th style={thSort('variant')} onClick={() => handleSort('variant')}>{scope === 'Collectibles' ? 'Condition' : scope === 'Sports Cards' ? 'Insert' : 'Variant'}{sortIndicator('variant')}{resizeHandle('variant')}</th>
                <th style={thSort('price_usd')} onClick={() => handleSort('price_usd')}>Value{sortIndicator('price_usd')}{resizeHandle('price_usd')}</th>
                <th style={thSort('paid')} onClick={() => handleSort('paid')}>Paid{sortIndicator('paid')}{resizeHandle('paid')}</th>
                <th style={{ padding: '6px 8px', width: colWidths.actions, position: 'relative' }}>{resizeHandle('actions')}</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((card) => (
                <tr
                  key={card.id}
                  style={{ borderBottom: '1px solid #eee', background: selectedIds.has(card.id) ? '#eef1fd' : undefined }}
                >
                  <td style={{ padding: '5px 8px' }}>
                    <input
                      type="checkbox"
                      checked={selectedIds.has(card.id)}
                      onChange={() => toggleSelect(card.id)}
                    />
                  </td>
                  <td style={{ padding: '5px 8px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 0 }}>
                    {card.link ? (
                      <a href={card.link} target="_blank" rel="noreferrer" style={{ color: '#4c6ef5', textDecoration: 'none' }}>
                        {card.name}
                      </a>
                    ) : card.name}
                  </td>
                  <td style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 0 }}>{card.set_name}</td>
                  <td style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 0 }}>{scope === 'Collectibles' ? (card.manufacturer || '—') : card.card_number}</td>
                  {(scope === 'All' || scope === 'Sports Cards' || scope === 'Collectibles') && (
                    <td style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 0 }}>{scope === 'Sports Cards' ? (card.sport || card.game) : card.game}</td>
                  )}
                  <td style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: 0 }}>{card.year || '—'}</td>
                  <td>
                    {editId === card.id ? (
                      <input
                        type="number" min={1} defaultValue={card.quantity} style={{ width: 50 }}
                        onBlur={(e) => {
                          updateCard.mutate({ id: card.id, payload: { quantity: parseInt(e.target.value) || 1 } });
                          setEditId(null);
                        }}
                        autoFocus
                      />
                    ) : (
                      <span onClick={() => setEditId(card.id)} style={{ cursor: 'pointer' }}>{card.quantity}</span>
                    )}
                  </td>
                  <td>{card.variant || '—'}</td>
                  <td>${(card.price_usd || 0).toFixed(2)}</td>
                  <td>${(card.paid || 0).toFixed(2)}</td>
                  <td style={{ padding: '5px 8px' }}>
                    {(card.game === 'Sports Cards' || card.game === 'Collectibles') && (
                      <button
                        onClick={() => setEditCard(card)}
                        style={{ padding: '2px 10px', fontSize: '0.78rem', border: '1px solid #ccc', borderRadius: 4, background: '#f8f9fa', cursor: 'pointer' }}
                      >
                        Edit
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          </div>
        </div>
      )}

      {/* Gallery tab */}
      {activeTab === 1 && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 12 }}>
          {filtered.map((card) => (
            <div key={card.id} style={{ textAlign: 'center' }}>
              <CardImage src={card.image_url} alt={card.name} width={150} link={card.link} />
              <div style={{ fontSize: '0.75rem', marginTop: 4, color: '#555' }}>
                {card.name} — {card.year} {card.set_name}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Investment tab */}
      {activeTab === 2 && <InvestmentTab ownerId={currentOwnerId} profileId={currentProfileId} game={game} />}

      {/* Watchlist tab */}
      {activeTab === 3 && <WatchlistTab />}

      {/* Import/Export tab */}
      {activeTab === 4 && <ImportExportTab />}

      {/* Management tab */}
      {activeTab === 5 && <ManagementTab />}

      {/* Edit modal for Sports Cards / Collectibles */}
      {editCard && (
        <EditCardModal
          card={editCard}
          onSave={async (id, payload) => {
            await updateCard.mutateAsync({ id, payload });
          }}
          onClose={() => setEditCard(null)}
        />
      )}
    </div>
  );
}
