import React, { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, fmtBytes, fmtDate, fmtNumber } from "../api.js";
import { useI18n } from "../locale.jsx";
import {
  Card, CardHeading, ErrorBox, Icon, LoadingState, PageHeader, StatCard, TypeBadge,
} from "../components.jsx";

export default function DashboardPage() {
  const { lang, t } = useI18n();
  const [stats, setStats] = useState(null);
  const [tags, setTags] = useState([]);
  const [dups, setDups] = useState(null);
  const [docs, setDocs] = useState([]);
  const [scanning, setScanning] = useState(false);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    api.stats().then(setStats).catch((e) => setError(e.message));
    api.tags().then(setTags).catch(() => setTags([]));
    api.duplicates().then(setDups).catch(() => setDups(null));
    api.documents({ limit: 10 })
      .then((d) => setDocs(d.documents ?? []))
      .catch(() => setDocs([]));
  }, []);

  useEffect(() => { load(); }, [load]);

  async function rescan() {
    setScanning(true);
    try {
      await api.scan(null);
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setScanning(false);
    }
  }

  if (!stats) {
    return (
      <div className="page">
        <PageHeader eyebrow={t("dashboard.eyebrow")} title={t("dashboard.title")} subtitle={t("dashboard.subtitle")} />
        {error ? <ErrorBox message={error} onRetry={load} retryLabel={t("common.retry")} /> : <LoadingState label={t("dashboard.loading")} />}
      </div>
    );
  }

  const contentTypes = stats.content_types ?? {};
  const maxType = Math.max(1, ...Object.values(contentTypes));
  const exact = dups?.exact ?? [];
  const similar = dups?.similar ?? [];

  return (
    <div className="page dashboard-page">
      <PageHeader
        eyebrow={t("dashboard.eyebrow")}
        title={t("dashboard.title")}
        subtitle={t("dashboard.subtitle")}
        action={
          <button className="btn primary" onClick={rescan} disabled={scanning}>
            {scanning ? <span className="spinner light" /> : <Icon name="refresh" size={15} />}
            {scanning ? t("dashboard.scanning") : t("dashboard.rescan")}
          </button>
        }
      />

      {error && <ErrorBox message={error} onRetry={load} retryLabel={t("common.retry")} />}

      <div className="stat-grid">
        <StatCard icon="document" tone="indigo" label={t("dashboard.statDocuments")} value={fmtNumber(stats.documents, lang)} />
        <StatCard icon="hash" tone="cyan" label={t("dashboard.statWords")} value={fmtNumber(stats.words, lang)} />
        <StatCard icon="database" tone="violet" label={t("dashboard.statBytes")} value={fmtBytes(stats.bytes)} />
        <StatCard icon="tag" tone="amber" label={t("dashboard.statTags")} value={fmtNumber(stats.tags, lang)} />
        <StatCard icon="timeline" tone="green" label={t("dashboard.statEvents")} value={fmtNumber(stats.events, lang)} />
      </div>

      <div className="dash-columns">
        <Card className="card-types">
          <CardHeading icon="layers" title={t("dashboard.contentTypes")} />
          {Object.entries(contentTypes).length === 0 ? (
            <div className="inline-empty">
              {t("dashboard.emptyVault")} <code>memoryvault index &lt;dir&gt;</code> {t("dashboard.emptyVaultEnd")}
            </div>
          ) : (
            <div className="type-list">
              {Object.entries(contentTypes).map(([type, n]) => (
                <div className="type-row" key={type}>
                  <span className="type-name">{type}</span>
                  <div className="type-bar">
                    <div className="type-fill" style={{ width: `${(n / maxType) * 100}%` }} />
                  </div>
                  <span className="type-count">{fmtNumber(n, lang)}</span>
                </div>
              ))}
            </div>
          )}
        </Card>

        <Card className="card-tags">
          <CardHeading icon="tag" title={t("dashboard.topTags")} />
          {tags.length === 0 ? (
            <div className="inline-empty">{t("dashboard.noTags")}</div>
          ) : (
            <div className="tag-cloud">
              {tags.slice(0, 16).map((tag) => (
                <Link key={tag.name} to={`/?tag=${encodeURIComponent(tag.name)}`} className="tag-chip">
                  {tag.name}<span>{fmtNumber(tag.document_count, lang)}</span>
                </Link>
              ))}
            </div>
          )}
        </Card>

        <Card className="card-dups">
          <CardHeading icon="copy" title={t("dashboard.duplicates")} />
          <div className="dup-summary">
            <div><strong>{fmtNumber(exact.length, lang)}</strong><span>{t("dashboard.exact")}</span></div>
            <div><strong>{fmtNumber(similar.length, lang)}</strong><span>{t("dashboard.near")}</span></div>
          </div>
          {[...exact.slice(0, 3), ...similar.slice(0, 3)].map((group, i) => (
            <div className="dup-line" key={`${group.kind}-${i}`}>
              <span className={`dup-dot ${group.kind}`} />
              {group.document_ids.map((id) => (
                <Link to={`/doc/${id}`} key={id}>#{id}</Link>
              ))}
              {group.similarity != null && (
                <span className="dup-pct">{Math.round(group.similarity * 100)}%</span>
              )}
            </div>
          ))}
          {exact.length === 0 && similar.length === 0 && (
            <div className="inline-empty">{t("dashboard.noDuplicates")}</div>
          )}
        </Card>
      </div>

      <Card className="card-recent">
        <CardHeading icon="clock" title={t("dashboard.recent")} />
        <ul className="doc-rows">
          {docs.map((doc) => (
            <li key={doc.id}>
              <span className="doc-row-icon"><Icon name="document" size={16} /></span>
              <Link to={`/doc/${doc.id}`} className="doc-row-title">{doc.title}</Link>
              <span className="doc-row-path" title={doc.path}>{doc.path}</span>
              <TypeBadge type={doc.content_type} />
              <span className="doc-row-time">{fmtDate(doc.modified_at, lang)}</span>
              <Icon name="arrowRight" size={15} className="doc-row-arrow" />
            </li>
          ))}
          {docs.length === 0 && <li className="inline-empty">{t("dashboard.noDocs")}</li>}
        </ul>
      </Card>
    </div>
  );
}
