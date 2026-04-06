import { useState } from 'react';
import { NavLink } from 'react-router-dom';
import { useOwners } from '../../hooks/useOwners';
import { useOwnerStore } from '../../store/ownerStore';
import { devApi } from '../../api/dev';
import styles from './Sidebar.module.css';

const NAV: { to: string; label: string }[] = [
  { to: '/search',     label: '➕ Add to Collection' },
  { to: '/collection', label: '💳 My Collection' },
  { to: '/sets',       label: '📚 Card Sets' },
  { to: '/settings',   label: '⚙️ Settings' },
  { to: '/help',       label: '❓ Help' },
];

type BuildPhase = 'idle' | 'building' | 'restarting' | 'waiting' | 'done' | 'error';

export default function Sidebar() {
  const { data: owners = [] } = useOwners();
  const { currentOwnerId, currentProfileId, setOwner, setProfile } = useOwnerStore();

  const currentOwner = owners.find((o) => o.owner_id === currentOwnerId);
  const profiles = currentOwner?.profiles ?? [];

  const [phase, setPhase]   = useState<BuildPhase>('idle');
  const [log, setLog]       = useState('');
  const [logError, setLogError] = useState(false);

  const phaseLabel: Record<BuildPhase, string> = {
    idle:       '🔄 Build & Refresh',
    building:   '⚙️  Building…',
    restarting: '🔁 Restarting…',
    waiting:    '⏳ Waiting for server…',
    done:       '✓ Done — reloading…',
    error:      '⚠️  Build failed — see log',
  };

  const handleBuildAndRefresh = async () => {
    setPhase('building');
    setLog('');
    setLogError(false);

    // ── Step 1: rebuild frontend ──────────────────────────────────────────────
    let buildResult;
    try {
      buildResult = await devApi.rebuild();
    } catch (e) {
      setLog(e instanceof Error ? e.message : 'Request to /api/dev/rebuild failed');
      setLogError(true);
      setPhase('error');
      return;
    }

    const output = [buildResult.stdout, buildResult.stderr].filter(Boolean).join('\n').trim();
    setLog(output);

    if (!buildResult.success) {
      setLogError(true);
      setPhase('error');
      return;
    }

    // ── Step 2: restart the backend process ───────────────────────────────────
    setPhase('restarting');
    try {
      await devApi.restart();
    } catch {
      // The server may close the connection before responding — that's fine
    }

    // ── Step 3: poll until the server is back ─────────────────────────────────
    setPhase('waiting');
    const back = await devApi.waitForServer();

    if (!back) {
      // Build succeeded even if the server took too long to respond — let the
      // user reload manually rather than treating this as a hard failure.
      setLog((prev) => (prev ? prev + '\n' : '') + 'Server poll timed out — click Refresh to reload when ready.');
      setPhase('error');
      return;
    }

    // ── Step 4: hard reload ───────────────────────────────────────────────────
    setPhase('done');
    setTimeout(() => window.location.reload(), 600);
  };

  return (
    <aside className={styles.sidebar}>
      <div className={styles.logo}>
        <span>🃏</span>
        <span className={styles.logoText}>Collectibles</span>
      </div>

      {/* Owner selector */}
      <div className={styles.section}>
        <label className={styles.label}>Owner</label>
        <select
          className={styles.select}
          value={currentOwnerId ?? ''}
          onChange={(e) => setOwner(e.target.value)}
        >
          <option value="">— select owner —</option>
          {owners.map((o) => (
            <option key={o.owner_id} value={o.owner_id}>
              {o.label}
            </option>
          ))}
        </select>

        {profiles.length > 1 && (
          <>
            <label className={styles.label} style={{ marginTop: '0.5rem' }}>Collection Set</label>
            <select
              className={styles.select}
              value={currentProfileId}
              onChange={(e) => setProfile(e.target.value)}
            >
              {profiles.map((p) => (
                <option key={p.profile_id} value={p.profile_id}>
                  {p.profile_id}
                </option>
              ))}
            </select>
          </>
        )}
      </div>

      {/* Navigation */}
      <nav className={styles.nav}>
        {NAV.map(({ to, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              [styles.navLink, isActive ? styles.active : ''].join(' ')
            }
          >
            {label}
          </NavLink>
        ))}
      </nav>

      {/* ── Build & Refresh ── */}
      <div className={styles.footer}>
        <button
          className={styles.buildBtn}
          onClick={handleBuildAndRefresh}
          disabled={phase !== 'idle' && phase !== 'error'}
          title="Rebuild the frontend and restart the backend server"
        >
          {phaseLabel[phase]}
        </button>

        {log && (
          <div className={[styles.buildLog, logError ? styles.buildLogError : ''].join(' ')}>
            {log}
          </div>
        )}

        {phase !== 'idle' && phase !== 'error' && (
          <span className={styles.buildStatus}>
            {phase === 'building'   && 'Running npm run build…'}
            {phase === 'restarting' && 'Restarting uvicorn process…'}
            {phase === 'waiting'    && 'Polling /api/health…'}
            {phase === 'done'       && 'Server is back — reloading page…'}
          </span>
        )}

        {phase === 'error' && (
          <div style={{ display: 'flex', gap: '0.4rem' }}>
            <button
              className={styles.buildBtn}
              onClick={() => window.location.reload()}
              style={{ fontSize: '0.72rem' }}
            >
              ↺ Refresh page
            </button>
            <button
              className={styles.buildBtn}
              onClick={() => { setPhase('idle'); setLog(''); setLogError(false); }}
              style={{ fontSize: '0.72rem', opacity: 0.6 }}
            >
              ✕ Dismiss
            </button>
          </div>
        )}
      </div>
    </aside>
  );
}
