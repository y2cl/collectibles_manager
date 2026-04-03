import { NavLink } from 'react-router-dom';
import { useOwners } from '../../hooks/useOwners';
import { useOwnerStore } from '../../store/ownerStore';
import styles from './Sidebar.module.css';

const NAV: { to: string; label: string }[] = [
  { to: '/search', label: '➕ Add to Collection' },
  { to: '/collection', label: '💳 My Collection' },
  { to: '/sets', label: '📚 Card Sets' },
  { to: '/settings', label: '⚙️ Settings' },
  { to: '/help', label: '❓ Help' },
];

export default function Sidebar() {
  const { data: owners = [] } = useOwners();
  const { currentOwnerId, currentProfileId, setOwner, setProfile } = useOwnerStore();

  const currentOwner = owners.find((o) => o.owner_id === currentOwnerId);
  const profiles = currentOwner?.profiles ?? [];

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
    </aside>
  );
}
