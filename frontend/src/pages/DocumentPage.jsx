import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, fmtBytes, fmtDate, fmtNumber } from "../api.js";

export default function DocumentPage() {
  const { id } = useParams();
  const [doc, setDoc] = useState(null);
  const [content, setContent] = useState("");
  const [history, setHistory] = useState([]);
  const [related, setRelated] = useState([]);
  const [similar, setSimilar] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    setDoc(null);
    setError(null);
    api
      .document(id)
      .then((d) => !cancelled && setDoc(d))
      .catch((e) => !cancelled && setError(e.message));
    api
      .content(id)
      .then((c) => !cancelled && setContent(c.content))
      .catch(() => {});
    api
      .history(id)
      .then((h) => !cancelled && setHistory(h.events))
      .catch(() => {});
    api
      .related(id)
      .then((r) => !cancelled && setRelated(r.results))
      .catch(() => {});
    api
      .similar(id)
      .then((s) => !cancelled && setSimilar(s.similar))
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (error) return <div className="error-box">{error}</div>;
  if (!doc) return <div className="empty">Loading…</div>;

  return (
    <div className="page doc-page">
      <div className="doc-main">
        <h1 className="doc-title">{doc.title}</h1>
        <div className="doc-meta muted">
          <span className="type-badge">{doc.content_type}</span>
          <span>{fmtNumber(doc.word_count)} words</span>
          <span>{fmtBytes(doc.file_size)}</span>
          <span>modified {fmtDate(doc.modified_at)}</span>
        </div>
        <div className="doc-path muted">{doc.path}</div>

        {(doc.tags.length > 0 || doc.topics.length > 0) && (
          <div className="doc-tags">
            {doc.tags.map((t) => (
              <Link className="chip" key={t} to={`/?tag=${t}`}>{t}</Link>
            ))}
            {doc.topics.map((t) => (
              <Link className="chip topic" key={t} to={`/?q=${t}`}>{t}</Link>
            ))}
          </div>
        )}

        <pre className="doc-content">{content}</pre>
      </div>

      <aside className="doc-side">
        <section className="side-card">
          <h3>History</h3>
          <ul className="history-list">
            {history.map((e) => (
              <li key={e.id}>
                <span className={`event event-${e.event_type}`}>{e.event_type}</span>
                <span className="muted">{fmtDate(e.occurred_at)}</span>
              </li>
            ))}
            {history.length === 0 && <li className="muted">No events recorded.</li>}
          </ul>
        </section>

        <section className="side-card">
          <h3>Related</h3>
          <ul className="link-list">
            {related.map((r) => (
              <li key={r.document_id}>
                <Link to={`/doc/${r.document_id}`}>{r.title}</Link>
              </li>
            ))}
            {related.length === 0 && <li className="muted">Nothing related yet.</li>}
          </ul>
        </section>

        {similar.length > 0 && (
          <section className="side-card">
            <h3>Near duplicates</h3>
            <ul className="link-list">
              {similar.map((s) => (
                <li key={s.document_id}>
                  <Link to={`/doc/${s.document_id}`}>#{s.document_id}</Link>
                  <span className="muted"> {Math.round(s.similarity * 100)}% similar</span>
                </li>
              ))}
            </ul>
          </section>
        )}

        <section className="side-card">
          <h3>Fingerprint</h3>
          <div className="mono muted small">
            sha256: {doc.sha256.slice(0, 16)}…
            <br />
            simhash: {doc.simhash}
          </div>
        </section>
      </aside>
    </div>
  );
}
