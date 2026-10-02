import React, { useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api.js";

const KIND_COLORS = {
  document: "#4f9cf9",
  tag: "#3ddc97",
  topic: "#f6c344",
};

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
 * Force-directed graph on a canvas — hand-rolled, deterministic,
 * no external graph libraries. Simple O(n²) simulation is fine for
 * personal-vault sizes (hundreds of nodes).
 */
function ForceGraph({ graph, onPick }) {
  const canvasRef = useRef(null);
  const simRef = useRef(null);

  const [filter, setFilter] = useState({ document: true, tag: true, topic: true });

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
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    const rand = mulberry32(42);
    const width = canvas.width;
    const height = canvas.height;

    const sim = {
      nodes: nodes.map((n, i) => ({
        ...n,
        x: width / 2 + (rand() - 0.5) * width * 0.7,
        y: height / 2 + (rand() - 0.5) * height * 0.7,
        vx: 0,
        vy: 0,
      })),
      edges,
      alpha: 1,
      stopped: false,
    };
    simRef.current = sim;
    const byId = new Map(sim.nodes.map((n) => [n.id, n]));

    function tick() {
      const N = sim.nodes;
      // repulsion (sampled for large graphs)
      const repulsion = 2200;
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
      // spring attraction along edges
      for (const e of sim.edges) {
        const a = byId.get(e.source), b = byId.get(e.target);
        if (!a || !b) continue;
        const dx = b.x - a.x, dy = b.y - a.y;
        const d = Math.sqrt(dx * dx + dy * dy) || 1;
        const target = 90;
        const force = (d - target) * 0.004;
        const fx = (dx / d) * force, fy = (dy / d) * force;
        a.vx += fx; a.vy += fy;
        b.vx -= fx; b.vy -= fy;
      }
      // centering + integration
      for (const n of N) {
        n.vx += (width / 2 - n.x) * 0.0015;
        n.vy += (height / 2 - n.y) * 0.0015;
        n.vx *= 0.82; n.vy *= 0.82;
        n.x += Math.max(-14, Math.min(14, n.vx));
        n.y += Math.max(-14, Math.min(14, n.vy));
        n.x = Math.max(20, Math.min(width - 20, n.x));
        n.y = Math.max(20, Math.min(height - 20, n.y));
      }
      sim.alpha *= 0.995;
    }

    function draw() {
      ctx.clearRect(0, 0, width, height);
      ctx.fillStyle = "#0d1117";
      ctx.fillRect(0, 0, width, height);

      for (const e of sim.edges) {
        const a = byId.get(e.source), b = byId.get(e.target);
        if (!a || !b) continue;
        ctx.strokeStyle = e.kind === "similar"
          ? "rgba(240, 113, 120, 0.35)"
          : e.kind === "mentions"
          ? "rgba(79, 156, 249, 0.45)"
          : "rgba(139, 148, 158, 0.14)";
        ctx.lineWidth = e.kind === "has_tag" || e.kind === "has_topic" ? 1 : 1.6;
        ctx.beginPath();
        ctx.moveTo(a.x, a.y);
        ctx.lineTo(b.x, b.y);
        ctx.stroke();
      }

      for (const n of sim.nodes) {
        const r = n.kind === "document" ? 6 + Math.min(10, (n.degree || 1)) : 4 + Math.min(6, (n.degree || 1));
        ctx.beginPath();
        ctx.arc(n.x, n.y, r, 0, Math.PI * 2);
        ctx.fillStyle = KIND_COLORS[n.kind] || "#8b949e";
        ctx.fill();
        if (n.kind === "document") {
          ctx.strokeStyle = "rgba(255,255,255,0.35)";
          ctx.lineWidth = 1;
          ctx.stroke();
        }
        if (sim.alpha > 0.12 || r > 7) {
          ctx.fillStyle = "rgba(230, 237, 243, 0.92)";
          ctx.font = "11px system-ui, sans-serif";
          ctx.fillText(n.label.slice(0, 28), n.x + r + 3, n.y + 4);
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

    function onClick(evt) {
      const rect = canvas.getBoundingClientRect();
      const x = evt.clientX - rect.left;
      const y = evt.clientY - rect.top;
      for (const n of sim.nodes) {
        if (n.kind === "document" && Math.hypot(n.x - x, n.y - y) < 10) {
          onPick?.(n);
          return;
        }
      }
    }
    canvas.addEventListener("click", onClick);
    return () => {
      sim.stopped = true;
      cancelAnimationFrame(raf);
      canvas.removeEventListener("click", onClick);
    };
  }, [nodes, edges, onPick]);

  return (
    <div className="graph-wrap">
      <div className="graph-toolbar">
        {Object.keys(KIND_COLORS).map((kind) => (
          <label key={kind} className="legend">
            <input
              type="checkbox"
              checked={filter[kind]}
              onChange={(e) => setFilter((f) => ({ ...f, [kind]: e.target.checked }))}
            />
            <span className="dot" style={{ background: KIND_COLORS[kind] }} />
            {kind}
          </label>
        ))}
        <span className="muted">
          {nodes.length} nodes · {edges.length} edges · click a document to open it
        </span>
      </div>
      <canvas ref={canvasRef} width={1100} height={620} className="graph-canvas" />
    </div>
  );
}

export default function GraphPage() {
  const [graph, setGraph] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api
      .graph({ include_similar: true, include_cooccurrence: true })
      .then(setGraph)
      .catch((e) => setError(e.message));
  }, []);

  if (error) return <div className="error-box">{error}</div>;
  if (!graph) return <div className="empty">Building knowledge graph…</div>;

  return (
    <div className="page graph-page">
      <h2>Knowledge graph</h2>
      <p className="muted">
        Documents, tags and auto-extracted topics. Red edges are near-duplicates,
        blue edges are document-to-document mentions.
      </p>
      <ForceGraph
        graph={graph}
        onPick={(node) => window.open(`/doc/${node.document_id}`, "_self")}
      />
      {graph.meta && (
        <div className="muted graph-meta">
          {graph.meta.document_count} documents · {graph.meta.tag_count} tags ·{" "}
          {graph.meta.topic_count} topics · {graph.edges.length} relationships
        </div>
      )}
    </div>
  );
}
