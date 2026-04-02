import { useState } from 'react';
import { useOwnerStore } from '../store/ownerStore';
import { useCollection, useUpdateCard, useBulkDeleteCards, useBulkMoveCards, useBulkRefreshCards } from '../hooks/useCollection';
import { useOwners } from '../hooks/useOwners';
import StatCard from '../components/shared/StatCard';
import CardImage from '../components/shared/CardImage';
import InvestmentTab from '../components/collection/InvestmentTab';
import WatchlistTab from '../components/collection/WatchlistTab';
import ImportExportTab from '../components/collection/ImportExportTab';
import ManagementTab from '../components/collection/ManagementTab';
import type { CollectionCard } from '../types/card';

const GAMES = ['All', 'Magic: The Gathering', 'Pokémon', 'Baseball Cards'];
const TABS = ['🗂️ Collection', '🖼️ Gallery', '📈 Investment', '⭐ Watchlist', '⬇️⬆️ Import/Export', '🧭 Management'];

export default function CollectionPage() {
  const { currentOwnerId, currentProfileId } = useOwnerStore();
  const [scope, setScope] = useState('All');
  const [activeTab, setActiveTab] = useState(0);
  const [editId, setEditId] = useState<number | null>(null);
  const [search, setSearch] = useState('');

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
  const filtered = search
    ? cards.filter((c) => c.name.toLowerCase().includes(search.toLowerCase()))
    : cards;

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
        <select
          value={scope}
          onChange={(e) => setScope(e.target.value)}
          style={{ padding: '6px 10px', borderRadius: 4, border: '1px solid #ccc', fontSize: '0.9rem' }}
        >
          {GAMES.map((g) => <option key={g}>{g}</option>)}
        </select>
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
          <input
            placeholder="Search cards…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            style={{ padding: '6px 10px', borderRadius: 4, border: '1px solid #ccc', marginBottom: '1rem', width: '100%', boxSizing: 'border-box' }}
          />

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
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
            <thead>
              <tr style={{ background: '#f5f7fb', textAlign: 'left' }}>
                <th style={{ padding: '6px 8px', width: 28 }}>
                  <input
                    type="checkbox"
                    checked={allSelected}
                    onChange={toggleSelectAll}
                    title="Select all"
                  />
                </th>
                <th style={{ padding: '6px 8px' }}>Name</th>
                <th>Set</th>
                <th>#</th>
                <th>Game</th>
                <th>Qty</th>
                <th>Variant</th>
                <th>Price</th>
                <th>Paid</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((card) => (
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
                  <td style={{ padding: '5px 8px' }}>
                    {card.link ? (
                      <a href={card.link} target="_blank" rel="noreferrer" style={{ color: '#4c6ef5', textDecoration: 'none' }}>
                        {card.name}
                      </a>
                    ) : card.name}
                  </td>
                  <td>{card.set_name}</td>
                  <td>{card.card_number}</td>
                  <td>{card.game}</td>
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
                </tr>
              ))}
            </tbody>
          </table>
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
    </div>
  );
}
