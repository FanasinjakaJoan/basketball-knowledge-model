"""A tiny dependency-free web explorer for the knowledge graph.

    python -m basketball_kg.cli serve --port 8000

Serves ``web/index.html`` plus a read-only JSON API over the loaded graph. Standard
library only: no framework, no build step, no outbound requests. Bind to 0.0.0.0 so it
works behind a proxy/preview host.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qs, urlparse

from .graph import graph_stats, subgraph_around, to_networkx, to_node_link
from .model import KnowledgeGraph, load_graph
from .nlq import VocabularyIndex, answer, parse
from .queries import INTENTS, QueryPlan, intent_help
from .viz import ascii_court, to_dot

WEB_DIR = Path(__file__).resolve().parent.parent / "web"


class KnowledgeGraphServer:
    """Holds the loaded graph and answers API requests (single shared instance)."""

    def __init__(self, kg: Optional[KnowledgeGraph] = None, data_dir: Optional[Path] = None) -> None:
        self.kg = kg or load_graph(data_dir)
        self.index = VocabularyIndex(self.kg)
        self.nx = to_networkx(self.kg)

    # -- API ---------------------------------------------------------------- #
    def stats(self) -> Dict[str, Any]:
        stats = graph_stats(self.nx)
        types = sorted({n.type for n in self.kg.nodes.values()})
        return {
            "version": "0.1.0",
            "datasets": [
                {"id": d.id, "label": d.label, "file": d.path.name,
                 "nodes": sum(1 for n in self.kg.nodes.values() if n.dataset == d.id)}
                for d in self.kg.datasets
            ],
            "nodes": stats["nodes"],
            "edges": stats["edges"],
            "density": stats["density"],
            "node_types": stats["node_types"],
            "predicates": stats["predicates"],
            "most_connected": stats["most_connected"][:8],
            "types": types,
            "validation": self.kg.validate(),
        }

    def ask(self, question: str) -> Dict[str, Any]:
        plan = parse(self.kg, question, index=self.index)
        result = plan.execute(kg=self.kg)
        return {
            "question": question,
            "intent": plan.intent,
            "slots": plan.slots,
            "confidence": plan.confidence,
            "evidence": plan.evidence,
            "summary": result.summary,
            "rows": result.rows,
            "sparql": plan.to_sparql(),
            "cypher": plan.to_cypher(),
            "pattern": plan.to_graph_pattern(),
        }

    def search(self, text: str, types: Optional[List[str]] = None, limit: int = 40) -> Dict[str, Any]:
        hits = self.kg.search(text, types)[:limit]
        return {
            "query": text,
            "rows": [
                {"id": n.id, "type": n.type, "label": n.name, "score": s, "definition": n.definition}
                for n, s in hits
            ],
        }

    def node(self, node_id: str) -> Dict[str, Any]:
        found = self.kg.get(node_id)
        # a bare word falls back to search; a CURIE that misses is a real miss
        if found is None and ":" not in node_id:
            hits = self.kg.search(node_id)
            found = hits[0][0] if hits else None
        if found is None:
            return {"error": f"not found: {node_id}"}
        outgoing = {
            predicate: [
                {"id": t, "label": self.kg[t].name if t in self.kg else t,
                 "type": self.kg[t].type if t in self.kg else "?"}
                for t in targets
            ]
            for predicate, targets in sorted(found.edges.items())
        }
        return {
            "id": found.id,
            "type": found.type,
            "label": found.name,
            "definition": found.definition,
            "props": found.props,
            "keys": found.keys(),
            "outgoing": outgoing,
            "incoming": [
                {"id": src, "predicate": p, "label": self.kg[src].name}
                for src, p in sorted(_incoming(self.kg, found.id))[:60]
            ],
            "dot": to_dot(self.kg, node_ids=_neighbourhood(self.kg, self.nx, found.id, 1)),
        }

    def graph(self, focus: Optional[str] = None, depth: int = 1, limit: int = 220) -> Dict[str, Any]:
        g = self.nx
        if focus:
            g = subgraph_around(g, [focus], depth=depth)
        if g.number_of_nodes() > limit:
            # keep the best-connected nodes so the layout stays readable
            ranked = sorted(g.degree(), key=lambda kv: -kv[1])[:limit]
            g = g.subgraph([n for n, _ in ranked]).copy()
        payload = to_node_link(g)
        for node in payload["nodes"]:
            node["definition"] = str(node.get("definition", ""))[:200]
        return payload

    def court(self, highlight: Optional[List[str]] = None, scheme: Optional[str] = None) -> Dict[str, Any]:
        marks = list(highlight or [])
        if scheme:
            node = self.kg.get(scheme) or self.kg.resolve(scheme)
            if node is not None:
                zones: List[str] = []
                for cid in [node.id, *node.out("relatedTo"), *self.kg.in_(node.id, "relatedTo")]:
                    holder = self.kg.get(cid)
                    if not holder:
                        continue
                    for assignment in sorted(set(holder.out("hasAssignment") + self.kg.in_(cid, "ofScheme"))):
                        if self.kg.get(assignment):
                            zones.extend(self.kg[assignment].out("coversZone"))
                marks.extend(sorted(set(zones)))
        return {"court": ascii_court(self.kg, highlight=marks), "highlighted": marks}

    def intents(self) -> Dict[str, Any]:
        return {"intents": INTENTS, "help": intent_help()}

    def examples(self) -> Dict[str, Any]:
        return {
            "questions": [
                "How do you attack a 2-3 zone?",
                "Who covers the corner in a 2-3 zone?",
                "What beats drop coverage?",
                "What rules govern setting a screen?",
                "Walk me through the pick and roll.",
                "What happens after the roll?",
                "What kind of players does motion offence need?",
                "Who on Harbour fits switch all?",
                "What is next to the short corner?",
                "What should we run late in the shot clock?",
                "What is drop coverage?",
                "What are the 2-3 zone assignments?",
            ],
            "schemes": [
                {"id": s.id, "label": s.name}
                for s in sorted(self.kg.by_type("Scheme", "OffensiveScheme", "DefensiveScheme"), key=lambda n: n.name)
            ],
            "plays": [{"id": p.id, "label": p.name} for p in self.kg.by_type("Play", "OffensivePlay", "DefensivePlay")],
        }


def _incoming(kg: KnowledgeGraph, node_id: str):
    for node in kg.nodes.values():
        for predicate, targets in node.edges.items():
            if node_id in targets:
                yield node.id, predicate


def _neighbourhood(kg: KnowledgeGraph, nx_graph, node_id: str, depth: int) -> List[str]:
    sub = subgraph_around(nx_graph, [node_id], depth=depth)
    return list(sub.nodes)


# --------------------------------------------------------------------------- #
# HTTP plumbing
# --------------------------------------------------------------------------- #


class Handler(BaseHTTPRequestHandler):
    server_version = "BasketballKG/0.1"
    app: KnowledgeGraphServer  # injected by create_server

    def log_message(self, fmt: str, *args) -> None:  # keep the console readable
        if "/api/" in (self.path or ""):
            return
        super().log_message(fmt, *args)

    # -- helpers ------------------------------------------------------------ #
    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def _json(self, payload: Any, status: int = 200) -> None:
        self._send(status, json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _html(self, body: bytes) -> None:
        self._send(200, body, "text/html; charset=utf-8")

    def _params(self):
        return parse_qs(urlparse(self.path).query)

    # -- routes ------------------------------------------------------------- #
    def do_HEAD(self) -> None:  # noqa: N802
        self.do_GET()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path, params = parsed.path, parse_qs(parsed.query)

        def one(key, default=None):
            value = params.get(key, [default])
            return value[0] if value else default

        try:
            if path in {"/", "/index.html"}:
                index = WEB_DIR / "index.html"
                self._html(index.read_bytes())
                return
            if path == "/favicon.ico":
                self._send(204, b"", "image/x-icon")
                return
            if path == "/api/stats":
                self._json(self.app.stats())
            elif path == "/api/ask":
                question = one("q", "")
                self._json(self.app.ask(question) if question.strip() else {"error": "empty question"})
            elif path == "/api/search":
                self._json(self.app.search(one("q", ""), params.get("type"), limit=int(one("limit", 40))))
            elif path == "/api/node":
                self._json(self.app.node(one("id", "")))
            elif path == "/api/graph":
                self._json(self.app.graph(focus=one("focus"), depth=int(one("depth", 1))))
            elif path == "/api/court":
                self._json(self.app.court(highlight=params.get("highlight"), scheme=one("scheme")))
            elif path == "/api/intents":
                self._json(self.app.intents())
            elif path == "/api/examples":
                self._json(self.app.examples())
            elif path == "/api/plan":
                plan = QueryPlan(intent=one("intent", "describe"),
                                 slots={k: v[0] for k, v in params.items() if k != "intent"})
                self._json({"intent": plan.intent, "sparql": plan.to_sparql(), "cypher": plan.to_cypher()})
            elif path.startswith("/web/"):
                target = (WEB_DIR.parent / path[1:]).resolve()
                if target.is_file() and str(target).startswith(str(WEB_DIR.parent)):
                    ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
                    self._send(200, target.read_bytes(), ctype)
                else:
                    self._json({"error": "not found"}, 404)
            else:
                self._json({"error": f"no route for {path}"}, HTTPStatus.NOT_FOUND)
        except Exception as exc:  # pragma: no cover - defensive
            self._json({"error": f"{type(exc).__name__}: {exc}"}, 500)


def create_server(
    host: str = "0.0.0.0",
    port: int = 8000,
    data_dir: Optional[Path] = None,
    app: Optional[KnowledgeGraphServer] = None,
):
    app = app or KnowledgeGraphServer(data_dir=data_dir)
    handler = type("BoundHandler", (Handler,), {"app": app})
    return ThreadingHTTPServer((host, port), handler), app


def main(argv=None, app: Optional[KnowledgeGraphServer] = None) -> int:
    parser = argparse.ArgumentParser(description="Serve the basketball knowledge graph explorer.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--data", type=Path, default=None)
    args = parser.parse_args(argv)
    httpd, app = create_server(args.host, args.port, args.data, app=app)
    print(f"Basketball Knowledge Model explorer: http://{args.host}:{args.port}")
    print(f"  {len(app.kg)} nodes, {app.nx.number_of_edges()} edges, {len(app.kg.datasets)} datasets")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
