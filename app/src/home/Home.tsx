import { useRef, type ReactNode } from 'react';
import { Ridges, DropMark } from './art';

// Opening page: two doors (dashboard, planner), then a short word on the tool, WATSAN and the team.
export default function Home() {
  const about = useRef<HTMLElement>(null);
  const team = useRef<HTMLElement>(null);
  const go = (el: HTMLElement | null) => el?.scrollIntoView({ behavior: 'smooth', block: 'start' });

  return (
    <div className="home">
      <header className="lp-hero">
        <Ridges />
        <nav className="lp-hero-nav">
          <span className="lp-hero-mark">
            <img className="srhu-tile" src="/brand/srhu-logo.png" alt="Swami Rama Himalayan University" width="80" height="52" />
            <span><DropMark />RDI · WATSAN</span>
          </span>
          <span className="lp-hero-links">
            <button type="button" onClick={() => go(about.current)}>About</button>
            <button type="button" onClick={() => go(team.current)}>Team</button>
          </span>
        </nav>
        <div className="lp-hero-text">
          <p className="eyebrow">Springs of the Garhwal Himalaya</p>
          <h1>Keep the springs flowing</h1>
          <p className="lp-hero-sub">See what recharge has done. Plan where to do it next.</p>
        </div>
      </header>

      <section className="doors" aria-label="Open a section">
        <a className="door door-dash" href="#/dashboard">
          <span className="door-badge">Coming soon</span>
          <DashArt />
          <span className="door-kicker">WATSAN interventions</span>
          <h2>Dashboard</h2>
          <p>Springs and their recharge handpumps. What changed, and by how much.</p>
          <span className="door-chips"><i>Springs</i><i>DI handpumps</i><i>Impact</i></span>
          <span className="door-go">Preview <Arrow /></span>
        </a>
        <a className="door door-plan" href="#/planner">
          <PlanArt />
          <span className="door-kicker">Planning tool</span>
          <h2>Spring health &amp; recharge planner</h2>
          <p>Pick any spring. Get its risk, its recharge zone and the gain from DI, on a 3D map.</p>
          <span className="door-chips"><i><b>A</b>Vulnerability</i><i><b>B</b>Springshed</i><i><b>C</b>DI impact</i></span>
          <span className="door-go">Open planner <Arrow /></span>
        </a>
      </section>

      <section className="about" ref={about} aria-labelledby="about-h">
        <h2 id="about-h" className="sec-h">About</h2>
        <div className="about-grid">
          <article>
            <h3>The tool</h3>
            <p>One place for WATSAN's spring work: track the springs already recharged, and plan new ones from a spring's location and a few field answers.</p>
          </article>
          <article>
            <h3>WATSAN, RDI</h3>
            <p>The water and sanitation team of the Rural Development Institute works with hill villages in Uttarakhand to revive springs.</p>
          </article>
        </div>
        <DiStrip />
      </section>

      <section className="team" ref={team} aria-labelledby="team-h">
        <h2 id="team-h" className="sec-h">Team</h2>
        <div className="team-grid">
          <Person initials="R" name="Rajat" org="SPJIMR" />
          <Person initials="A" name="Abhishek" org="SPJIMR" />
          <Person initials="W" name="WATSAN team" org="RDI" note="Names to be added" />
        </div>
      </section>

      <footer className="home-foot">
        <img src="/brand/srhu-logo.png" alt="Swami Rama Himalayan University" width="200" height="130" />
        <p>Rural Development Institute · WATSAN<br />with SPJIMR · 2026</p>
      </footer>
    </div>
  );
}

function Person({ initials, name, org, note }: { initials: string; name: string; org: string; note?: string }) {
  return (
    <div className={`person${note ? ' person-tbc' : ''}`}>
      <span className="avatar" aria-hidden="true">{initials}</span>
      <span><b>{name}</b><small>{org}{note ? ` · ${note}` : ''}</small></span>
    </div>
  );
}

/** How Direct Injection works, in four pictures. */
function DiStrip() {
  const steps: [string, ReactNode][] = [
    ['Rain on a roof', <path key="r" d="M6 26 24 12l18 14M10 23v15h28V23M4 8l-2 4M14 4l-2 4M34 4l-2 4M44 8l-2 4" />],
    ['Into an old handpump', <path key="h" d="M20 40V14h8v26M16 14h16M28 18h10l3 4M24 10V6M14 40h20" />],
    ['Down to the rock layer', <path key="g" d="M4 14h40M4 24c8-3 14 3 22 0s12-3 18 0M4 34c10-3 16 3 24 0s12-2 16 0M24 4v28" />],
    ['Back out at the spring', <path key="s" d="M24 6c-6 9-11 14-11 21a11 11 0 0 0 22 0c0-7-5-12-11-21ZM18 29c3-1.5 5-1.5 8 0s4 1 5 .5" />],
  ];
  return (
    <div className="di-strip" aria-label="How DI recharge works">
      <p className="di-title">Direct Injection (DI)</p>
      <ol>
        {steps.map(([label, path]) => (
          <li key={label}>
            <svg viewBox="0 0 48 44" aria-hidden="true">{path}</svg>
            <span>{label}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

function Arrow() {
  return <svg className="arrow" viewBox="0 0 20 20" aria-hidden="true"><path d="M4 10h11M11 5l5 5-5 5" /></svg>;
}

/** Small picture on the dashboard door: flow bars rising after recharge. */
function DashArt() {
  const bars = [14, 18, 12, 16, 30, 38, 34, 42];
  return (
    <svg className="door-art" viewBox="0 0 160 64" aria-hidden="true">
      <line x1="76" y1="4" x2="76" y2="60" className="art-split" />
      {bars.map((h, i) => (
        <rect key={i} x={6 + i * 19 + (i > 3 ? 4 : 0)} y={60 - h} width="12" height={h} rx="3" className={i > 3 ? 'art-after' : 'art-before'} />
      ))}
      <text x="40" y="10" className="art-label">before</text>
      <text x="118" y="10" className="art-label">after DI</text>
    </svg>
  );
}

/** Small picture on the planner door: contours, a spring and three recharge zones. */
function PlanArt() {
  return (
    <svg className="door-art" viewBox="0 0 160 64" aria-hidden="true">
      {[0, 1, 2, 3, 4, 5, 6].map((i) => (
        <path key={i} className="art-contour" d={`M-4 ${70 - i * 9}C40 ${58 - i * 9} 60 ${66 - i * 10} 92 ${50 - i * 9}S140 ${30 - i * 7} 164 ${36 - i * 8}`} />
      ))}
      <path className="art-zone z1" d="M96 14c8-4 18-2 20 5s-6 12-14 11-12-12-6-16Z" />
      <path className="art-zone z2" d="M126 30c6-3 13 0 13 6s-8 8-13 6-5-10 0-12Z" />
      <path className="art-zone z3" d="M64 30c5-3 11-1 11 4s-6 7-10 5-5-7-1-9Z" />
      <path className="art-drop" d="M40 38c-3 4.5-5.5 7-5.5 10a5.5 5.5 0 0 0 11 0c0-3-2.5-5.5-5.5-10Z" />
    </svg>
  );
}
