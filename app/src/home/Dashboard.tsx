import { useEffect, useState } from 'react';
import { getExistingDiSites, type ExistingDiSite } from '../api';

// Slot for Abhishek's WATSAN intervention dashboard. Until it arrives this page shows what is coming,
// plus the WATSAN DI sites the tool already holds, since the dashboard will read the same data (/api/di_sites, /api/springs).
export default function Dashboard() {
  const [sites, setSites] = useState<ExistingDiSite[] | null>(null);
  useEffect(() => { getExistingDiSites().then(setSites).catch(() => setSites([])); }, []);
  const springs = new Set((sites ?? []).map((s) => s.linked_spring).filter(Boolean));

  return (
    <div className="dash">
      <header className="dash-top">
        <div className="dash-banner" aria-hidden="true" />
        <a className="dash-back" href="#/">← Home</a>
        <span className="dash-title">WATSAN intervention dashboard</span>
        <a className="btn btn-light btn-small" href="#/planner">Open planner</a>
      </header>

      <main className="dash-main">
        <div className="dash-hero">
          <h1>Springs and their recharge handpumps</h1>
          <p>Each WATSAN spring, its DI handpumps, and how flow changed after recharge.</p>
        </div>

        <div className="ghost-grid" aria-hidden="true">
          <div className="ghost ghost-kpis">{[0, 1, 2, 3].map((i) => <span key={i} className="ghost-kpi"><i /><b /></span>)}</div>
          <div className="ghost ghost-chart">{[30, 42, 26, 38, 64, 78, 70, 86].map((h, i) => <span key={i} style={{ height: `${h}%` }} className={i > 3 ? 'after' : ''} />)}</div>
          <div className="ghost ghost-map"><span className="pin p1" /><span className="pin p2" /><span className="pin p3" /></div>
          <div className="ghost ghost-list">{[0, 1, 2, 3, 4].map((i) => <span key={i} />)}</div>
        </div>

        {sites && sites.length > 0 && (
          <section className="dash-data">
            <h2>Already in the shared data</h2>
            <p className="muted">{sites.length} WATSAN DI handpumps{springs.size ? `, linked to ${springs.size} springs` : ''}. The dashboard and the planner read the same list.</p>
            <ul>
              {sites.map((s) => (
                <li key={s.id}><b>{s.name}</b><span>{s.linked_spring || 'No spring linked yet'}</span></li>
              ))}
            </ul>
          </section>
        )}
      </main>
    </div>
  );
}
