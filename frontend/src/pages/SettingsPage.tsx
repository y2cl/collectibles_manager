import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { settingsApi } from '../api/settings';
import { changelogApi } from '../api/changelog';
import { useSettingsStore } from '../store/settingsStore';
import { useAppearanceStore, DEFAULTS, PRESETS, FONT_OPTIONS } from '../store/appearanceStore';
import type { AppSettings, ApiSourceConfig } from '../types/settings';

const TABS = ['General', 'Appearance', 'Data Sources', 'Debug', 'Change Log', 'About'];

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState(0);

  const tabBarStyle: React.CSSProperties = {
    display: 'flex', gap: '0.25rem', borderBottom: '2px solid #e0e4ef', marginBottom: '1rem',
  };
  const tabBtn = (active: boolean): React.CSSProperties => ({
    padding: '6px 14px', border: 'none', borderRadius: '4px 4px 0 0',
    background: active ? '#4c6ef5' : '#f0f2fa',
    color: active ? '#fff' : '#333',
    fontWeight: active ? 700 : 400,
    cursor: 'pointer', fontSize: '0.85rem',
  });

  return (
    <div>
      <h1 style={{ margin: '0 0 1rem' }}>Settings</h1>
      <div style={tabBarStyle}>
        {TABS.map((label, i) => (
          <button key={i} style={tabBtn(activeTab === i)} onClick={() => setActiveTab(i)}>{label}</button>
        ))}
      </div>
      {activeTab === 0 && <GeneralSettings />}
      {activeTab === 1 && <AppearanceSettings />}
      {activeTab === 2 && <DataSourcesSettings />}
      {activeTab === 3 && <DebugSettings />}
      {activeTab === 4 && <ChangeLogSettings />}
      {activeTab === 5 && <AboutSettings />}
    </div>
  );
}

function GeneralSettings() {
  const qc = useQueryClient();
  const { viewMode, cardsPerRow, imageWidth, compactMode, setViewMode, setCardsPerRow, setImageWidth, setCompactMode } = useSettingsStore();

  const { data: settings } = useQuery({
    queryKey: ['settings'],
    queryFn: settingsApi.get,
  });

  const updateSettings = useMutation({
    mutationFn: (payload: Partial<AppSettings>) => settingsApi.update(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['settings'] }),
  });

  const [msg, setMsg] = useState('');

  const handleSave = async (field: keyof AppSettings, value: unknown) => {
    try {
      await updateSettings.mutateAsync({ [field]: value });
      setMsg('Saved.');
      setTimeout(() => setMsg(''), 2000);
    } catch {
      setMsg('Error saving.');
    }
  };

  const labelStyle: React.CSSProperties = { fontWeight: 600, fontSize: '0.85rem', marginBottom: 4, display: 'block' };
  const selectStyle: React.CSSProperties = { padding: '6px 10px', borderRadius: 4, border: '1px solid #ccc', fontSize: '0.9rem' };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', maxWidth: 480 }}>
      {msg && <p style={{ color: '#2b7a2b', margin: 0 }}>{msg}</p>}

      <section>
        <h3 style={{ marginTop: 0 }}>Collection Behavior</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div>
            <label style={labelStyle}>Duplicate Strategy</label>
            <select
              value={settings?.duplicate_strategy ?? 'merge'}
              onChange={(e) => handleSave('duplicate_strategy', e.target.value)}
              style={selectStyle}
            >
              <option value="merge">Merge (combine quantities)</option>
              <option value="separate">Separate (keep as distinct entries)</option>
            </select>
          </div>
          <div>
            <label style={labelStyle}>Paid Merge Strategy</label>
            <select
              value={settings?.paid_merge_strategy ?? 'sum'}
              onChange={(e) => handleSave('paid_merge_strategy', e.target.value)}
              style={selectStyle}
            >
              <option value="sum">Sum (add paid amounts)</option>
              <option value="average">Average (average paid amounts)</option>
              <option value="ignore">Ignore (keep original paid)</option>
            </select>
          </div>
        </div>
      </section>

      <section>
        <h3 style={{ marginTop: 0 }}>Backup</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <input
              type="checkbox"
              id="auto-backup"
              checked={settings?.auto_backup_enabled ?? true}
              onChange={(e) => handleSave('auto_backup_enabled', e.target.checked)}
            />
            <label htmlFor="auto-backup" style={{ fontSize: '0.9rem' }}>Enable auto-backup on import</label>
          </div>
          <div>
            <label style={labelStyle}>Backup Retention (days)</label>
            <input
              type="number"
              min={1}
              max={365}
              defaultValue={settings?.backup_retention ?? 30}
              onBlur={(e) => handleSave('backup_retention', parseInt(e.target.value) || 30)}
              style={{ ...selectStyle, width: 80 }}
            />
          </div>
        </div>
      </section>

      <section>
        <h3 style={{ marginTop: 0 }}>Display Preferences</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
          <div>
            <label style={labelStyle}>Gallery View Mode</label>
            <select value={viewMode} onChange={(e) => setViewMode(e.target.value as 'grid' | 'list')} style={selectStyle}>
              <option value="grid">Grid</option>
              <option value="list">List</option>
            </select>
          </div>
          <div>
            <label style={labelStyle}>Cards Per Row (gallery)</label>
            <input
              type="number" min={2} max={10} value={cardsPerRow}
              onChange={(e) => setCardsPerRow(parseInt(e.target.value) || 4)}
              style={{ ...selectStyle, width: 80 }}
            />
          </div>
          <div>
            <label style={labelStyle}>Image Width (px)</label>
            <input
              type="number" min={80} max={400} value={imageWidth}
              onChange={(e) => setImageWidth(parseInt(e.target.value) || 150)}
              style={{ ...selectStyle, width: 80 }}
            />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <input
              type="checkbox"
              id="compact-mode"
              checked={compactMode}
              onChange={(e) => setCompactMode(e.target.checked)}
            />
            <label htmlFor="compact-mode" style={{ fontSize: '0.9rem' }}>Compact table rows</label>
          </div>
        </div>
      </section>
    </div>
  );
}

