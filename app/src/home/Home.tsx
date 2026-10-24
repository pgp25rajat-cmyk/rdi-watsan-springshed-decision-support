import { useRef, type ReactNode } from 'react';
import { DropMark } from './art';

// Opening page: two doors (dashboard, planner), then a short word on the tool, WATSAN and the team.
export default function Home() {
  const about = useRef<HTMLElement>(null);
  const team = useRef<HTMLElement>(null);
  const go = (el: HTMLElement | null) => el?.scrollIntoView({ behavior: 'smooth', block: 'start' });

  return (
    <div className="home">
      <header className="lp-hero">
        <div className="lp-hero-photo" aria-hidden="true" />
        <nav className="lp-hero-nav">
          <span className="lp-hero-mark"><DropMark />RDI · WATSAN</span>
          <span className="lp-hero-links">
            <button type="button" onClick={() => go(about.current)}>About</button>
            <button type="button" onClick={() => go(team.current)}>Team</button>
          </span>
        </nav>
        <div className="lp-hero-text">
          <p className="eyebrow">Springs of Uttarakhand</p>
          <h1>Keep the springs flowing</h1>
          <p className="lp-hero-sub">See what recharge has done. Plan where to do it next.</p>
          <span className="lp-hero-rule" aria-hidden="true" />
        </div>
      </header>

      <section className="doors" aria-label="Open a section">
        <a className="door door-dash" href="#/dashboard">
          <span className="door-kicker"><ChartIcon />WATSAN interventions</span>
          <h2>Dashboard</h2>
          <p>Track the springs and their recharge handpumps. What changed, and by how much.</p>
          <span className="door-go">Open dashboard <Arrow /></span>
          <Contours />
        </a>
        <a className="door door-plan" href="#/planner">
          <span className="door-kicker"><LeafIcon />Planning tool</span>
          <h2>Spring health &amp; recharge planner</h2>
          <p>Pick any spring. Get its risk, its recharge zone and the gain from DI, on a 3D map.</p>
          <span className="door-go">Open planner <Arrow /></span>
          <Contours pin />
        </a>
      </section>

      <section className="about" ref={about} aria-labelledby="about-h">
        <h2 id="about-h" className="sec-h">About</h2>
        <div className="about-body">
        <div className="about-text">
        <article className="about-item">
          <h3>The tool</h3>
          <p>One place for WATSAN's spring work: track the springs already recharged, and plan new ones from a spring's location and a few field answers.</p>
        </article>
        <article className="about-item">
          <h3>WATSAN, RDI</h3>
          <p>The water and sanitation team of the Rural Development Institute works with hill villages in Uttarakhand to revive springs.</p>
          <p>One way they do it: rooftop rainwater is sent down old, unused handpumps into the ground, where it feeds the springs below. This is called Direct Injection (DI).</p>
          <DiStrip />
        </article>
        </div>
        <img className="about-photo" src="/brand/about-spring.jpg" alt="A spring stream below snow peaks in the Himalaya" width="1024" height="572" loading="lazy" />
        </div>
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
        <svg className="foot-ridges" viewBox="0 0 1440 120" preserveAspectRatio="none" aria-hidden="true">
          <path d="M0 120V84l120-30 90 22 140-52 110 40 130-46 120 48 150-38 110 30 160-50 120 44 90-20 100 26v66Z" />
        </svg>
        <div className="home-foot-in">
          <img src="/brand/srhu-logo-white.png" alt="Swami Rama Himalayan University" width="190" height="122" />
          <p>Rural Development Institute · WATSAN<br />with SPJIMR · 2026</p>
        </div>
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

function ChartIcon() {
  return <svg className="kicker-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M3 21h18M5 21v-5M9 21v-8M13 21v-6M17 21v-10M4 11l5-4 4 3 7-6M16 4h4v4" /></svg>;
}

function LeafIcon() {
  return <svg className="kicker-icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 22v-8M12 3c-4 4-6 7-6 10a6 6 0 0 0 12 0c0-3-2-6-6-10ZM12 14l-3-3M12 17l3-3" /></svg>;
}

/** Faint contour lines in a card's corner, like a topo sheet. */
function Contours({ pin }: { pin?: boolean }) {
  return (
    <svg className="door-contours" viewBox="0 0 220 120" aria-hidden="true">
      {[0, 1, 2, 3, 4, 5].map((i) => (
        <ellipse key={i} cx="160" cy="92" rx={18 + i * 17} ry={10 + i * 10} transform="rotate(-14 160 92)" />
      ))}
      {pin && <path className="door-pin" d="M160 58c-6 0-10 4.4-10 9.8 0 7.2 10 17.2 10 17.2s10-10 10-17.2c0-5.4-4-9.8-10-9.8Zm0 13.4a3.6 3.6 0 1 1 0-7.2 3.6 3.6 0 0 1 0 7.2Z" />}
    </svg>
  );
}
