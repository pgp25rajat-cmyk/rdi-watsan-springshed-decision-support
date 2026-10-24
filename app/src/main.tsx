import { StrictMode, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import Home from './home/Home';
import '@fontsource/source-sans-3/latin-400.css';
import '@fontsource/source-sans-3/latin-500.css';
import '@fontsource/source-sans-3/latin-600.css';
import '@fontsource/source-sans-3/latin-700.css';
import './theme.css';
import './styles.css';
import './home/home.css';

// Pages: #/ (opening page) and #/planner here; the DI dashboard is its own page at /dashboard/ (DI Dashboard/, same server)
function route() {
  const h = window.location.hash.replace(/^#\/?/, '').split(/[?/]/)[0];
  if (h === 'dashboard') window.location.replace('/dashboard/'); // old address of the dashboard slot
  return h === 'planner' ? h : 'home';
}

function Root() {
  const [page, setPage] = useState(route);
  useEffect(() => {
    const on = () => { setPage(route()); window.scrollTo(0, 0); };
    window.addEventListener('hashchange', on);
    return () => window.removeEventListener('hashchange', on);
  }, []);
  useEffect(() => {
    document.title = page === 'planner' ? 'Spring Health & Recharge Planner' : 'Springs of the Himalaya · RDI WATSAN';
  }, [page]);
  if (page === 'planner') return <App />;
  return <Home />;
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Root />
  </StrictMode>,
);
