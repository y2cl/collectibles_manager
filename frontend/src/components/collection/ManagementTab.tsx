import { useState } from 'react';
import { useOwners, useCreateOwner, useCreateProfile } from '../../hooks/useOwners';
import { useOwnerStore } from '../../store/ownerStore';

export default function ManagementTab() {
  const { data: owners = [] } = useOwners();
  const { currentOwnerId } = useOwnerStore();
  const createOwner = useCreateOwner();
  const createProfile = useCreateProfile();
  const [newOwner, setNewOwner] = useState('');
  const [newProfile, setNewProfile] = useState('');
  const [msg, setMsg] = useState('');

  const btnStyle: React.CSSProperties = {
    padding: '6px 14px', borderRadius: 4, border: 'none',
    cursor: 'pointer', background: '#4c6ef5', color: '#fff', fontSize: '0.85rem',
  };

  const handleCreateOwner = async () => {
    if (!newOwner.trim()) return;
    try {
      await createOwner.mutateAsync(newOwner.trim());
      setMsg(`Created owner: ${newOwner}`);
      setNewOwner('');
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : 'Error creating owner');
    }
  };

  const handleCreateProfile = async () => {
    if (!newProfile.trim() || !currentOwnerId) return;
    try {
      await createProfile.mutateAsync({ owner_id: currentOwnerId, name: newProfile.trim() });
      setMsg(`Created profile: ${newProfile}`);
      setNewProfile('');
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : 'Error creating profile');
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {msg && <p style={{ color: '#2b7a2b', margin: 0 }}>{msg}</p>}

      <section>
        <h3 style={{ marginTop: 0 }}>Create New Owner</h3>
        <div style={{ display: 'flex', gap: 8 }}>
          <input
            placeholder="Owner name"
            value={newOwner}
            onChange={(e) => setNewOwner(e.target.value)}
            style={{ padding: '6px 10px', borderRadius: 4, border: '1px solid #ccc', flex: 1 }}
          />
          <button onClick={handleCreateOwner} style={btnStyle}>Create</button>
        </div>
      </section>

      {currentOwnerId && (
        <section>
          <h3 style={{ marginTop: 0 }}>Create Collection Profile for {currentOwnerId}</h3>
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              placeholder="Profile name (e.g. vintage, foils)"
              value={newProfile}
              onChange={(e) => setNewProfile(e.target.value)}
              style={{ padding: '6px 10px', borderRadius: 4, border: '1px solid #ccc', flex: 1 }}
            />
            <button onClick={handleCreateProfile} style={btnStyle}>Create</button>
          </div>
        </section>
      )}

      <section>
        <h3 style={{ marginTop: 0 }}>Existing Owners</h3>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.85rem' }}>
          <thead>
            <tr style={{ background: '#f5f7fb', textAlign: 'left' }}>
              <th style={{ padding: '6px 8px' }}>Owner</th>
              <th>Slug</th>
              <th>Profiles</th>
            </tr>
          </thead>
          <tbody>
            {owners.map((o) => (
              <tr key={o.owner_id} style={{ borderBottom: '1px solid #eee' }}>
                <td style={{ padding: '5px 8px' }}>{o.label}</td>
                <td>{o.owner_id}</td>
                <td>{o.profiles.map((p) => p.profile_id).join(', ')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
