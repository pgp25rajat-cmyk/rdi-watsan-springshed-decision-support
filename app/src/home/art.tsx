// Drawings for the opening pages. Plain SVG, no images, so they stay sharp and work offline.

export function DropMark() {
  return (
    <svg className="drop-mark" viewBox="0 0 32 32" aria-hidden="true">
      <path d="M16 3C12 9 7 13.5 7 19a9 9 0 0 0 18 0c0-5.5-5-10-9-16Z" fill="currentColor" />
      <path d="M10.5 21.5c2.5-1.2 4.5-1.2 7 0s4.3 1.1 4.8.6" fill="none" stroke="#06364a" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}
