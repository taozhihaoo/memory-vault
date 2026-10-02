import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, fmtBytes, fmtNumber } from "../api.js";

export default function DashboardPage() {
  const [stats, setStats] = useState(null);
  const [tags, setTags] = useState([]);
  const [dups, setDups] = useState(null);
  const [docs, setDocs] = useState([]);
  const [scanning, setScanning] = useState(false);

  useEffect(() => {
    api.stats().then(setStats).catch(() => {});
    api.tags().then(setTags).catch(() => {});
    api.duplicates().then(setDups).catch(() => {});
    api.documents({ limit: 10 }).then((d) => setDocs(d.documents)).catch(() => {});
  }, []);

  async function rescan() {
    setScanning(true);
    try {
      await api.scan(null);
      setStats(await api.stats());
    } catch {
      /* watch paths may not be configured */
    } finally {
      setScanning(false);
    }
  }

  if (!stats) return <div className="empty">Loading vault…</div>;

  return (
    <div className="page dashboard">
      <h2>Vault overview</h2>
      <div className="stat-grid">
        <div className="stat-card">
          <div className="stat-number">{fmtNumber(stats.documents)}</div>
          <div className="muted">documents</div>
        </div>
        <div className="stat-card">
          <div className="stat-number">{fmtNumber(stats.words)}</div>
          <div className="muted">words</div>
        </div>
        <div className="stat-card">
          <div className="stat-number">{fmtBytes(stats.bytes)}</div>
          <div className="muted">raw text</div>
        </div>
        <div className="stat-card">
          <div className="stat-number">{fmtNumber(stats.tags)}</div>
          <div className="muted">tags & topics</div>
        </div>
        <div className="stat-card">
          <div className="stat-number">{fmtNumber(stats.events)}</div>
          <div className="muted">timeline events</div>
        </div>
      </div>

      <div className="dash-columns">
        <section className="chart-card">
          <h3>Content types</h3>
          {Object.entries(stats.content_types).map(([type, n]) => (
            <div className="type-row" key={type}>
              <span className="type-name">{type}</span>
              <div className="type-bar">
                <div
                  className="type-fill"
                  style={{ width: `${(n / stats.documents) * 100}%` }}
                />
              </div>
              <span className="muted">{n}</span>
            </div>
          ))}
          {Object.keys(stats.content_types).length === 0 && (
            <div className="muted">
              Vault is empty — run <code>memoryvault index &lt;dir&gt;</code> first.
            </div>
          )}
        </section>

        <section className="chart-card">
          <h3>Top tags</h3>
          <div className="tag-cloud">
            {tags.slice(0, 15).map((t) => (
              <Link key={t.name} to={`/?tag=${t.name}`} className="chip">
                {t.name} <span className="chip-count">{t.document_count}</span>
              </Link>
            ))}
            {tags.length === 0 && <span className="muted">No tags yet.</span>}
          </div>
        </section>

        <section className="chart-card">
          <h3>Duplicates</h3>
          {dups && (
            <>
              <div className="dup-line">
                {dups.exact.length} exact · {dups.similar.length} near-duplicate group(s)
              </div>
              {dups.exact.slice(0, 5).map((g, i) => (
                <div className="dup-line muted" key={`e${i}`}>
                  exact: {g.document_ids.map((id) => (
                    <Link to={`/doc/${id}`} key={id}>#{id} </Link>
                  ))}
                </div>
              ))}
              {dups.similar.slice(0, 5).map((g, i) => (
                <div className="dup-line muted" key={`s${i}`}>
                  ~{Math.round((g.similarity ?? 0) * 100)}%: {g.document_ids.map((id) => (
                    <Link to={`/doc/${id}`} key={id}>#{id} </Link>
                  ))}
                </div>
              ))}
              {dups.exact.length === 0 && dups.similar.length === 0 && (
                <div className="muted">No duplicates detected.</div>
              )}
            </>
          )}
        </section>
      </div>

      <section className="chart-card">
        <div className="recent-head">
          <h3>Recently modified</h3>
          <button className="btn" onClick={rescan} disabled={scanning}>
            {scanning ? "Scanning…" : "Re-scan vault"}
          </button>
        </div>
        <ul className="doc-rows">
          {docs.map((d) => (
            <li key={d.id}>
              <Link to={`/doc/${d.id}`} className="doc-row-title">{d.title}</Link>
              <span className="muted doc-row-path">{d.path}</span>
              <span className="type-badge">{d.content_type}</span>
            </li>
          ))}
          {docs.length === 0 && <li className="muted">No documents indexed yet.</li>}
        </ul>
      </section>
    </div>
  );
}
