import { useState } from 'react';
import { lookupApi } from '../../api/lookup';
import type { ImageResult } from '../../api/lookup';

interface Props {
  query: string;
  selectedUrl: string;
  onSelect: (url: string) => void;
}

export default function ImagePicker({ query, selectedUrl, onSelect }: Props) {
  const [open, setOpen] = useState(false);
  const [results, setResults] = useState<ImageResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [configured, setConfigured] = useState(true);
  const [error, setError] = useState('');
  const [pasteUrl, setPasteUrl] = useState('');
  const [hoveredUrl, setHoveredUrl] = useState('');

  const handleSearch = async () => {
    if (!query.trim()) return;
    setOpen(true);
    setLoading(true);
    setError('');
    setResults([]);
    try {
      const data = await lookupApi.images(query);
      setConfigured(data.configured);
      setResults(data.results);
      if (data.configured && data.results.length === 0) {
        setError('No images found. Try a different search term.');
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      if (msg.includes('429')) {
        setError('Monthly image search quota reached (250/month). Paste a URL below instead.');
      } else {
        setError('Image search failed. Paste a URL below instead.');
      }
    } finally {
      setLoading(false);
    }
  };

  const handleSelect = (url: string) => {
    onSelect(url);
    setOpen(false);
  };

  const handlePasteApply = () => {
    if (pasteUrl.trim()) {
      onSelect(pasteUrl.trim());
      setPasteUrl('');
      setOpen(false);
    }
  };

  return (
    <div>
      {/* Trigger row */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
        <button
          type="button"
          onClick={handleSearch}
          disabled={!query.trim()}
          style={{
            padding: '5px 12px', fontSize: '0.82rem', borderRadius: 4, border: '1px solid #ccc',
            background: '#f8f9fa', cursor: query.trim() ? 'pointer' : 'not-allowed',
            display: 'flex', alignItems: 'center', gap: 5,
          }}
        >
          🖼️ Find Image
        </button>

        {selectedUrl && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <img
              src={selectedUrl}
              alt="selected"
              style={{ width: 36, height: 36, objectFit: 'contain', borderRadius: 3, border: '1px solid #ddd' }}
              onError={(e) => { (e.target as HTMLImageElement).style.display = 'none'; }}
            />
            <span style={{ fontSize: '0.75rem', color: '#666', maxWidth: 160, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {selectedUrl}
            </span>
            <button
              type="button"
              onClick={() => onSelect('')}
              style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#999', fontSize: '0.8rem', padding: 0 }}
              title="Remove image"
            >
              ✕
            </button>
          </div>
        )}
      </div>

      {/* Picker panel */}
      {open && (
        <div style={{
          marginTop: 10, border: '1px solid #d0d5ee', borderRadius: 8,
          background: '#fff', padding: '12px 14px',
          boxShadow: '0 4px 16px rgba(0,0,0,0.08)',
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
            <span style={{ fontSize: '0.82rem', color: '#555' }}>
              {loading ? 'Searching…' : `Results for "${query}"`}
            </span>
            <button
              type="button"
              onClick={() => setOpen(false)}
              style={{ background: 'none', border: 'none', cursor: 'pointer', fontSize: '1rem', color: '#888', padding: 0 }}
            >
              ✕
            </button>
          </div>

          {/* No API key configured */}
          {!configured && !loading && (
            <div style={{ marginBottom: 12, padding: '8px 10px', background: '#fff8e1', borderRadius: 6, fontSize: '0.82rem', color: '#7a5900' }}>
              <strong>Image search not configured.</strong> To enable it, add a free SerpAPI key to your <code>.env</code>:
              <br />
              <code style={{ fontSize: '0.78rem' }}>SERPAPI_KEY=...</code>
              <br />
              Get a free key (250/month, no credit card) at serpapi.com → sign up → Dashboard
            </div>
          )}

          {error && (
            <p style={{ color: '#c00', fontSize: '0.82rem', margin: '0 0 10px' }}>{error}</p>
          )}

          {/* Image grid */}
          {results.length > 0 && (
            <div style={{
              display: 'grid',
              gridTemplateColumns: 'repeat(auto-fill, minmax(90px, 1fr))',
              gap: 8,
              marginBottom: 12,
              maxHeight: 320,
              overflowY: 'auto',
            }}>
              {results.map((img, i) => (
                <button
                  key={i}
                  type="button"
                  onClick={() => handleSelect(img.url)}
                  onMouseEnter={() => setHoveredUrl(img.url)}
                  onMouseLeave={() => setHoveredUrl('')}
                  title={`${img.title}\n${img.source}`}
                  style={{
                    padding: 0, border: selectedUrl === img.url ? '2px solid #4c6ef5' : '2px solid transparent',
                    borderRadius: 6, cursor: 'pointer', background: '#f5f7fb',
                    overflow: 'hidden', aspectRatio: '1',
                    outline: hoveredUrl === img.url ? '2px solid #a5b4fc' : 'none',
                    transition: 'outline 0.1s',
                  }}
                >
                  <img
                    src={img.thumbnail}
                    alt={img.title}
                    style={{ width: '100%', height: '100%', objectFit: 'cover', display: 'block' }}
                    onError={(e) => {
                      const parent = (e.target as HTMLImageElement).closest('button');
                      if (parent) parent.style.display = 'none';
                    }}
                  />
                </button>
              ))}
            </div>
          )}

          {/* Always-available URL paste fallback */}
          <div style={{ borderTop: results.length > 0 ? '1px solid #eee' : 'none', paddingTop: results.length > 0 ? 10 : 0 }}>
            <p style={{ margin: '0 0 6px', fontSize: '0.78rem', color: '#888' }}>
              Or paste an image URL directly:
            </p>
            <div style={{ display: 'flex', gap: 6 }}>
              <input
                type="url"
                placeholder="https://example.com/image.jpg"
                value={pasteUrl}
                onChange={(e) => setPasteUrl(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); handlePasteApply(); } }}
                style={{ flex: 1, padding: '5px 8px', borderRadius: 4, border: '1px solid #ccc', fontSize: '0.82rem' }}
              />
              <button
                type="button"
                onClick={handlePasteApply}
                disabled={!pasteUrl.trim()}
                style={{
                  padding: '5px 12px', borderRadius: 4, border: 'none',
                  background: pasteUrl.trim() ? '#4c6ef5' : '#ccc',
                  color: '#fff', cursor: pasteUrl.trim() ? 'pointer' : 'default',
                  fontSize: '0.82rem', fontWeight: 600,
                }}
              >
                Use
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
