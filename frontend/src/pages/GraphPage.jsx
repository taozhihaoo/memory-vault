import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, fmtNumber } from "../api.js";
import { useI18n } from "../locale.jsx";
import { EmptyState, ErrorBox, Icon, LoadingState, PageHeader } from "../components.jsx";

const KINDS = [
  { key: "document", color: "#818cf8" },
  { key: "tag", color: "#34d399" },
  { key: "topic", color: "#fbbf24" },
];

const KIND_COLORS = Object.fromEntries(KINDS.map((k) => [k.key, k.color]));

// Deterministic pseudo-random generator so layouts are reproducible.
function mulberry32(seed) {
  let a = seed >>> 0;
  return function () {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/**
 * Force-directed graph on a canvas — hand-rolled, deterministic, no external
 * graph libraries. Coordinates are CSS pixels (the canvas is scaled for DPR),
 * so hit-testing matches the pointer exactly on any display or zoom level.
 */
function ForceGraph({ graph, onPick, labels, hint, nodesLabel, edgesLabel }) {
  const wrapRef = useRef(null);
  const canvasRef = useRef(null);
  const [filter, setFilter] = useState({ document: true, tag: true, topic: true });
  const [seed, setSeed] = useState(42);
  const [size, setSize] = useState({ w: 1000, h: 560 });
  const [hover, setHover] = useState(null);

  const nodes = useMemo(
    () => graph.nodes.filter((n) => filter[n.kind]),
    [graph, filter]
  );
  const nodeIds = useMemo(() => new Set(nodes.map((n) => n.id)), [nodes]);
  const edges = useMemo(
    () => graph.edges.filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target)),
    [graph, nodeIds]
  );

  useEffect(() => {
    const el = wrapRef.current;
    if (!el || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver((entries) => {
      const rect = entries[0].contentRect;
      if (rect.width > 0) setSize({ w: Math.round(rect.width), h: 560 });
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const { w, h } = size;
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    canvas.style.width = `${w}px`;
    canvas.style.height = `${h}px`;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

    const rand = mulberry32(seed);
    const sim = {
      nodes: nodes.map((n) => ({
        ...n,
        x: w / 2 + (rand() - 0.5) * w * 0.72,
        y: h / 2 + (rand() - 0.5) * h * 0.72,
        vx: 0,
        vy: 0,
      })),
      edges,
      alpha: 1,
      stopped: false,
    };
    const byId = new Map(sim.nodes.map((n) => [n.id, n]));

    function radius(node) {
      return node.kind === "document"
        ? 6 + Math.min(11, (node.degree || 1) * 1.4)
        : 4.5 + Math.min(6, (node.degree || 1) * 0.9);
    }

    function tick() {
      const N = sim.nodes;
      const repulsion = 2600;
      for (let i = 0; i < N.length; i++) {
        for (let j = i + 1; j < N.length; j++) {
          const a = N[i], b = N[j];
          let dx = b.x - a.x, dy = b.y - a.y;
          let d2 = dx * dx + dy * dy;
          if (d2 < 1) { dx = rand() - 0.5; dy = rand() - 0.5; d2 = 1; }
          const d = Math.sqrt(d2);
          const force = repulsion / d2;
          const fx = (dx / d) * force, fy = (dy / d) * force;
          a.vx -= fx; a.vy -= fy;
          b.vx += fx; b.vy += fy;
        }
      }
      for (const e of sim.edges) {
        const a = byId.get(e.source), b = byId.get(e.target);
        if (!a || !b) continue;
        const dx = b.x - a.x, dy = b.y - a.y;
        const d = Math.sqrt(dx * dx + dy * dy) || 1;
        const force = (d - 92) * 0.004;
        const fx = (dx / d) * force, fy = (dy / d) * force;
        a.vx += fx; a.vy += fy;
        b.vx -= fx; b.vy -= fy;
      }
      for (const n of N) {
        n.vx += (w / 2 - n.x) * 0.0016;
        n.vy += (h / 2 - n.y) * 0.0016;
        n.vx *= 0.82; n.vy *= 0.82;
        n.x += Math.max(-14, Math.min(14, n.vx));
        n.y += Math.max(-14, Math.min(14, n.vy));
        n.x = Math.max(24, Math.min(w - 24, n.x));
        n.y = Math.max(24, Math.min(h - 24, n.y));
      }
      sim.alpha *= 0.995;
    }

    function draw() {
      ctx.clearRect(0, 0, w, h);
      for (const e of sim.edges) {
        const a = byId.get(e.source), b = byId.get(e.target);
        if (!a || !b) continue;
        ctx.strokeStyle = e.kind === "similar"
          ? "rgba(251, 113, 133, 0.42)"
          : e.kind === "mentions"
          ? "rgba(129, 140, 248, 0.5)"
          : "rgba(148, 163, 184, 0.13)";
        ctx.lineWidth = e.kind === "has_tag" || e.kind === "has_topic" ? 1 : 1.6;
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
      }
      for (const n of sim.nodes) {
        const r = radius(n);
        const color = KIND_COLORS[n.kind] || "#94a3b8";
        ctx.save();
        ctx.shadowColor = color;
        ctx.shadowBlur = n.kind === "document" ? 14 : 8;
        ctx.beginPath();
        ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.globalAlpha = 0.9;
        ctx.fill();
        ctx.restore();
        if (n.kind === "document") {
          ctx.strokeStyle = "rgba(255,255,255,0.55)";
          ctx.lineWidth = 1.2;
          ctx.beginPath();
          ctx.arc(n.x, n.y, r + 2.5, 0, Math.PI * 2);
          ctx.stroke();
        }
        if (sim.alpha > 0.12 || r > 8 || n.kind === "document") {
          ctx.font = "11px ui-sans-serif, system-ui, sans-serif";
          ctx.fillStyle = "rgba(226, 232, 240, 0.88)";
          ctx.shadowColor = "rgba(8, 11, 18, 0.95)";
          ctx.shadowBlur = 6;
          ctx.fillText(String(n.label ?? "").slice(0, 30), n.x + r + 6, n.y + 4);
          ctx.shadowBlur = 0;
        }
      }
    }

    let raf;
    function loop() {
      if (sim.stopped) return;
      for (let k = 0; k < 3 && sim.alpha > 0.02; k++) tick();
      draw();
      raf = requestAnimationFrame(loop);
    }
    loop();

    function locate(evt) {
      const rect = canvas.getBoundingClientRect();
      const x = ((evt.clientX - rect.left) / rect.width) * w;
      const y = ((evt.clientY - rect.top) / rect.height) * h;
      let found = null;
      let best = Infinity;
      for (const node of sim.nodes) {
        const dist = Math.hypot(node.x - x, node.y - y);
        if (dist < radius(node) + 7 && dist < best) { best = dist; found = node; }
      }
      return { found, x, y };
    }

    function onMove(evt) {
      const { found, x, y } = locate(evt);
      canvas.style.cursor = found?.kind === "document" ? "pointer" : "default";
      setHover(found ? { id: found.id, label: found.label, kind: found.kind, x, y } : null);
    }
    function onLeave() {
      setHover(null);
      canvas.style.cursor = "default";
    }
    function onClick(evt) {
      const { found } = locate(evt);
      if (found?.kind === "document" && found.document_id != null) onPick?.(found);
    }
    canvas.addEventListener("mousemove", onMove);
    canvas.addEventListener("mouseleave", onLeave);
    canvas.addEventListener("click", onClick);
    return () => {
      sim.stopped = true;
      cancelAnimationFrame(raf);
      canvas.removeEventListener("mousemove", onMove);
      canvas.removeEventListener("mouseleave", onLeave);
      canvas.removeEventListener("click", onClick);
    };
  }, [nodes, edges, size, seed, onPick]);

  return (
    <div className="graph-wrap">
      <div className="graph-toolbar">
        <div className="graph-legend">
          {KINDS.map((kind, index) => (
            <button
              key={kind.key}
              type="button"
              className={`legend-item ${filter[kind.key] ? "" : "off"}`}
              onClick={() => setFilter((f) => ({ ...f, [kind.key]: !f[kind.key] }))}
            >
              <span className="legend-dot" style={{ background: kind.color }} />
              {labels[index]}
            </button>
          ))}
        </div>
        <div className="graph-toolbar-right">
          <span className="graph-count">
            {nodes.length} {nodesLabel} · {edges.length} {edgesLabel}
          </span>
          <button type="button" className="btn ghost small" onClick={() => setSeed((s) => s + 1)} title="Re-layout">
            <Icon name="refresh" size={14} />
          </button>
        </div>
      </div>
      <div className="graph-canvas-wrap" ref={wrapRef}>
        <canvas ref={canvasRef} className="graph-canvas" />
        {hover && (
          <div className="graph-tooltip" style={{ left: hover.x + 14, top: hover.y - 10 }}>
            <span className="legend-dot" style={{ background: KIND_COLORS[hover.kind] }} />
            {hover.label}
          </div>
        )}
        <div className="graph-hint"><Icon name="info" size={13} />{hint}</div>
      </div>
    </div>
  );
}

export default function GraphPage() {
  const { lang, t } = useI18n();
  const navigate = useNavigate();
  const [graph, setGraph] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    api.graph({ include_similar: true, include_cooccurrence: true })
      .then((g) => !cancelled && setGraph(g))
      .catch((e) => !cancelled && setError(e.message));
    return () => { cancelled = true; };
  }, []);

  const onPick = useCallback((node) => navigate(`/doc/${node.document_id}`), [navigate]);

  return (
    <div className="page graph-page">
      <PageHeader eyebrow={t("graph.eyebrow")} title={t("graph.title")} subtitle={t("graph.subtitle")} />
      {error && <ErrorBox message={error} />}
      {!graph && !error && <LoadingState label={t("graph.loading")} cards={1} />}
      {graph && graph.nodes.length === 0 && (
        <EmptyState icon="graph" title={t("graph.title")} body={t("dashboard.noDocs")} />
      )}
      {graph && graph.nodes.length > 0 && (
        <>
          <ForceGraph
            graph={graph}
            onPick={onPick}
            labels={[
              t("graph.legendDocuments"),
              t("graph.legendTags"),
              t("graph.legendTopics"),
            ]}
            hint={t("graph.hint")}
            nodesLabel={t("graph.nodes")}
            edgesLabel={t("graph.edges")}
          />
          {graph.meta && (
            <div className="graph-meta">
              <Icon name="layers" size={14} />
              {t("graph.meta", {
                docs: fmtNumber(graph.meta.document_count ?? 0, lang),
                tags: fmtNumber(graph.meta.tag_count ?? 0, lang),
                topics: fmtNumber(graph.meta.topic_count ?? 0, lang),
                edges: fmtNumber(graph.edges.length, lang),
              })}
            </div>
          )}
        </>
      )}
    </div>
  );
}
