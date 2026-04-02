import { useQuery } from '@tanstack/react-query';
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';
import client from '../../api/client';

interface Props { ownerId: string; profileId: string; game?: string; }

export default function InvestmentTab({ ownerId, profileId, game }: Props) {
  const { data, isLoading } = useQuery({
    queryKey: ['stats', ownerId, profileId, game],
    queryFn: () => client.get('/api/stats', { params: { owner_id: ownerId, profile_id: profileId, game } }).then((r) => r.data),
    enabled: !!ownerId,
  });

  if (isLoading) return <p>Loading investment data…</p>;
  if (!data) return <p style={{ color: '#888' }}>No data yet.</p>;

  const { value_by_game, top_sets, paid_vs_market } = data;
  const pnl = (paid_vs_market.total_market - paid_vs_market.total_paid).toFixed(2);
  const pnlColor = parseFloat(pnl) >= 0 ? '#2b7a2b' : '#c0392b';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
        <div style={{ background: '#f5f7fb', borderRadius: 8, padding: '0.75rem 1.25rem', minWidth: 140 }}>
          <div style={{ fontSize: '0.75rem', color: '#888' }}>Total Paid</div>
          <div style={{ fontSize: '1.3rem', fontWeight: 700 }}>${paid_vs_market.total_paid.toFixed(2)}</div>
        </div>
        <div style={{ background: '#f5f7fb', borderRadius: 8, padding: '0.75rem 1.25rem', minWidth: 140 }}>
          <div style={{ fontSize: '0.75rem', color: '#888' }}>Market Value</div>
          <div style={{ fontSize: '1.3rem', fontWeight: 700 }}>${paid_vs_market.total_market.toFixed(2)}</div>
        </div>
        <div style={{ background: '#f5f7fb', borderRadius: 8, padding: '0.75rem 1.25rem', minWidth: 140 }}>
          <div style={{ fontSize: '0.75rem', color: '#888' }}>P&L</div>
          <div style={{ fontSize: '1.3rem', fontWeight: 700, color: pnlColor }}>{parseFloat(pnl) >= 0 ? '+' : ''}${pnl}</div>
        </div>
      </div>

      {value_by_game?.length > 0 && (
        <div>
          <h3 style={{ marginBottom: 8 }}>Value by Game</h3>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={value_by_game}>
              <XAxis dataKey="game" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v) => `$${(v as number).toFixed(2)}`} />
              <Bar dataKey="total_value" fill="#4c6ef5" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}

      {top_sets?.length > 0 && (
        <div>
          <h3 style={{ marginBottom: 8 }}>Top Sets by Value</h3>
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={top_sets} layout="vertical">
              <XAxis type="number" tick={{ fontSize: 11 }} />
              <YAxis type="category" dataKey="set_label" width={160} tick={{ fontSize: 10 }} />
              <Tooltip formatter={(v) => `$${(v as number).toFixed(2)}`} />
              <Bar dataKey="total_value" fill="#82ca9d" />
            </BarChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
