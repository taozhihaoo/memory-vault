import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, fmtBytes, fmtDate, fmtNumber } from "../api.js";
import { useI18n } from "../locale.jsx";
import {
  BackLink, Card, CardHeading, EmptyState, Icon, LoadingState, TypeBadge,
} from "../components.jsx";

export default function DocumentPage() {
  const { id } = useParams();
  const { lang, t } = useI18n();
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
    setContent("");
    setHistory([]);
    setRelated([]);
    setSimilar([]);
    api.document(id)
      .then((d) => !cancelled && setDoc(d))
      .catch((e) => !cancelled && setError(e.message));
    api.content(id).then((c) => !cancelled && setContent(c.content ?? "")).catch(() => {});
    api.history(id).then((h) => !cancelled && setHistory(h.events ?? [])).catch(() => {});
    api.related(id).then((r) => !cancelled && setRelated(r.results ?? [])).catch(() => {});
    api.similar(id).then((s) => !cancelled && setSimilar(s.similar ?? [])).catch(() => {});
    return () => { cancelled = true; };
  }, [id]);

  if (error) {
    return (
      <div className="page">
        <BackLink label={t("common.back")} />
        <EmptyState icon="alert" title={t("doc.notFound")} body={error} />
      </div>
    );
  }
  if (!doc) {
    return (
      <div className="page">
        <LoadingState label={t("doc.loading")} cards={2} />
      </div>
    );
  }

  const tags = doc.tags ?? [];
  const topics = doc.topics ?? [];

  return (
    <div className="page doc-page">
      <div className="doc-main">
        <BackLink label={t("common.back")} />
        <div className="doc-heading">
          <div className="doc-heading-icon"><Icon name="document" size={24} /></div>
          <div>
            <h1>{doc.title}</h1>
            <div className="doc-meta">
              <TypeBadge type={doc.content_type} />
              <span><Icon name="hash" size={13} />{fmtNumber(doc.word_count, lang)} {t("common.words")}</span>
              <span><Icon name="database" size={13} />{fmtBytes(doc.file_size)}</span>
              <span><Icon name="clock" size={13} />{t("doc.modified")} {fmtDate(doc.modified_at, lang)}</span>
            </div>
          </div>
        </div>
        <div className="doc-path"><Icon name="folder" size={14} />{doc.path}</div>

        {(tags.length > 0 || topics.length > 0) && (
          <div className="doc-tags">
            {tags.map((tag) => (
              <Link className="tag-chip" key={`t-${tag}`} to={`/?tag=${encodeURIComponent(tag)}`}>
                <Icon name="tag" size={12} />{tag}
              </Link>
            ))}
            {topics.map((topic) => (
              <Link className="tag-chip topic" key={`k-${topic}`} to={`/?q=${encodeURIComponent(topic)}`}>
                <Icon name="sparkles" size={12} />{topic}
              </Link>
            ))}
          </div>
        )}

        <Card className="doc-content-card">
          <div className="doc-content-head">
            <span><Icon name="document" size={14} />{doc.content_type || "text"}</span>
            <span>{fmtNumber(content.length, lang)} chars</span>
          </div>
          <pre className="doc-content">{content}</pre>
        </Card>
      </div>

      <aside className="doc-side">
        <Card>
          <CardHeading icon="clock" title={t("doc.history")} />
          <ul className="history-list">
            {history.map((event) => (
              <li key={event.id}>
                <span className={`event-dot event-${event.event_type}`} />
                <span className={`event event-${event.event_type}`}>{t(`event.${event.event_type}`) || event.event_type}</span>
                <span className="history-time">{fmtDate(event.occurred_at, lang)}</span>
              </li>
            ))}
            {history.length === 0 && <li className="inline-empty">{t("doc.noEvents")}</li>}
          </ul>
        </Card>

        <Card>
          <CardHeading icon="link" title={t("doc.related")} />
          <ul className="link-list">
            {related.map((r) => (
              <li key={r.document_id}>
                <Icon name="arrowRight" size={13} />
                <Link to={`/doc/${r.document_id}`}>{r.title}</Link>
              </li>
            ))}
            {related.length === 0 && <li className="inline-empty">{t("doc.nothingRelated")}</li>}
          </ul>
        </Card>

        {similar.length > 0 && (
          <Card>
            <CardHeading icon="copy" title={t("doc.nearDuplicates")} />
            <ul className="link-list">
              {similar.map((s) => (
                <li key={s.document_id}>
                  <Icon name="arrowRight" size={13} />
                  <Link to={`/doc/${s.document_id}`}>#{s.document_id}</Link>
                  <span className="dup-pct">{Math.round((s.similarity ?? 0) * 100)}% {t("doc.similar")}</span>
                </li>
              ))}
            </ul>
          </Card>
        )}

        <Card className="fingerprint-card">
          <CardHeading icon="shield" title={t("doc.fingerprint")} />
          <div className="fingerprint">
            <div><span>{t("doc.sha")}</span><code>{(doc.sha256 ?? "").slice(0, 20)}…</code></div>
            <div><span>{t("doc.simhash")}</span><code>{doc.simhash ?? "—"}</code></div>
          </div>
        </Card>
      </aside>
    </div>
  );
}
