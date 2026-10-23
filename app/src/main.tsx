import { StrictMode, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import Home from './home/Home';
import Dashboard from './home/Dashboard';
import './styles.css';
import './home/home.css';

// Three pages on hash addresses, so the Python server needs no change: #/ (opening page), #/planner, #/dashboard
function route() {
  const h = window.location.hash.replace(/^#\/?/, '').split(/[?/]/)[0];
  return h === 'planner' || h === 'dashboard' ? h : 'home';
}

function Root() {
  const [page, setPage] = useState(route);
  useEffect(() => {
    const on = () => { setPage(route()); window.scrollTo(0, 0); };
    window.addEventListener('hashchange', on);
    return () => window.removeEventListener('hashchange', on);
  }, []);
  useEffect(() => {
    document.title = page === 'planner' ? 'Spring Health & Recharge Planner'
      : page === 'dashboard' ? 'WATSAN Intervention Dashboard' : 'Springs of the Himalaya · RDI WATSAN';
  }, [page]);
  if (page === 'planner') return <App />;
  if (page === 'dashboard') return <Dashboard />;
  return <Home />;
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <Root />
  </StrictMode>,
);
