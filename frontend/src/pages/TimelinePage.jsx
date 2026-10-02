import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, fmtDate } from "../api.js";

const EVENT_COLORS = {
  created: "#3ddc97",
  updated: "#4f9cf9",
  deleted: "#f07178",
};

export default function TimelinePage() {
  const [activity, setActivity] = useState(null);
  const [events, setEvents] = useState([]);
  const [groupBy, setGroupBy] = useState("day");
  const [error, setError] = useState(null);

  useEffect(() => {
    api
      .timeline({ group_by: groupBy, days: 365 })
      .then(setActivity)
      .catch((e) => setError(e.message));
  }, [groupBy]);

  useEffect(() => {
    api.events({ limit: 60 }).then((res) => setEvents(res.events)).catch(() => {});
  }, []);

  if (error) return <div className="error-box">{error}</div>;
  if (!activity) return <div className="empty">Loading activity…</div>;

  const buckets = activity.buckets;
  const maxTotal = Math.max(1, ...buckets.map((b) => b.total));

  return (
    <div className="page timeline-page">
      <div className="timeline-head">
        <h2>Activity timeline</h2>
        <div className="group-toggle">
          {["day", "month"].map((g) => (
            <button
              key={g}
              className={groupBy === g ? "chip active" : "chip"}
              onClick={() => setGroupBy(g)}
            >
              by {g}
            </button>
          ))}
        </div>
      </div>

      <div className="totals-row">
        {Object.entries(activity.totals).map(([kind, n]) => (
          <div className="total-card" key={kind}>
            <div className="total-number" style={{ color: EVENT_COLORS[kind] || "#8b949e" }}>
              {n}
            </div>
            <div className="muted">{kind}</div>
          </div>
        ))}
      </div>

      <section className="chart-card">
        <h3>Indexing activity</h3>
        {buckets.length === 0 && <div className="muted">No activity recorded yet.</div>}
        <div className="bar-chart">
          {buckets.map((b) => (
            <div className="bar-col" key={b.date} title={`${b.date}: ${b.total} events`}>
              <div
                className="bar"
                style={{ height: `${(b.total / maxTotal) * 140}px` }}
              />
              <div className="bar-label muted">{b.date.slice(groupBy === "month" ? 0 : 5)}</div>
            </div>
          ))}
        </div>
      </section>

      <section className="chart-card">
        <h3>Recent events</h3>
        <ul className="event-list">
          {events.map((e) => (
            <li key={e.id ?? `${e.path}-${e.occurred_at}`}>
              <span className={`event event-${e.event_type}`}>{e.event_type}</span>
              <span className="event-title">
                {e.document_id ? (
                  <Link to={`/doc/${e.document_id}`}>{e.title || e.path}</Link>
                ) : (
                  e.title || e.path
                )}
              </span>
              <span className="muted event-time">{fmtDate(e.occurred_at)}</span>
            </li>
          ))}
          {events.length === 0 && <li className="muted">Nothing yet — index a directory first.</li>}
        </ul>
      </section>
    </div>
  );
}
