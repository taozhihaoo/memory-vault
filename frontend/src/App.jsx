import React from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import SearchPage from "./pages/SearchPage.jsx";
import DocumentPage from "./pages/DocumentPage.jsx";
import GraphPage from "./pages/GraphPage.jsx";
import TimelinePage from "./pages/TimelinePage.jsx";
import DashboardPage from "./pages/DashboardPage.jsx";

export default function App() {
  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="brand-mark">◉</span>
          <span className="brand-name">MemoryVault</span>
          <span className="brand-tag">local-first</span>
        </div>
        <nav className="nav">
          <NavLink to="/" end>Search</NavLink>
          <NavLink to="/dashboard">Dashboard</NavLink>
          <NavLink to="/graph">Graph</NavLink>
          <NavLink to="/timeline">Timeline</NavLink>
        </nav>
        <div className="topbar-right">
          <span className="offline-badge">100% offline</span>
        </div>
      </header>
      <main className="content">
        <Routes>
          <Route path="/" element={<SearchPage />} />
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/graph" element={<GraphPage />} />
          <Route path="/timeline" element={<TimelinePage />} />
          <Route path="/doc/:id" element={<DocumentPage />} />
        </Routes>
      </main>
      <footer className="footer">
        MemoryVault — your documents never leave this machine.
      </footer>
    </div>
  );
}
