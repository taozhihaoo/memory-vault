"""MemoryVault command-line interface.

Commands
--------
index      Index a directory (incrementally: only changed files are re-parsed).
watch      Keep scanning for file-system changes and re-index live.
search     Keyword search with BM25 ranking and highlighted snippets.
show       Print a stored document.
stats      Vault statistics.
tags       List tags and topics with document counts.
duplicates Find exact and near duplicates.
graph      Export the knowledge graph as JSON.
timeline   Show recent document activity.
serve      Start the local HTTP API (+ dashboard if built).
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from memoryvault import __version__
from memoryvault.config import VaultConfig
from memoryvault.vault import Vault


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="memoryvault",
        description="MemoryVault — local-first personal knowledge engine.",
    )
    parser.add_argument("--db", default=None, help="Path to the SQLite vault file")
    parser.add_argument("--version", action="version", version=f"memoryvault {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_index = sub.add_parser("index", help="Index a directory (incremental)")
    p_index.add_argument("path", help="Directory (or file) to index")
    p_index.add_argument("--json", action="store_true", help="Machine-readable output")

    p_watch = sub.add_parser("watch", help="Watch directories and index changes live")
    p_watch.add_argument("paths", nargs="+", help="Directories to watch")

    p_search = sub.add_parser("search", help="Keyword search (BM25)")
    p_search.add_argument("query")
    p_search.add_argument("--limit", type=int, default=20)
    p_search.add_argument("--offset", type=int, default=0)
    p_search.add_argument("--type", dest="content_type", default=None)
    p_search.add_argument("--tag", default=None)
    p_search.add_argument("--json", action="store_true")

    p_show = sub.add_parser("show", help="Show one stored document")
    p_show.add_argument("document_id", type=int)
    p_show.add_argument("--max-chars", type=int, default=4000)

    sub.add_parser("stats", help="Vault statistics")
    sub.add_parser("tags", help="List tags and topics")
    sub.add_parser("duplicates", help="Find exact and near duplicates")

    p_graph = sub.add_parser("graph", help="Export the knowledge graph")
    p_graph.add_argument("--out", default="-", help="Output file (default: stdout)")

    p_timeline = sub.add_parser("timeline", help="Recent document activity")
    p_timeline.add_argument("--limit", type=int, default=25)
    p_timeline.add_argument("--group-by", choices=["day", "month"], default="day")

    p_serve = sub.add_parser("serve", help="Start the local API server")
    p_serve.add_argument("--host", default=None)
    p_serve.add_argument("--port", type=int, default=None)

    p_scan = sub.add_parser("scan", help="Incremental scan of configured watch paths")
    p_scan.add_argument("paths", nargs="*", help="Optional explicit roots")
    p_scan.add_argument("--json", action="store_true")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    config = VaultConfig()
    if args.db:
        config.db_path = Path(args.db)

    handlers = {
        "index": _cmd_index,
        "watch": _cmd_watch,
        "search": _cmd_search,
        "show": _cmd_show,
        "stats": _cmd_stats,
        "tags": _cmd_tags,
        "duplicates": _cmd_duplicates,
        "graph": _cmd_graph,
        "timeline": _cmd_timeline,
        "serve": _cmd_serve,
        "scan": _cmd_scan,
    }
    return handlers[args.command](args, config)


# --------------------------------------------------------------------- commands
def _cmd_index(args, config: VaultConfig) -> int:
    config.watch_paths = [Path(args.path)]
    with Vault(config) as vault:
        vault.scanner.remember_roots([Path(args.path)])
        started = time.perf_counter()
        stats = vault.scanner.scan(roots=[Path(args.path)])
        elapsed = time.perf_counter() - started
    if args.json:
        print(json.dumps({**stats.to_dict(), "seconds": round(elapsed, 2)}))
    else:
        print(
            f"indexed {args.path}: {stats.created} created, {stats.updated} updated, "
            f"{stats.unchanged} unchanged, {stats.errors} errors "
            f"({elapsed:.2f}s)"
        )
    return 1 if stats.errors else 0


def _cmd_scan(args, config: VaultConfig) -> int:
    explicit = [Path(p) for p in args.paths]
    with Vault(config) as vault:
        if explicit:
            vault.scanner.remember_roots(explicit)
        else:
            remembered = vault.scanner.remembered_roots()
            vault.config.watch_paths = vault.config.watch_paths or remembered
        if not vault.config.watch_paths and not explicit:
            print("no watch paths configured; pass directories to scan", file=sys.stderr)
            return 2
        stats = vault.scanner.scan(roots=explicit or None)
    if args.json:
        print(json.dumps(stats.to_dict()))
    else:
        print(json.dumps(stats.to_dict(), indent=2))
    return 0


def _cmd_watch(args, config: VaultConfig) -> int:
    config.watch_paths = [Path(p) for p in args.paths]
    with Vault(config) as vault:
        vault.scanner.remember_roots(vault.config.watch_paths)
        print(f"watching {len(vault.config.watch_paths)} path(s) — Ctrl+C to stop")
        for root in config.watch_paths:
            stats = vault.scanner.scan(roots=[root])
            print(
                f"  initial scan {root}: +{stats.created} ~{stats.updated} "
                f"={stats.unchanged} !{stats.errors}"
            )
        from memoryvault.indexer.scanner import VaultWatcher

        def on_scan(stats) -> None:
            print(
                f"  change: +{stats.created} ~{stats.updated} ={stats.unchanged}"
            )

        watcher = VaultWatcher(vault.scanner, config, on_scan=on_scan)
        try:
            with watcher:
                while True:
                    time.sleep(0.5)
        except KeyboardInterrupt:
            print("\nstopped")
    return 0


def _cmd_search(args, config: VaultConfig) -> int:
    with Vault(config) as vault:
        found = vault.search.search(
            args.query,
            limit=args.limit,
            offset=args.offset,
            content_type=args.content_type,
            tag=args.tag,
        )
    if args.json:
        print(json.dumps(found, default=_json_default, indent=2))
        return 0
    if not found["results"]:
        print("no results")
        return 0
    print(f"{found['total']} result(s) for {args.query!r}\n")
    for hit in found["results"]:
        print(f"[{hit.score:7.3f}] #{hit.document_id}  {hit.title}")
        print(f"          {hit.path}")
        snippet = hit.snippet.replace("\n", " ")
        print(f"          {snippet}\n")
    return 0


def _cmd_show(args, config: VaultConfig) -> int:
    with Vault(config) as vault:
        doc = vault.repo.get(args.document_id)
    if doc is None:
        print(f"document #{args.document_id} not found", file=sys.stderr)
        return 1
    print(f"# {doc.title}")
    print(f"  path:    {doc.path}")
    print(f"  type:    {doc.content_type}")
    print(f"  sha256:  {doc.sha256}")
    print(f"  words:   {doc.word_count}")
    if doc.tags:
        print(f"  tags:    {', '.join(doc.tags)}")
    if doc.topics:
        print(f"  topics:  {', '.join(doc.topics)}")
    print()
    print(doc.content[: args.max_chars])
    if len(doc.content) > args.max_chars:
        print(f"\n… truncated ({len(doc.content)} chars total)")
    return 0


def _cmd_stats(args, config: VaultConfig) -> int:
    with Vault(config) as vault:
        stats = vault.stats()
    print(json.dumps(stats, indent=2))
    return 0


def _cmd_tags(args, config: VaultConfig) -> int:
    with Vault(config) as vault:
        tags = vault.repo.list_tags()
    if not tags:
        print("no tags yet")
        return 0
    width = max(len(t["name"]) for t in tags)
    for tag in tags:
        bar = "█" * min(tag["document_count"], 40)
        print(f"{tag['name']:<{width}}  {tag['document_count']:>4}  {bar}")
    return 0


def _cmd_duplicates(args, config: VaultConfig) -> int:
    with Vault(config) as vault:
        exact = vault.dedup.find_exact_duplicates()
        similar = vault.dedup.find_similar_pairs()
    for group in exact:
        print(f"EXACT  ids={group.document_ids}")
    for group in similar:
        print(f"SIMILAR ({group.similarity:.2%}) ids={group.document_ids}")
    if not exact and not similar:
        print("no duplicates found")
    return 0


def _cmd_graph(args, config: VaultConfig) -> int:
    with Vault(config) as vault:
        graph = vault.graph.build()
    payload = json.dumps(graph, indent=2)
    if args.out == "-":
        print(payload)
    else:
        Path(args.out).write_text(payload, encoding="utf-8")
        print(f"graph written to {args.out}")
    return 0


def _cmd_timeline(args, config: VaultConfig) -> int:
    with Vault(config) as vault:
        activity = vault.timeline.activity(group_by=args.group_by)
        recent = vault.timeline.recent(limit=args.limit)
    print(f"activity by {args.group_by}:")
    for bucket in activity["buckets"]:
        print(f"  {bucket['date']}  {bucket['total']:>4}  {bucket['counts']}")
    print(f"\nrecent events (last {args.limit}):")
    for event in recent:
        print(f"  {event['occurred_at']}  {event['event_type']:<8} {event['title'] or event['path']}")
    return 0


def _cmd_serve(args, config: VaultConfig) -> int:
    import uvicorn

    config.api_host = args.host or config.api_host
    config.api_port = args.port or config.api_port
    if config.frontend_dist is None:
        for candidate in (Path("frontend/dist"), Path("frontend-dist")):
            if candidate.is_dir():
                config.frontend_dist = candidate.resolve()
                break

    from memoryvault.api import create_app

    app = create_app(config=config)
    # Reuse this process's vault through the app lifespan; serve forever.
    print(f"MemoryVault API on http://{config.api_host}:{config.api_port}")
    uvicorn.run(app, host=config.api_host, port=config.api_port, log_level="info")
    return 0


def _json_default(obj):
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    return str(obj)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
