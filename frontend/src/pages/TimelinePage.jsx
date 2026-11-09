import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, fmtDate, fmtNumber } from "../api.js";
import { useI18n } from "../locale.jsx";
import {
  Card, CardHeading, ErrorBox, LoadingState, PageHeader, Segmented,
} from "../components.jsx";

const EVENT_COLORS = {
  created: "#34d399",
  updated: "#818cf8",
  deleted: "#fb7185",
  indexed: "#22d3ee",
};

export default function TimelinePage() {
  const { lang, t } = useI18n();
  const [activity, setActivity] = useState(null);
  const [events, setEvents] = useState([]);
  const [groupBy, setGroupBy] = useState("day");
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    api.timeline({ group_by: groupBy, days: 365 })
      .then((data) => !cancelled && setActivity(data))
      .catch((e) => !cancelled && setError(e.message));
    return () => { cancelled = true; };
  }, [groupBy]);

  useEffect(() => {
    let cancelled = false;
    api.events({ limit: 60 })
      .then((res) => !cancelled && setEvents(res.events ?? []))
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

  if (error) return <div className="page"><ErrorBox message={error} /></div>;
  if (!activity) {
    return (
      <div className="page">
        <PageHeader eyebrow={t("timeline.eyebrow")} title={t("timeline.title")} subtitle={t("timeline.subtitle")} />
        <LoadingState label={t("timeline.loading")} cards={2} />
      </div>
    );
  }

  const buckets = activity.buckets ?? [];
  const totals = activity.totals ?? {};
  const maxTotal = Math.max(1, ...buckets.map((b) => b.total));

  return (
    <div className="page timeline-page">
      <PageHeader
        eyebrow={t("timeline.eyebrow")}
        title={t("timeline.title")}
        subtitle={t("timeline.subtitle")}
        action={
          <Segmented
            ariaLabel={t("timeline.title")}
            value={groupBy}
            onChange={setGroupBy}
            options={[
              { value: "day", label: t("timeline.byDay") },
              { value: "month", label: t("timeline.byMonth") },
            ]}
          />
        }
      />

      <div className="totals-row">
        {Object.entries(totals).map(([kind, n]) => (
          <div className="total-card" key={kind}>
            <span className="total-color" style={{ background: EVENT_COLORS[kind] || "#94a3b8" }} />
            <div className="total-number" style={{ color: EVENT_COLORS[kind] || "#94a3b8" }}>
              {fmtNumber(n, lang)}
            </div>
            <div className="total-label">{t(`event.${kind}`) || kind}</div>
          </div>
        ))}
      </div>

      <Card className="chart-card">
        <CardHeading icon="timeline" title={t("timeline.indexingActivity")} />
        {buckets.length === 0 ? (
          <div className="inline-empty">{t("timeline.noActivity")}</div>
        ) : (
          <div className="bar-chart">
            {buckets.map((bucket) => (
              <div className="bar-col" key={bucket.date} title={`${bucket.date}: ${bucket.total}`}>
                <div className="bar-value">{bucket.total}</div>
                <div className="bar-track">
                  <div className="bar" style={{ height: `${Math.max(4, (bucket.total / maxTotal) * 100)}%` }} />
                </div>
                <div className="bar-label">{bucket.date.slice(groupBy === "month" ? 0 : 5)}</div>
              </div>
            ))}
          </div>
        )}
      </Card>

      <Card className="events-card">
        <CardHeading icon="clock" title={t("timeline.recentEvents")} />
        <ul className="event-list">
          {events.map((event) => (
            <li key={event.id ?? `${event.path}-${event.occurred_at}`}>
              <span className="event-rail">
                <span className="event-node" style={{ background: EVENT_COLORS[event.event_type] || "#94a3b8" }} />
              </span>
              <span className={`event event-${event.event_type}`}>
                {t(`event.${event.event_type}`) || event.event_type}
              </span>
              <span className="event-title">
                {event.document_id ? (
                  <Link to={`/doc/${event.document_id}`}>{event.title || event.path}</Link>
                ) : (
                  event.title || event.path
                )}
              </span>
              <span className="event-time">{fmtDate(event.occurred_at, lang)}</span>
            </li>
          ))}
          {events.length === 0 && <li className="inline-empty">{t("timeline.nothingYet")}</li>}
        </ul>
      </Card>
    </div>
  );
}
