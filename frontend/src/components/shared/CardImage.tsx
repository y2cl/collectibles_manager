import { useState, useEffect } from 'react';

interface Props {
  src: string;
  alt: string;
  width?: number;
  link?: string;
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

export default function CardImage({ src, alt, width = 200, link }: Props) {
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

  if (link) {
    return (
      <a href={link} target="_blank" rel="noopener noreferrer">
        {img}
      </a>
    );
  }
  return img;
}