function DataSourcesSettings() {
  const qc = useQueryClient();
  const { data: sources = [] } = useQuery({
    queryKey: ['settings', 'api-sources'],
    queryFn: settingsApi.getApiSources,
  });

  const updateSources = useMutation({
    mutationFn: settingsApi.updateApiSources,
    onSuccess: () => qc.invalidateQueries({ queryKey: ['settings', 'api-sources'] }),
  });

  const [msg, setMsg] = useState('');

  const handleToggle = async (source: ApiSourceConfig) => {
    try {
      await updateSources.mutateAsync([{ source_id: source.source_id, enabled: !source.enabled }]);
      setMsg(`${source.name} ${!source.enabled ? 'enabled' : 'disabled'}.`);
      setTimeout(() => setMsg(''), 2000);
    } catch {
      setMsg('Error updating source.');
    }
  };

  const gameGroups = sources.reduce<Record<string, ApiSourceConfig[]>>((acc, s) => {
    if (!acc[s.game]) acc[s.game] = [];
    acc[s.game].push(s);
    return acc;
  }, {});

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', maxWidth: 640 }}>
      {msg && <p style={{ color: '#2b7a2b', margin: 0 }}>{msg}</p>}
      <p style={{ margin: 0, color: '#666', fontSize: '0.85rem' }}>
        API keys are configured in the backend <code>.env</code> file. Toggle sources on/off here.
      </p>

      {Object.entries(gameGroups).map(([game, gameSources]) => (
        <section key={game}>
          <h3 style={{ marginTop: 0 }}>{game}</h3>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
            <thead>
              <tr style={{ background: '#f5f7fb', textAlign: 'left' }}>
                <th style={{ padding: '6px 8px' }}>Source</th>
                <th>Free</th>
                <th>Description</th>
                <th>Enabled</th>
              </tr>
            </thead>
            <tbody>
              {gameSources.map((s) => (
                <tr key={s.source_id} style={{ borderBottom: '1px solid #eee' }}>
                  <td style={{ padding: '5px 8px', fontWeight: 600 }}>{s.name}</td>
                  <td>{s.free ? '✓' : '—'}</td>
                  <td style={{ color: '#666' }}>{s.description}</td>
                  <td>
                    <input
                      type="checkbox"
                      checked={s.enabled}
                      onChange={() => handleToggle(s)}
                    />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ))}

      {sources.length === 0 && (
        <p style={{ color: '#888' }}>No data sources configured yet.</p>
      )}
    </div>
  );
}

function DebugSettings() {
  const { data, isLoading } = useQuery({
    queryKey: ['debug', 'fallback-stats'],
    queryFn: () => import('../api/client').then(({ default: client }) =>
      client.get('/api/debug/fallback-stats').then((r) => r.data)
    ),
    staleTime: 0,
  });

  const handleBackup = async () => {
    try {
      await import('../api/client').then(({ default: client }) => client.post('/api/backup'));
      alert('Backup triggered successfully.');
    } catch {
      alert('Backup failed — check backend logs.');
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', maxWidth: 540 }}>
      <section>
        <h3 style={{ marginTop: 0 }}>Manual Backup</h3>
        <p style={{ fontSize: '0.85rem', color: '#666', margin: '0 0 8px' }}>
          Creates a timestamped copy of the SQLite database in the backups/ directory.
        </p>
        <button
          onClick={handleBackup}
          style={{ padding: '6px 14px', background: '#4c6ef5', color: '#fff', border: 'none', borderRadius: 4, cursor: 'pointer', fontSize: '0.85rem' }}
        >
          Trigger Backup Now
        </button>
      </section>

      <section>
        <h3 style={{ marginTop: 0 }}>Fallback Cache Stats</h3>
        {isLoading && <p>Loading…</p>}
        {data && (
          <pre style={{ background: '#f5f7fb', padding: '0.75rem', borderRadius: 6, fontSize: '0.8rem', overflow: 'auto' }}>
            {JSON.stringify(data, null, 2)}
          </pre>
        )}
        {!isLoading && !data && <p style={{ color: '#888' }}>No fallback stats available.</p>}
      </section>

      <section>
        <h3 style={{ marginTop: 0 }}>Backend Info</h3>
        <p style={{ fontSize: '0.85rem', color: '#666' }}>
          API URL: <code>{import.meta.env.VITE_API_URL || 'http://localhost:8000'}</code>
        </p>
        <p style={{ fontSize: '0.85rem', color: '#666', margin: 0 }}>
          Health check: <a href="/api/health" target="_blank" rel="noreferrer" style={{ color: '#4c6ef5' }}>/api/health</a>
        </p>
      </section>
    </div>
  );
}

// ── Appearance Settings ───────────────────────────────────────────────────────

function AppearanceSettings() {
  const store = useAppearanceStore();
  const set = store.set;

  const row: React.CSSProperties = {
    display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10,
  };
  const lbl: React.CSSProperties = {
    width: 170, fontSize: '0.85rem', fontWeight: 500, flexShrink: 0,
  };
  const inputStyle: React.CSSProperties = {
    padding: '5px 8px', borderRadius: 4, border: '1px solid #ccc', fontSize: '0.85rem',
  };

  return (
    <div style={{ display: 'flex', gap: '2rem', flexWrap: 'wrap', alignItems: 'flex-start' }}>

      {/* ── Controls panel ── */}
      <div style={{ flex: '1 1 340px', minWidth: 300 }}>

        {/* Presets */}
        <section style={{ marginBottom: '1.5rem' }}>
          <h3 style={{ marginTop: 0, marginBottom: 8 }}>Presets</h3>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {Object.keys(PRESETS).map((name) => (
              <button
                key={name}
                onClick={() => set({ ...DEFAULTS, ...PRESETS[name] })}
                style={{
                  padding: '5px 10px', fontSize: '0.8rem', borderRadius: 4,
                  border: '1px solid #ccc', background: '#f5f7fb', cursor: 'pointer',
                }}
              >
                {name}
              </button>
            ))}
            <button
              onClick={() => store.reset()}
              style={{
                padding: '5px 10px', fontSize: '0.8rem', borderRadius: 4,
                border: '1px solid #e88', background: '#fff0f0', cursor: 'pointer', color: '#c00',
              }}
            >
              Reset to defaults
            </button>
          </div>
        </section>

        {/* Font */}
        <section style={{ marginBottom: '1.5rem' }}>
          <h3 style={{ marginTop: 0, marginBottom: 8 }}>Typography</h3>
          <div style={row}>
            <span style={lbl}>Font family</span>
            <select
              value={store.fontFamily}
              onChange={(e) => set({ fontFamily: e.target.value })}
              style={{ ...inputStyle, flex: 1 }}
            >
              {FONT_OPTIONS.map((f) => (
                <option key={f.value} value={f.value}>{f.label}</option>
              ))}
            </select>
          </div>
        </section>

        {/* Page colours */}
        <section style={{ marginBottom: '1.5rem' }}>
          <h3 style={{ marginTop: 0, marginBottom: 8 }}>Page</h3>
          <ColorRow label="Background" value={store.bg} onChange={(v) => set({ bg: v })} style={row} lbl={lbl} />
          <ColorRow label="Text" value={store.text} onChange={(v) => set({ text: v })} style={row} lbl={lbl} />
          <ColorRow label="Muted text" value={store.textMuted} onChange={(v) => set({ textMuted: v })} style={row} lbl={lbl} />
          <ColorRow label="Border" value={store.border} onChange={(v) => set({ border: v })} style={row} lbl={lbl} />
          <ColorRow label="Accent / links" value={store.accent} onChange={(v) => set({ accent: v })} style={row} lbl={lbl} />
          <ColorRow label="Surface (cards)" value={store.surface} onChange={(v) => set({ surface: v })} style={row} lbl={lbl} />
          <ColorRow label="Surface alt (tables)" value={store.surfaceAlt} onChange={(v) => set({ surfaceAlt: v })} style={row} lbl={lbl} />
        </section>

        {/* Sidebar */}
        <section style={{ marginBottom: '1.5rem' }}>
          <h3 style={{ marginTop: 0, marginBottom: 8 }}>Sidebar</h3>
          <div style={row}>
            <span style={lbl}>Width</span>
            <input
              type="range" min={160} max={320} step={5}
              value={store.sidebarWidth}
              onChange={(e) => set({ sidebarWidth: Number(e.target.value) })}
              style={{ flex: 1 }}
            />
            <span style={{ fontSize: '0.8rem', minWidth: 36 }}>{store.sidebarWidth}px</span>
          </div>
          <ColorRow label="Background" value={store.sidebarBg} onChange={(v) => set({ sidebarBg: v })} style={row} lbl={lbl} />
          <ColorRow label="Border" value={store.sidebarBorder} onChange={(v) => set({ sidebarBorder: v })} style={row} lbl={lbl} />
          <ColorRow label="Text" value={store.sidebarText} onChange={(v) => set({ sidebarText: v })} style={row} lbl={lbl} />
          <ColorRow label="Muted text" value={store.sidebarTextMuted} onChange={(v) => set({ sidebarTextMuted: v })} style={row} lbl={lbl} />
          <ColorRow label="Hover background" value={store.sidebarHoverBg} onChange={(v) => set({ sidebarHoverBg: v })} style={row} lbl={lbl} />
          <ColorRow label="Active background" value={store.sidebarActiveBg} onChange={(v) => set({ sidebarActiveBg: v })} style={row} lbl={lbl} />
          <ColorRow label="Active text" value={store.sidebarActiveText} onChange={(v) => set({ sidebarActiveText: v })} style={row} lbl={lbl} />
        </section>
      </div>

      {/* ── Live preview ── */}
      <div style={{ flex: '0 0 320px' }}>
        <h3 style={{ marginTop: 0, marginBottom: 8 }}>Live Preview</h3>
        <AppPreview store={store} />
      </div>
    </div>
  );
}

function ColorRow({
  label, value, onChange, style, lbl,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  style: React.CSSProperties;
  lbl: React.CSSProperties;
}) {
  return (
    <div style={style}>
      <span style={lbl}>{label}</span>
      <input
        type="color"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={{ width: 36, height: 28, padding: 2, border: '1px solid #ccc', borderRadius: 4, cursor: 'pointer' }}
      />
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        style={{ width: 88, padding: '4px 6px', fontFamily: 'monospace', fontSize: '0.8rem', border: '1px solid #ccc', borderRadius: 4 }}
      />
    </div>
  );
}

// ── Change Log ────────────────────────────────────────────────────────────────

function ChangeLogSettings() {
  const [selected, setSelected] = useState<string | null>(null);

  const { data: entries = [], isLoading } = useQuery({
    queryKey: ['changelog'],
    queryFn: changelogApi.list,
    staleTime: 5 * 60 * 1000,
  });

  const { data: detail, isLoading: detailLoading } = useQuery({
    queryKey: ['changelog', selected],
    queryFn: () => changelogApi.get(selected!),
    enabled: !!selected,
    staleTime: 60 * 60 * 1000,
  });

  if (selected) {
    return (
      <div style={{ maxWidth: 760 }}>
        <button
          onClick={() => setSelected(null)}
          style={{ marginBottom: 16, padding: '5px 14px', borderRadius: 4, border: '1px solid #ccc', background: '#f5f7fb', cursor: 'pointer', fontSize: '0.85rem' }}
        >
          ← Back to list
        </button>
        {detailLoading && <p style={{ color: '#888' }}>Loading…</p>}
        {detail && <MarkdownView content={detail.content} />}
      </div>
    );
  }

  return (
    <div style={{ maxWidth: 600 }}>
      <p style={{ margin: '0 0 1rem', color: '#666', fontSize: '0.85rem' }}>
        Release notes for each version. Click an entry to read the full changelog.
      </p>
      {isLoading && <p style={{ color: '#888' }}>Loading…</p>}
      {!isLoading && entries.length === 0 && (
        <p style={{ color: '#888' }}>No changelogs found.</p>
      )}
      <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
        {entries.map((e) => (
          <button
            key={e.filename}
            onClick={() => setSelected(e.filename)}
            style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '12px 16px', borderRadius: 6,
              border: '1px solid #e0e4f0', background: '#fff',
              cursor: 'pointer', textAlign: 'left',
              transition: 'background 0.15s',
            }}
            onMouseEnter={(ev) => (ev.currentTarget.style.background = '#f5f7ff')}
            onMouseLeave={(ev) => (ev.currentTarget.style.background = '#fff')}
          >
            <div>
              <span style={{ fontWeight: 700, fontSize: '0.95rem', color: '#4c6ef5' }}>{e.version}</span>
              <span style={{ marginLeft: 12, fontSize: '0.85rem', color: '#666' }}>{e.date}</span>
            </div>
            <span style={{ fontSize: '0.8rem', color: '#aaa' }}>View →</span>
          </button>
        ))}
      </div>
    </div>
  );
}

function MarkdownView({ content }: { content: string }) {
  // Minimal markdown renderer: headings, bold, bullet lists, horizontal rules
  const lines = content.split('\n');
  const elements: React.ReactNode[] = [];
  let key = 0;

  const renderInline = (text: string): React.ReactNode => {
    // Bold **text**
    const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g);
    return parts.map((part, i) => {
      if (part.startsWith('**') && part.endsWith('**'))
        return <strong key={i}>{part.slice(2, -2)}</strong>;
      if (part.startsWith('`') && part.endsWith('`'))
        return <code key={i} style={{ background: '#f0f2fa', padding: '1px 4px', borderRadius: 3, fontFamily: 'monospace', fontSize: '0.88em' }}>{part.slice(1, -1)}</code>;
      return part;
    });
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.startsWith('# ')) {
      elements.push(<h1 key={key++} style={{ fontSize: '1.4rem', margin: '0.5rem 0 0.75rem', borderBottom: '2px solid #e0e4f0', paddingBottom: 8 }}>{renderInline(line.slice(2))}</h1>);
    } else if (line.startsWith('## ')) {
      elements.push(<h2 key={key++} style={{ fontSize: '1.1rem', margin: '1.25rem 0 0.5rem', color: '#3b5bdb' }}>{renderInline(line.slice(3))}</h2>);
    } else if (line.startsWith('### ')) {
      elements.push(<h3 key={key++} style={{ fontSize: '0.95rem', margin: '1rem 0 0.25rem', color: '#555' }}>{renderInline(line.slice(4))}</h3>);
    } else if (line.startsWith('- ')) {
      elements.push(<li key={key++} style={{ marginLeft: 20, marginBottom: 3, fontSize: '0.9rem' }}>{renderInline(line.slice(2))}</li>);
    } else if (line.trim() === '---') {
      elements.push(<hr key={key++} style={{ border: 'none', borderTop: '1px solid #e0e4f0', margin: '1rem 0' }} />);
    } else if (line.trim() === '') {
      elements.push(<div key={key++} style={{ height: 6 }} />);
    } else {
      elements.push(<p key={key++} style={{ margin: '0 0 6px', fontSize: '0.9rem', lineHeight: 1.6 }}>{renderInline(line)}</p>);
    }
  }

  return (
    <div style={{ background: '#fff', border: '1px solid #e0e4f0', borderRadius: 8, padding: '24px 28px', lineHeight: 1.6 }}>
      {elements}
    </div>
  );
}

