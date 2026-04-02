import { useState, useRef } from 'react';
import { useOwnerStore } from '../../store/ownerStore';
import { exportApi } from '../../api/export';
import { useQueryClient } from '@tanstack/react-query';

export default function ImportExportTab() {
  const { currentOwnerId, currentProfileId } = useOwnerStore();
  const qc = useQueryClient();
  const fileRef = useRef<HTMLInputElement>(null);

  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState<{ imported: number; ambiguous: number } | null>(null);
  const [error, setError] = useState('');

  const btnStyle: React.CSSProperties = {
    padding: '6px 14px', borderRadius: 4, border: 'none', cursor: 'pointer', fontSize: '0.85rem',
  };

  const handleImport = async () => {
    const file = fileRef.current?.files?.[0];
    if (!file || !currentOwnerId) return;
    setImporting(true);
    setError('');
    try {
      const result = await exportApi.importCsv(file, currentOwnerId, currentProfileId);
      setImportResult(result);
      qc.invalidateQueries({ queryKey: ['collection', currentOwnerId] });
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Import failed');
    } finally {
      setImporting(false);
    }
  };

  const handleExportCsv = () => {
    if (!currentOwnerId) return;
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = '/api/export/csv';
    const addField = (name: string, value: string) => {
      const input = document.createElement('input');
      input.type = 'hidden'; input.name = name; input.value = value;
      form.appendChild(input);
    };
    addField('owner_id', currentOwnerId);
    addField('profile_id', currentProfileId);
    document.body.appendChild(form);
    form.submit();
    document.body.removeChild(form);
  };

  const handleExportZip = handleExportCsv; // same pattern with /api/export/zip

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      <section>
        <h3 style={{ marginTop: 0 }}>Import CSV</h3>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <input type="file" accept=".csv" ref={fileRef} />
          <button
            onClick={handleImport}
            disabled={importing || !currentOwnerId}
            style={{ ...btnStyle, background: '#4c6ef5', color: '#fff' }}
          >
            {importing ? 'Importing…' : 'Import'}
          </button>
        </div>
        {importResult && (
          <p style={{ color: '#2b7a2b', marginTop: 8 }}>
            Imported {importResult.imported} cards.
            {importResult.ambiguous > 0 && ` ${importResult.ambiguous} cards need disambiguation.`}
          </p>
        )}
        {error && <p style={{ color: '#c0392b', marginTop: 8 }}>{error}</p>}
      </section>

      <section>
        <h3 style={{ marginTop: 0 }}>Export</h3>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button
            onClick={handleExportCsv}
            disabled={!currentOwnerId}
            style={{ ...btnStyle, background: '#2b7a2b', color: '#fff' }}
          >
            ⬇ Export CSV
          </button>
          <button
            onClick={handleExportZip}
            disabled={!currentOwnerId}
            style={{ ...btnStyle, background: '#555', color: '#fff' }}
          >
            ⬇ Export ZIP (all profiles)
          </button>
        </div>
      </section>
    </div>
  );
}
