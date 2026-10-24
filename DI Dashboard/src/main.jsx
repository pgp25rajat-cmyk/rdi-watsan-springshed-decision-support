import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { api } from "./api.js";
import { Icon, Mark, Button } from "./shared.jsx";
import { Overview, Sites, SiteDetail, Tracking, HowItWorks, VisitDrawer } from "./views.jsx";
import { SiteForm, VisitForm } from "./forms.jsx";
import { Sources } from "./evidence.jsx";
import "./style.css";

function App() {
  const [state, setState] = useState(null),
    [error, setError] = useState(""),
    [route, setRoute] = useState(location.hash || "#/overview"),
    [menu, setMenu] = useState(false),
    [opened, setOpened] = useState(null),
    [toast, setToast] = useState("");
  async function reload() {
    try {
      setState(await api("state"));
      setError("");
    } catch (e) {
      setError(e.message);
    }
  }
  useEffect(() => {
    reload();
    const timer = setInterval(reload, 30000);
    const change = () => {
      setRoute(location.hash || "#/overview");
      setMenu(false);
      setOpened(null);
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", change);
    return () => {
      clearInterval(timer);
      window.removeEventListener("hashchange", change);
    };
  }, []);
  useEffect(() => {
    if (!toast) return;
    const timer = setTimeout(() => setToast(""), 4500);
    return () => clearTimeout(timer);
  }, [toast]);
  useEffect(() => {
    if (!opened) return;
    const before = document.activeElement;
    const key = (e) => {
      if (e.key === "Escape") setOpened(null);
      if (e.key === "Tab") {
        const elements = [...document.querySelectorAll(".drawer button,.drawer a")];
        const first = elements[0],
          last = elements.at(-1);
        if (e.shiftKey && document.activeElement === first) {
          last?.focus();
          e.preventDefault();
        } else if (!e.shiftKey && document.activeElement === last) {
          first?.focus();
          e.preventDefault();
        }
      }
    };
    document.addEventListener("keydown", key);
    document.querySelector(".drawer button")?.focus();
    return () => {
      document.removeEventListener("keydown", key);
      before?.focus();
    };
  }, [opened]);
  const [path, query = ""] = route.replace(/^#/, "").split("?"),
    params = new URLSearchParams(query),
    parts = path.split("/").filter(Boolean);
  let content;
  async function siteSaved(id) {
    await reload();
    location.hash = "/sites/" + id;
    setToast("Site saved.");
  }
  async function visitSaved(id) {
    await reload();
    location.hash = "/sites/" + id;
    setToast("Visit saved.");
  }
  if (state) {
    const site = state.sites.find((s) => s.id === parts[1]);
    if (parts[0] === "sites" && parts[1] === "new") content = <SiteForm key="new-site" onSaved={siteSaved} />;
    else if (parts[0] === "sites" && site && parts[2] === "edit")
      content = <SiteForm key={site.id} site={site} onSaved={siteSaved} />;
    else if (parts[0] === "sites" && site)
      content = <SiteDetail key={site.id} site={site} state={state} onOpen={setOpened} />;
    else if (parts[0] === "sites") content = <Sites state={state} />;
    else if (parts[0] === "visits") {
      const draft = state.visits.find((v) => v.id === params.get("draft") && v.status === "draft"),
        correction = state.visits.find((v) => v.id === params.get("correct") && v.status === "submitted");
      content = (
        <VisitForm
          key={route}
          state={state}
          siteId={params.get("site")}
          draft={draft}
          correction={correction}
          onSaved={visitSaved}
          onDraftSaved={async () => {
            await reload();
            setToast("Draft saved in the database.");
          }}
        />
      );
    } else if (parts[0] === "tracking") content = <Tracking state={state} onOpen={setOpened} />;
    else if (parts[0] === "sources") content = <Sources state={state} onOpen={setOpened} />;
    else if (parts[0] === "how") content = <HowItWorks state={state} />;
    else content = <Overview state={state} onOpen={setOpened} />;
  }
  const nav = [
    ["overview", "grid", "Overview"],
    ["sites", "site", "Sites"],
    ["visits/new", "visit", "Record a visit"],
    ["tracking", "track", "Track impact"],
    ["sources", "file", "Source records"],
    ["how", "help", "How it works"],
  ];
  return (
    <div className="app-frame">
      <aside className={"sidebar " + (menu ? "is-open" : "")}>
        <a href="#/overview" className="brand">
          <Mark />
          <div>
            <strong>DI Dashboard</strong>
          </div>
        </a>
        <div className="nav-label">Workspace</div>
        <nav aria-label="Main navigation">
          {nav.map(([key, icon, label]) => (
            <a key={key} href={"#/" + key} className={parts[0] === key.split("/")[0] ? "selected" : ""}>
              <Icon name={icon} />
              {label}
            </a>
          ))}
        </nav>
      </aside>
      <div className="mobile-bar">
        <a href="#/overview">
          <Mark />
          <strong>DI Dashboard</strong>
        </a>
        <button
          aria-label={menu ? "Close navigation" : "Open navigation"}
          aria-expanded={menu}
          onClick={() => setMenu(!menu)}
        >
          <Icon name={menu ? "close" : "menu"} />
        </button>
      </div>
      <main className="sheet" id="main">
        {error && (
          <div role="alert" className="error-box">
            {error}
            <button onClick={reload}>Retry</button>
          </div>
        )}
        {state ? (
          content
        ) : (
          <div className="loading">
            <Mark />
            <h1>Opening your dashboard…</h1>
            <p>Reading the local database.</p>
          </div>
        )}
      </main>
      {toast && (
        <div role="status" className="toast">
          <Icon name="check" />
          {toast}
        </div>
      )}
      {opened && (
        <div className="modal-backdrop" onClick={() => setOpened(null)}>
          <VisitDrawer visit={opened} state={state} onClose={() => setOpened(null)} />
        </div>
      )}
    </div>
  );
}
createRoot(document.getElementById("root")).render(<App />);
