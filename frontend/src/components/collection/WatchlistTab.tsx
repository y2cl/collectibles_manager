import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useOwnerStore } from '../../store/ownerStore';
import { watchlistApi } from '../../api/watchlist';
import type { WatchlistItem } from '../../types/card';

export default function WatchlistTab() {
  const { currentOwnerId, currentProfileId } = useOwnerStore();
  const qc = useQueryClient();

  const { data: items = [], isLoading } = useQuery({
    queryKey: ['watchlist', currentOwnerId, currentProfileId],
    queryFn: () => watchlistApi.list({ owner_id: currentOwnerId!, profile_id: currentProfileId }),
    enabled: !!currentOwnerId,
  });

  const deleteItem = useMutation({
    mutationFn: (id: number) => watchlistApi.delete(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['watchlist', currentOwnerId] }),
  });

  if (!currentOwnerId) return <p style={{ color: '#888' }}>Select an owner first.</p>;
  if (isLoading) return <p>Loading watchlist…</p>;
  if (!items.length) return <p style={{ color: '#888' }}>Your watchlist is empty.</p>;

  return (
    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
      <thead>
        <tr style={{ background: '#f5f7fb', textAlign: 'left' }}>
          <th style={{ padding: '6px 8px' }}>Name</th>
          <th>Set</th>
          <th>Game</th>
          <th>Qty</th>
          <th>Variant</th>
          <th>Market</th>
          <th>Target $</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        {(items as WatchlistItem[]).map((item) => (
          <tr key={item.id} style={{ borderBottom: '1px solid #eee' }}>
            <td style={{ padding: '5px 8px' }}>{item.name}</td>
            <td>{item.set_name}</td>
            <td>{item.game}</td>
            <td>{item.quantity}</td>
            <td>{item.variant || '—'}</td>
            <td>${(item.price_usd || 0).toFixed(2)}</td>
            <td>${(item.target_price || 0).toFixed(2)}</td>
            <td>
              <button
                onClick={() => deleteItem.mutate(item.id)}
                style={{ padding: '2px 8px', background: '#fa5252', color: '#fff', border: 'none', borderRadius: 3, cursor: 'pointer', fontSize: '0.75rem' }}
              >
                Remove
              </button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
