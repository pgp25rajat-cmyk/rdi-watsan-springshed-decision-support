// Drawings for the opening pages. Plain SVG, no images, so they stay sharp and work offline.

/** Hero background: layered Himalayan ridges at first light, a snow line, and a spring running down the near slope. */
export function Ridges() {
  return (
    <svg className="ridges" viewBox="0 0 1440 520" preserveAspectRatio="xMidYMax slice" aria-hidden="true">
      <defs>
        <linearGradient id="sky" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#06364a" />
          <stop offset="0.55" stopColor="#0b6e8a" />
          <stop offset="1" stopColor="#7fb7a8" />
        </linearGradient>
        <radialGradient id="sun" cx="0.74" cy="0.38" r="0.32">
          <stop offset="0" stopColor="#ffe3a8" stopOpacity="0.85" />
          <stop offset="1" stopColor="#ffe3a8" stopOpacity="0" />
        </radialGradient>
        <linearGradient id="r1" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#8fb9c4" /><stop offset="1" stopColor="#5f97a6" /></linearGradient>
        <linearGradient id="r2" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#3f8193" /><stop offset="1" stopColor="#2a6a7b" /></linearGradient>
        <linearGradient id="r3" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#25705f" /><stop offset="1" stopColor="#1b5a4b" /></linearGradient>
        <linearGradient id="r4" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#1a4f43" /><stop offset="1" stopColor="#123b33" /></linearGradient>
        <linearGradient id="stream" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stopColor="#bfeaf5" stopOpacity="0" /><stop offset="0.3" stopColor="#bfeaf5" /><stop offset="1" stopColor="#e8fbff" /></linearGradient>
      </defs>
      <rect width="1440" height="520" fill="url(#sky)" />
      <rect width="1440" height="520" fill="url(#sun)" />
      <circle cx="1065" cy="196" r="34" fill="#ffefc9" opacity="0.9" />
      {/* far snow range */}
      <path fill="url(#r1)" d="M0 300 L120 236 L190 262 L300 168 L360 210 L430 150 L520 232 L610 196 L700 252 L820 140 L900 200 L980 176 L1080 246 L1180 186 L1270 228 L1360 172 L1440 214 V520 H0Z" />
      <path fill="#f2f8f9" opacity="0.92" d="M300 168 L332 192 L318 194 L346 204 L360 210 L330 206 L312 186 L290 196Z M430 150 L470 186 L452 186 L478 204 L444 196 L428 176 L404 186Z M820 140 L858 172 L840 172 L870 192 L834 184 L818 160 L794 176Z M1360 172 L1394 196 L1376 196 L1400 206 L1366 202 L1352 186 L1338 192Z" />
      {/* middle ridges */}
      <path fill="url(#r2)" d="M0 340 C90 300 160 280 250 300 S420 250 520 280 S690 330 790 286 S980 236 1090 290 S1300 320 1440 268 V520 H0Z" />
      <path fill="url(#r3)" d="M0 392 C120 350 220 344 330 366 S540 330 650 360 S860 400 980 356 S1230 330 1440 372 V520 H0Z" />
      {/* terraces on the near-middle slope */}
      <g fill="none" stroke="#3b8a6c" strokeWidth="2" opacity="0.55">
        <path d="M720 392 C800 380 880 386 960 372" /><path d="M700 406 C790 394 880 400 980 386" /><path d="M690 420 C780 410 880 414 1000 400" />
      </g>
      {/* near slope with the spring */}
      <path fill="url(#r4)" d="M0 448 C140 410 260 396 380 418 S600 452 720 430 S980 400 1110 428 S1330 456 1440 436 V520 H0Z" />
      <path fill="none" stroke="url(#stream)" strokeWidth="4" strokeLinecap="round" d="M150 426 C158 450 138 466 150 486 S166 506 158 520" />
      <circle cx="150" cy="426" r="6" fill="#e8fbff" />
      <circle cx="150" cy="426" r="14" fill="none" stroke="#e8fbff" strokeWidth="1.5" opacity="0.5" className="ripple" />
      {/* a few pines */}
      <g fill="#0f3029">
        {[40, 64, 86, 1300, 1326, 1350, 1380].map((x, i) => (
          <path key={x} d={`M${x} ${450 - (i % 3) * 6} l10 30 h-20Z`} />
        ))}
      </g>
    </svg>
  );
}

export function DropMark() {
  return (
    <svg className="drop-mark" viewBox="0 0 32 32" aria-hidden="true">
      <path d="M16 3C12 9 7 13.5 7 19a9 9 0 0 0 18 0c0-5.5-5-10-9-16Z" fill="currentColor" />
      <path d="M10.5 21.5c2.5-1.2 4.5-1.2 7 0s4.3 1.1 4.8.6" fill="none" stroke="#06364a" strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}
