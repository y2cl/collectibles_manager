interface Props {
  label: string;
  value: string | number;
}

export default function StatCard({ label, value }: Props) {
  return (
    <div style={{
      background: '#f5f7fb',
      border: '1px solid #e0e4ef',
      borderRadius: 8,
      padding: '0.75rem 1rem',
      textAlign: 'center',
      minWidth: 100,
    }}>
      <div style={{ fontSize: '1.4rem', fontWeight: 700 }}>{value}</div>
      <div style={{ fontSize: '0.8rem', color: '#666', marginTop: 2 }}>{label}</div>
    </div>
  );
}
