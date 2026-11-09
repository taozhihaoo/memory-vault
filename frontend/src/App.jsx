import React, { useEffect, useState } from "react";
import { Link, NavLink, Route, Routes, useLocation } from "react-router-dom";
import { api } from "./api.js";
import { LocaleProvider, useI18n } from "./locale.jsx";
import { BrandMark, EmptyState, Icon, Segmented } from "./components.jsx";
import SearchPage from "./pages/SearchPage.jsx";
import DocumentPage from "./pages/DocumentPage.jsx";
import GraphPage from "./pages/GraphPage.jsx";
import TimelinePage from "./pages/TimelinePage.jsx";
import DashboardPage from "./pages/DashboardPage.jsx";

const APP_VERSION = "1.1.0";

const NAV = [
  { to: "/", end: true, key: "nav.search", icon: "search", group: "nav.section" },
  { to: "/dashboard", key: "nav.dashboard", icon: "dashboard", group: "nav.section" },
  { to: "/graph", key: "nav.graph", icon: "graph", group: "nav.sectionExplore" },
  { to: "/timeline", key: "nav.timeline", icon: "timeline", group: "nav.sectionExplore" },
];

function Sidebar() {
  const { t } = useI18n();
  let lastGroup = null;
  return (
    <aside className="sidebar">
      <Link to="/" className="brand">
        <BrandMark size={38} />
        <span className="brand-copy">
          <strong>MemoryVault</strong>
          <small>{t("brand.tagline")}</small>
        </span>
      </Link>

      <nav className="side-nav" aria-label="Main navigation">
        {NAV.map((item) => {
          const heading = item.group !== lastGroup ? t(item.group) : null;
          lastGroup = item.group;
          return (
            <React.Fragment key={item.to}>
              {heading && <div className="nav-group">{heading}</div>}
              <NavLink
                to={item.to}
                end={item.end}
                className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}
              >
                <Icon name={item.icon} size={18} />
                <span>{t(item.key)}</span>
                <span className="nav-item-glow" />
              </NavLink>
            </React.Fragment>
          );
        })}
      </nav>

      <div className="sidebar-bottom">
        <div className="offline-card">
          <span className="offline-card-icon"><Icon name="shield" size={18} /></span>
          <div>
            <strong>{t("status.title")}</strong>
            <p>{t("status.body")}</p>
          </div>
        </div>
        <div className="sidebar-meta">
          <span>{t("status.version")} {APP_VERSION}</span>
          <span className="local-chip">{t("brand.local")}</span>
        </div>
      </div>
    </aside>
  );
}

function Topbar() {
  const { lang, setLang, t } = useI18n();
  const location = useLocation();
  const [healthy, setHealthy] = useState(null);

  useEffect(() => {
    let cancelled = false;
    api.health()
      .then(() => !cancelled && setHealthy(true))
      .catch(() => !cancelled && setHealthy(false));
    return () => { cancelled = true; };
  }, []);

  const current = NAV.find((item) =>
    item.end ? location.pathname === item.to : location.pathname.startsWith(item.to)
  );
  const pageName = location.pathname.startsWith("/doc/")
    ? t("nav.documents")
    : current ? t(current.key) : t("nav.search");

  return (
    <header className="topbar">
      <div className="topbar-crumb">
        <span className="crumb-root">MemoryVault</span>
        <Icon name="chevron" size={14} className="crumb-chevron" />
        <span className="crumb-current">{pageName}</span>
      </div>
      <div className="topbar-right">
        <span className={`health-pill ${healthy === false ? "warn" : ""}`}>
          <span className="health-dot" />
          {healthy === false ? t("status.apiUnavailable") : t("status.healthy")}
        </span>
        <span className="offline-pill"><Icon name="shield" size={13} />{t("status.badge")}</span>
        <Segmented
          ariaLabel={t("lang.label")}
          value={lang}
          onChange={setLang}
          options={[
            { value: "en", label: t("lang.en") },
            { value: "zh", label: t("lang.zh") },
          ]}
        />
      </div>
    </header>
  );
}

function NotFound() {
  const { t } = useI18n();
  return (
    <div className="page">
      <EmptyState
        icon="folder"
        title={t("notFound.title")}
        body={t("notFound.body")}
        action={<Link to="/" className="btn primary"><Icon name="arrowLeft" size={15} />{t("notFound.action")}</Link>}
      />
    </div>
  );
}

function Shell() {
  const { t } = useI18n();
  const location = useLocation();
  return (
    <div className="app-shell">
      <div className="ambient" aria-hidden="true" />
      <Sidebar />
      <div className="main-column">
        <Topbar />
        <main className="main-content">
          <div className="page-transition" key={location.pathname}>
            <Routes>
              <Route path="/" element={<SearchPage />} />
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/graph" element={<GraphPage />} />
              <Route path="/timeline" element={<TimelinePage />} />
              <Route path="/doc/:id" element={<DocumentPage />} />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </div>
        </main>
        <footer className="footer">
          <span className="footer-dot" />{t("footer.text")}
        </footer>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <LocaleProvider>
      <Shell />
    </LocaleProvider>
  );
}