import type { AppearanceState } from '../store/appearanceStore';

function AppPreview({ store }: { store: AppearanceState }) {
  const NAV_ITEMS = ['🔍 Search', '💳 My Collection', '📚 Card Sets', '⚙️ Settings', '❓ Help'];
  const ACTIVE = '⚙️ Settings';

  const previewStyle: React.CSSProperties = {
    border: '1px solid #ccc',
    borderRadius: 8,
    overflow: 'hidden',
    boxShadow: '0 2px 12px rgba(0,0,0,0.12)',
    fontFamily: store.fontFamily,
    fontSize: '12px',
    display: 'flex',
    height: 340,
  };

  const sidebarStyle: React.CSSProperties = {
    width: Math.min(store.sidebarWidth * 0.65, 130),
    background: store.sidebarBg,
    display: 'flex',
    flexDirection: 'column',
    flexShrink: 0,
  };

  const logoStyle: React.CSSProperties = {
    padding: '8px 10px',
    borderBottom: `1px solid ${store.sidebarBorder}`,
    color: store.sidebarActiveText,
    fontWeight: 700,
    fontSize: '11px',
  };

  const navStyle: React.CSSProperties = {
    display: 'flex',
    flexDirection: 'column',
    padding: '6px 0',
    flex: 1,
  };

  const contentStyle: React.CSSProperties = {
    flex: 1,
    background: store.bg,
    padding: '12px 14px',
    overflowY: 'auto',
    color: store.text,
  };

  return (
    <div style={previewStyle}>
      {/* Mini sidebar */}
      <div style={sidebarStyle}>
        <div style={logoStyle}>🃏 Collectibles</div>

        {/* Owner selector mock */}
        <div style={{ padding: '6px 10px', borderBottom: `1px solid ${store.sidebarBorder}` }}>
          <div style={{ fontSize: '9px', textTransform: 'uppercase', color: store.sidebarTextMuted, letterSpacing: '0.05em', marginBottom: 3 }}>Owner</div>
          <div style={{ background: store.sidebarHoverBg, border: `1px solid ${store.sidebarBorder}`, borderRadius: 3, padding: '2px 5px', color: store.sidebarText, fontSize: '10px' }}>
            John ▾
          </div>
        </div>

        <div style={navStyle}>
          {NAV_ITEMS.map((item) => {
            const isActive = item === ACTIVE;
            return (
              <div
                key={item}
                style={{
                  padding: '5px 10px',
                  background: isActive ? store.sidebarActiveBg : 'transparent',
                  color: isActive ? store.sidebarActiveText : store.sidebarText,
                  fontWeight: isActive ? 700 : 400,
                  fontSize: '10px',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {item}
              </div>
            );
          })}
        </div>
      </div>

      {/* Mini content */}
      <div style={contentStyle}>
        <div style={{ fontWeight: 700, fontSize: '14px', marginBottom: 10, color: store.text }}>Settings</div>

        {/* Mock tab bar */}
        <div style={{ display: 'flex', gap: 3, marginBottom: 10, borderBottom: `1px solid ${store.border}`, paddingBottom: 6 }}>
          {['General', 'Appearance', 'Sources', 'Debug'].map((t) => (
            <div
              key={t}
              style={{
                padding: '2px 7px',
                borderRadius: '3px 3px 0 0',
                background: t === 'Appearance' ? store.accent : store.surfaceAlt,
                color: t === 'Appearance' ? '#fff' : store.textMuted,
                fontSize: '9px',
                cursor: 'default',
              }}
            >{t}</div>
          ))}
        </div>

        {/* Mock content card */}
        <div style={{ background: store.surface, border: `1px solid ${store.border}`, borderRadius: 5, padding: 8, marginBottom: 8 }}>
          <div style={{ fontSize: '10px', fontWeight: 700, marginBottom: 5, color: store.text }}>Presets</div>
          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
            {['Dark Navy', 'Light', 'Forest'].map((p) => (
              <div key={p} style={{ padding: '2px 6px', background: store.surfaceAlt, border: `1px solid ${store.border}`, borderRadius: 3, fontSize: '9px', color: store.textMuted }}>{p}</div>
            ))}
          </div>
        </div>

        {/* Mock color row */}
        <div style={{ background: store.surface, border: `1px solid ${store.border}`, borderRadius: 5, padding: 8 }}>
          <div style={{ fontSize: '10px', fontWeight: 700, marginBottom: 6, color: store.text }}>Page</div>
          {[['Background', store.bg], ['Accent', store.accent], ['Text', store.text]].map(([name, color]) => (
            <div key={name} style={{ display: 'flex', alignItems: 'center', gap: 5, marginBottom: 4 }}>
              <div style={{ width: 60, fontSize: '9px', color: store.textMuted }}>{name}</div>
              <div style={{ width: 14, height: 14, borderRadius: 3, background: color, border: `1px solid ${store.border}` }} />
              <div style={{ fontFamily: 'monospace', fontSize: '9px', color: store.textMuted }}>{color}</div>
            </div>
          ))}
        </div>

        {/* Mock link */}
        <div style={{ marginTop: 8, fontSize: '10px' }}>
          Sample <span style={{ color: store.accent, cursor: 'pointer' }}>link text</span> in accent colour.
        </div>
      </div>
    </div>
  );
}

function AboutSettings() {
  const APP_VERSION = '2.3.0';

  const sectionStyle: React.CSSProperties = {
    background: '#fff', border: '1px solid #e0e4f0', borderRadius: 8,
    padding: '24px 28px', marginBottom: '1rem',
  };
  const headingStyle: React.CSSProperties = {
    margin: '0 0 0.5rem', fontSize: '1rem', fontWeight: 700, color: '#222',
  };
  const textStyle: React.CSSProperties = {
    fontSize: '0.9rem', color: '#444', lineHeight: 1.7, margin: '0 0 0.5rem',
  };
  const linkStyle: React.CSSProperties = {
    color: '#4c6ef5', textDecoration: 'none', fontWeight: 600,
  };
  const badgeStyle: React.CSSProperties = {
    display: 'inline-block', background: '#eef1ff', color: '#3b5bdb',
    borderRadius: 6, padding: '2px 10px', fontSize: '0.85rem',
    fontWeight: 700, border: '1px solid #c5cff7',
  };

  return (
    <div>
      {/* Logo / version block */}
      <div style={{ ...sectionStyle, display: 'flex', alignItems: 'center', gap: '1.5rem' }}>
        <div>
          <div style={{ fontSize: '2.4rem', lineHeight: 1 }}>💳</div>
        </div>
        <div>
          <h2 style={{ margin: '0 0 4px', fontSize: '1.3rem', fontWeight: 700 }}>
            Collectibles Manager
          </h2>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
            <span style={badgeStyle}>v{APP_VERSION}</span>
          </div>
          <p style={{ ...textStyle, margin: 0 }}>
            A personal collection tracker for Magic: The Gathering, Pokémon, Sports Cards, Coins, and more.
          </p>
        </div>
      </div>

      {/* About */}
      <div style={sectionStyle}>
        <h3 style={headingStyle}>About</h3>
        <p style={textStyle}>
          Collectibles Manager is a self-hosted app for tracking and valuing your collectibles. Search cards and
          coins using live data from Scryfall, Pokémon TCG API, Sports Card Database, and the NGC Price Guide,
          then save them to your personal collection with pricing, grades, and images.
        </p>
        <p style={textStyle}>
          Features include multi-owner support, portfolio investment tracking, import/export, a built-in
          watchlist, and automatic price updates — all running locally with no subscription required.
        </p>
      </div>

      {/* Links */}
      <div style={sectionStyle}>
        <h3 style={headingStyle}>Links</h3>
        <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: '1.1rem' }}>🌐</span>
            <span style={textStyle}>
              <a href="https://y2cl.net" target="_blank" rel="noreferrer" style={linkStyle}>
                y2cl.net
              </a>
              {' '}— y2cl home
            </span>
          </div>
        </div>
      </div>

      {/* Build info */}
      <div style={{ ...sectionStyle, background: '#fafbff' }}>
        <h3 style={headingStyle}>Build Info</h3>
        <table style={{ fontSize: '0.85rem', borderCollapse: 'collapse', width: '100%' }}>
          <tbody>
            {[
              ['Version',  APP_VERSION],
              ['Frontend', 'React 18 + TypeScript + Vite'],
              ['Backend',  'Python · FastAPI · SQLite'],
              ['Pricing',  'Scryfall · NGC · Pokémon TCG API · Sports Card Database'],
            ].map(([label, value]) => (
              <tr key={label} style={{ borderBottom: '1px solid #eef0f8' }}>
                <td style={{ padding: '6px 0', color: '#888', width: 120, fontWeight: 600 }}>{label}</td>
                <td style={{ padding: '6px 0', color: '#333' }}>{value}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
