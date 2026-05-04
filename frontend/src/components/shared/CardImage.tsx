import { useState, useEffect } from 'react';

interface Props {
  src: string;
  alt: string;
  width?: number;
  link?: string;
  isProxy?: boolean;
}

// Inline SVG card-back placeholder — no external dependency, never blocked.
const PLACEHOLDER_SVG = `data:image/svg+xml;utf8,${encodeURIComponent(`
<svg xmlns="http://www.w3.org/2000/svg" width="200" height="280" viewBox="0 0 200 280">
  <rect width="200" height="280" rx="10" fill="#1a1a2e"/>
  <rect x="8" y="8" width="184" height="264" rx="8" fill="none" stroke="#4c6ef5" stroke-width="2"/>
  <text x="100" y="130" text-anchor="middle" font-family="sans-serif" font-size="36" fill="#4c6ef5">🃏</text>
  <text x="100" y="165" text-anchor="middle" font-family="sans-serif" font-size="11" fill="#888">No image</text>
</svg>
`)}`;

/** Returns true if the src is a local filesystem path the browser can't load. */
function isLocalPath(src: string): boolean {
  return (
    src.startsWith('/Users/') ||
    src.startsWith('/home/') ||
    src.startsWith('C:\\') ||
    src.startsWith('C:/') ||
    (src.startsWith('/') && !src.startsWith('//') && !src.startsWith('/api/'))
  );
}

export default function CardImage({ src, alt, width = 200, link, isProxy }: Props) {
  const initial = src && !isLocalPath(src) ? src : PLACEHOLDER_SVG;
  const [imgSrc, setImgSrc] = useState(initial);

  // Re-sync when src prop changes (e.g. DFC flip toggling front/back face)
  useEffect(() => {
    const next = src && !isLocalPath(src) ? src : PLACEHOLDER_SVG;
    setImgSrc(next);
  }, [src]);

  const img = (
    <img
      src={imgSrc}
      alt={alt}
      width={width}
      style={{ borderRadius: 4, display: 'block', maxWidth: '100%' }}
      onError={() => setImgSrc(PLACEHOLDER_SVG)}
    />
  );

  const content = isProxy ? (
    <div style={{ position: 'relative', display: 'inline-block' }}>
      {img}
      {/* Proxy overlay badge */}
      <div
        style={{
          position: 'absolute',
          top: 8,
          left: 8,
          background: 'rgba(220, 38, 38, 0.9)',  // Red with slight transparency
          color: '#fff',
          padding: '4px 10px',
          borderRadius: 4,
          fontSize: '0.75rem',
          fontWeight: 700,
          textTransform: 'uppercase',
          letterSpacing: '0.5px',
          boxShadow: '0 2px 4px rgba(0,0,0,0.3)',
          zIndex: 10,
        }}
      >
        PROXY
      </div>
      {/* Optional: semi-transparent overlay on entire image */}
      <div
        style={{
          position: 'absolute',
          inset: 0,
          background: 'rgba(220, 38, 38, 0.05)',  // Very subtle red tint
          borderRadius: 4,
          pointerEvents: 'none',
        }}
      />
    </div>
  ) : img;

  if (link) {
    return (
      <a href={link} target="_blank" rel="noopener noreferrer" style={{ display: 'inline-block' }}>
        {content}
      </a>
    );
  }
  return content;
}
