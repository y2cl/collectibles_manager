import { useState } from 'react';
import { useOwnerStore } from '../store/ownerStore';
import { useCollection, useDeleteCard, useUpdateCard } from '../hooks/useCollection';
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

  const game = scope === 'All' ? undefined : scope;
  const { data, isLoading } = useCollection(currentOwnerId, currentProfileId, game);
  const deleteCard = useDeleteCard();
  const updateCard = useUpdateCard();

  if (!currentOwnerId) {
    return <div style={{ padding: '2rem', color: '#666' }}>Please select an owner in the sidebar to view your collection.</div>;
  }

  const cards: CollectionCard[] = data?.cards ?? [];
  const stats = data?.stats;

  const filtered = search
    ? cards.filter((c) => c.name.toLowerCase().includes(search.toLowerCase()))
    : cards;

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
          {isLoading && <p>Loading…</p>}
          {!isLoading && filtered.length === 0 && <p style={{ color: '#888' }}>No cards in this collection yet.</p>}
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
            <thead>
              <tr style={{ background: '#f5f7fb', textAlign: 'left' }}>
                <th style={{ padding: '6px 8px' }}>Name</th>
                <th>Set</th>
                <th>#</th>
                <th>Game</th>
                <th>Qty</th>
                <th>Variant</th>
                <th>Price</th>
                <th>Paid</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((card) => (
                <tr key={card.id} style={{ borderBottom: '1px solid #eee' }}>
                  <td style={{ padding: '5px 8px' }}>{card.name}</td>
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
                  <td>
                    <button
                      onClick={() => deleteCard.mutate(card.id)}
                      style={{ padding: '2px 8px', background: '#fa5252', color: '#fff', border: 'none', borderRadius: 3, cursor: 'pointer', fontSize: '0.75rem' }}
                    >
                      Remove
                    </button>
                  </td>
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
