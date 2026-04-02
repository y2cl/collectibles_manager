import { useState } from 'react';
import {
  useOwners, useCreateOwner, useCreateProfile,
  useUpdateOwner, useDeleteOwner, useUpdateProfile, useDeleteProfile,
} from '../../hooks/useOwners';
import { useOwnerStore } from '../../store/ownerStore';

export default function ManagementTab() {
  const { data: owners = [] } = useOwners();
  const { currentOwnerId, currentProfileId, reset, setProfile } = useOwnerStore();
  const createOwner = useCreateOwner();
  const createProfile = useCreateProfile();
  const updateOwner = useUpdateOwner();
  const deleteOwner = useDeleteOwner();
  const updateProfile = useUpdateProfile();
  const deleteProfile = useDeleteProfile();

  const [newOwner, setNewOwner] = useState('');
  const [newProfile, setNewProfile] = useState('');
  const [msg, setMsg] = useState('');

  const [editingOwnerId, setEditingOwnerId] = useState<string | null>(null);
  const [editLabel, setEditLabel] = useState('');

  // key is "owner_id:profile_id"
  const [editingProfileKey, setEditingProfileKey] = useState<string | null>(null);
  const [editProfileLabel, setEditProfileLabel] = useState('');

  const btnStyle: React.CSSProperties = {
    padding: '6px 14px', borderRadius: 4, border: 'none',
    cursor: 'pointer', background: '#4c6ef5', color: '#fff', fontSize: '0.85rem',
  };
  const smBtn = (bg: string): React.CSSProperties => ({
    padding: '2px 8px', borderRadius: 3, border: 'none',
    cursor: 'pointer', background: bg, color: '#fff', fontSize: '0.75rem',
  });

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

  const handleRenameOwner = async (owner_id: string) => {
    if (!editLabel.trim()) return;
    try {
      await updateOwner.mutateAsync({ owner_id, label: editLabel.trim() });
      setMsg(`Renamed owner to: ${editLabel.trim()}`);
      setEditingOwnerId(null);
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : 'Error renaming owner');
    }
  };

  const handleDeleteOwner = async (owner_id: string, label: string) => {
    if (!window.confirm(`Delete owner "${label}"? This will permanently delete all their profiles, cards, and watchlist items.`)) return;
    try {
      await deleteOwner.mutateAsync(owner_id);
      if (currentOwnerId === owner_id) {
        reset();
      }
      setMsg(`Deleted owner: ${label}`);
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : 'Error deleting owner');
    }
  };

  const handleRenameProfile = async (owner_id: string, profile_id: string) => {
    if (!editProfileLabel.trim()) return;
    try {
      await updateProfile.mutateAsync({ owner_id, profile_id, new_profile_id: editProfileLabel.trim() });
      if (currentOwnerId === owner_id && currentProfileId === profile_id) {
        setProfile(editProfileLabel.trim());
      }
      setMsg(`Renamed profile to: ${editProfileLabel.trim()}`);
      setEditingProfileKey(null);
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : 'Error renaming profile');
    }
  };

  const handleDeleteProfile = async (owner_id: string, profile_id: string) => {
    if (!window.confirm(`Delete profile "${profile_id}"? Cards in this profile will be removed.`)) return;
    try {
      await deleteProfile.mutateAsync({ owner_id, profile_id });
      if (currentOwnerId === owner_id && currentProfileId === profile_id) {
        setProfile('default');
      }
      setMsg(`Deleted profile: ${profile_id}`);
    } catch (e: unknown) {
      setMsg(e instanceof Error ? e.message : 'Error deleting profile');
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
              <th style={{ padding: '6px 8px' }}>Slug</th>
              <th style={{ padding: '6px 8px' }}>Profiles</th>
              <th style={{ padding: '6px 8px' }}>Actions</th>
            </tr>
          </thead>
          <tbody>
            {owners.map((o) => (
              <>
                <tr key={o.owner_id} style={{ borderBottom: o.profiles.length === 0 ? '1px solid #eee' : undefined }}>
                  <td style={{ padding: '5px 8px' }}>
                    {editingOwnerId === o.owner_id ? (
                      <div style={{ display: 'flex', gap: 4 }}>
                        <input
                          value={editLabel}
                          onChange={(e) => setEditLabel(e.target.value)}
                          onKeyDown={(e) => { if (e.key === 'Enter') handleRenameOwner(o.owner_id); if (e.key === 'Escape') setEditingOwnerId(null); }}
                          autoFocus
                          style={{ padding: '2px 6px', borderRadius: 3, border: '1px solid #aaa', fontSize: '0.85rem' }}
                        />
                        <button onClick={() => handleRenameOwner(o.owner_id)} style={smBtn('#2b7a2b')}>Save</button>
                        <button onClick={() => setEditingOwnerId(null)} style={smBtn('#888')}>Cancel</button>
                      </div>
                    ) : o.label}
                  </td>
                  <td style={{ padding: '5px 8px' }}>{o.owner_id}</td>
                  <td style={{ padding: '5px 8px' }}></td>
                  <td style={{ padding: '5px 8px' }}>
                    {editingOwnerId !== o.owner_id && (
                      <div style={{ display: 'flex', gap: 4 }}>
                        <button
                          onClick={() => { setEditingOwnerId(o.owner_id); setEditLabel(o.label); }}
                          style={smBtn('#4c6ef5')}
                        >Edit</button>
                        <button
                          onClick={() => handleDeleteOwner(o.owner_id, o.label)}
                          style={smBtn('#fa5252')}
                        >Delete</button>
                      </div>
                    )}
                  </td>
                </tr>
                {o.profiles.map((p, i) => {
                  const profileKey = `${o.owner_id}:${p.profile_id}`;
                  const isLast = i === o.profiles.length - 1;
                  return (
                    <tr key={profileKey} style={{ borderBottom: isLast ? '1px solid #eee' : undefined, background: '#fafafa' }}>
                      <td style={{ padding: '3px 8px 3px 24px', color: '#666' }}></td>
                      <td style={{ padding: '3px 8px', color: '#666', fontSize: '0.8rem' }}>↳ profile</td>
                      <td style={{ padding: '3px 8px' }}>
                        {editingProfileKey === profileKey ? (
                          <div style={{ display: 'flex', gap: 4 }}>
                            <input
                              value={editProfileLabel}
                              onChange={(e) => setEditProfileLabel(e.target.value)}
                              onKeyDown={(e) => { if (e.key === 'Enter') handleRenameProfile(o.owner_id, p.profile_id); if (e.key === 'Escape') setEditingProfileKey(null); }}
                              autoFocus
                              style={{ padding: '2px 6px', borderRadius: 3, border: '1px solid #aaa', fontSize: '0.8rem' }}
                            />
                            <button onClick={() => handleRenameProfile(o.owner_id, p.profile_id)} style={smBtn('#2b7a2b')}>Save</button>
                            <button onClick={() => setEditingProfileKey(null)} style={smBtn('#888')}>Cancel</button>
                          </div>
                        ) : (
                          <span style={{ fontSize: '0.8rem' }}>{p.profile_id}</span>
                        )}
                      </td>
                      <td style={{ padding: '3px 8px' }}>
                        {editingProfileKey !== profileKey && (
                          <div style={{ display: 'flex', gap: 4 }}>
                            <button
                              onClick={() => { setEditingProfileKey(profileKey); setEditProfileLabel(p.profile_id); }}
                              style={smBtn('#4c6ef5')}
                            >Edit</button>
                            <button
                              onClick={() => handleDeleteProfile(o.owner_id, p.profile_id)}
                              style={smBtn('#fa5252')}
                            >Delete</button>
                          </div>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}
