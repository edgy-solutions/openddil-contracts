#!/usr/bin/env python3
"""Load-before-amend migration: deployment defaults -> site declarations.

DESIGN-2026-11-06-site-declaration.md §7. ADR-0055 §4 step 0. Four steps,
each its own invocation, each writing its result under --out:

    python scripts/migrate_site_declarations.py plan    --helm-dir ../openddil-helm -n NS --vocabulary ATL,BDR --pep URL --session FILE [--pep URL --session FILE ...] --out DIR
    python scripts/migrate_site_declarations.py predict --out DIR
    python scripts/migrate_site_declarations.py load    --helm-dir ../openddil-helm -n NS --pep URL --session FILE ... --out DIR
    python scripts/migrate_site_declarations.py verify  --helm-dir ../openddil-helm -n NS [--after-amend] [--metrics-url URL ...] --out DIR

WHAT EACH STEP MAY DO
  plan     reads only. Pod specs, the deployment's files inside the pods,
           every tier store's census, every PEP's GET /declarations/site.
  predict  reads only, and only the files plan wrote. No cluster.
  load     writes, and only through the PEP's door, with the operator's
           own session. Never a topic write, never an INSERT.
  verify   reads only.
  The amend itself (removing the defaults) is not here. It is a person's
  change to the chart and the bundle.

REFUSAL HALTS. Every refusal stops the whole run with exit 3 and the state
named: what was done, what was not attempted. Nothing retries a refusal, and
nothing rolls back a loaded declaration: a person withdraws one through the
door, with a reason.

THE CLUSTER GUARD runs first in every step that reads the cluster: the
chart's scripts/lib/require-cluster.sh. Its exit 78 is a halt. Every kubectl
call is then pinned to the context it asserted.

UNTESTED AGAINST A CLUSTER. The pure functions below are tested offline
(tests/test_migrate_site_declarations.py). The cluster and HTTP paths have
never run, and the PEP route and the site_declaration table they call do not
exist yet. plan refuses when either is missing.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import hashlib
import json
import pathlib
import re
import ssl
import subprocess
import sys
import urllib.error
import urllib.request

EXIT_OK = 0
EXIT_DIFF = 1          # verify: the census or a citation does not match
EXIT_REFUSED = 3       # a refusal halted the run
EXIT_UNCHECKED = 4     # verify: the census matches, citations were not read
EXIT_GUARD = 78        # the cluster guard refused

RECORD_CLASSES = ("entity", "logistics", "spares")
NULL = None


class Refusal(Exception):
    """A refusal. Halts the run; `state` names what was and was not done."""

    def __init__(self, reason: str, state: dict | None = None):
        super().__init__(reason)
        self.reason = reason
        self.state = state or {}


# --------------------------------------------------------------------------
# Pure: reading the sources out of pod specs and file contents
# --------------------------------------------------------------------------

def env_of(container: dict) -> dict:
    """Inline env of one container. A valueFrom entry is a refusal for the
    names this migration reads, because the plan would then be reading a
    reference and not the value the process holds."""
    out = {}
    for e in container.get("env") or []:
        if "value" in e:
            out[e["name"]] = e["value"]
        elif "valueFrom" in e:
            out[e["name"]] = {"valueFrom": e["valueFrom"]}
    return out


WATCHED_ENV = ("DIS_NATION_RULES", "LOGISTICS_SIM_SITE_NATION",
               "LOGISTICS_SIM_RELEASABILITY_EDGE_DEFAULTS",
               "LOGISTICS_SIM_RELEASABILITY_PATH", "LOGISTICS_SIM_CONFIG_PATH")


def sources_from_pods(pods: dict) -> dict:
    """kubectl get pods -o json -> the nation sources each workload holds.

    Returns {"ingest": {edge: rules_json}, "sim": [{pod, container, env}],
    "ontology_pods": [(pod, container)], "edges": [...]}. Replicas with the
    same env collapse; two different DIS_NATION_RULES at one edge refuse.
    """
    ingest: dict[str, str] = {}
    sims, onto, edges = [], [], set()
    for pod in pods.get("items") or []:
        name = pod["metadata"]["name"]
        if (pod.get("status") or {}).get("phase") != "Running":
            continue
        for c in (pod.get("spec") or {}).get("containers") or []:
            env = env_of(c)
            for k in WATCHED_ENV:
                if isinstance(env.get(k), dict):
                    raise Refusal(f"{name}/{c['name']}: {k} is not inline "
                                  f"({sorted(env[k]['valueFrom'])[0]}); read it "
                                  "and restate it inline before planning")
            edge = env.get("OPENDDIL_EDGE_ID")
            if isinstance(edge, str) and edge:
                edges.add(edge)
            if "DIS_NATION_RULES" in env:
                if not isinstance(edge, str) or not edge:
                    raise Refusal(f"{name}/{c['name']}: DIS_NATION_RULES with "
                                  "no OPENDDIL_EDGE_ID")
                prev = ingest.get(edge)
                if prev is not None and prev != env["DIS_NATION_RULES"]:
                    raise Refusal(f"edge {edge}: two different DIS_NATION_RULES "
                                  f"(second at {name}/{c['name']})")
                ingest[edge] = env["DIS_NATION_RULES"]
            if "LOGISTICS_SIM_CONFIG_PATH" in env:
                sims.append({"pod": name, "container": c["name"], "env": env})
            if any(m.get("mountPath") == "/ontology"
                   for m in c.get("volumeMounts") or []):
                onto.append((name, c["name"]))
    return {"ingest": ingest, "sim": sims, "ontology_pods": onto,
            "edges": sorted(edges)}


def sim_defaults(env: dict, sim_cfg: dict, rel_doc: dict) -> dict:
    """The sim's three defaults and its sites, in its own precedence
    (logistics_sim/config.py:549-575, releasability.py:192-229)."""
    edge_defaults: dict[str, str] = {}
    raw = env.get("LOGISTICS_SIM_RELEASABILITY_EDGE_DEFAULTS")
    if raw is not None:
        for pair in filter(None, (p.strip() for p in raw.split(","))):
            edge, _, nation = pair.partition("=")
            if not edge.strip() or not nation.strip():
                raise Refusal(f"LOGISTICS_SIM_RELEASABILITY_EDGE_DEFAULTS: bad "
                              f"pair {pair!r}")
            edge_defaults[edge.strip()] = nation.strip()
    else:
        edge_defaults = {str(k): str(v) for k, v in
                         (sim_cfg.get("releasability_edge_defaults") or {}).items()}
    site_nation = env.get("LOGISTICS_SIM_SITE_NATION",
                          str(sim_cfg.get("site_nation") or ""))
    sites = {str(s): str((row or {}).get("nation") or "") for s, row in
             (((sim_cfg.get("parts_availability") or {}).get("sites")) or {}).items()}
    return {"edge_defaults": edge_defaults,
            "document_default": rel_doc.get("default_originator_nation"),
            "site_nation": site_nation or "",
            "sites": sites}


# --------------------------------------------------------------------------
# Pure: translation (DESIGN §7.2)
# --------------------------------------------------------------------------

def _labels(nation: str) -> dict:
    return {"originator_nation": nation, "releasable_to": []}


def _site(scope_kind: str, scope_id: str, records: list, nation: str,
          replaces: str, door_edge: str | None) -> dict:
    return {"kind": "site",
            "scope": {"kind": scope_kind, "id": scope_id, "records": records},
            "labels": _labels(nation), "replaces": replaces,
            "door_edge": door_edge}


def translate(src: dict, vocabulary: list[str]) -> dict:
    """Every default in use -> the site declaration stating the same answer.

    src = {"edges": [...], "ingest": {edge: rules_json},
           "sim": sim_defaults(...) or None, "document": rel_doc or None}

    Returns {"declarations": [...], "for_person": [...], "owed": [...]}.
    Raises Refusal on anything the translation cannot state exactly.
    """
    vocab = set(vocabulary)
    decls, for_person, owed = [], [], []
    doc = src.get("document") or {}
    file_rows = doc.get("assets") or {}

    def check(nation, where):
        if nation not in vocab:
            raise Refusal(f"{where}: {nation!r} is outside the declared "
                          f"vocabulary {sorted(vocab)}")

    for edge in sorted(src.get("ingest") or {}):
        try:
            rules_doc = json.loads(src["ingest"][edge] or "{}")
        except ValueError as exc:
            raise Refusal(f"edge {edge}: DIS_NATION_RULES is not JSON: {exc}")
        for urn, nation in sorted((rules_doc.get("overrides") or {}).items()):
            if nation == "exempt":
                decls.append({"kind": "exemption", "asset_id": urn,
                              "replaces": f"ingest override {urn}=exempt at {edge}",
                              "door_edge": edge})
                continue
            check(nation, f"ingest override {urn} at {edge}")
            row = file_rows.get(urn) or {}
            row_nation = row.get("originator_nation")
            if row_nation and row_nation != nation:
                raise Refusal(f"ingest override {urn}={nation} at {edge}, but "
                              f"the file row says {row_nation}")
            for_person.append({"asset_id": urn, "originator_nation": nation,
                               "edge_id": edge,
                               "why": "a per-asset statement: declare it in "
                                      "Arrivals before the amend"})
        for i, rule in enumerate(rules_doc.get("rules") or []):
            nation = rule.get("nation")
            check(nation, f"ingest rule {rule.get('name', i)!r} at {edge}")
            decls.append({"kind": "rule",
                          "scope": {"kind": "edge", "id": edge,
                                    "records": ["entity"]},
                          "match": rule.get("match"),
                          "labels": _labels(nation),
                          "replaces": f"ingest rule {rule.get('name', i)!r} at {edge}",
                          "door_edge": edge})

    sim = src.get("sim")
    if sim:
        for edge in sorted(src.get("edges") or []):
            if edge in sim["edge_defaults"]:
                nation, what = sim["edge_defaults"][edge], "sim edge default"
            elif sim["document_default"]:
                nation, what = sim["document_default"], "sim document default"
            elif sim["site_nation"]:
                nation, what = sim["site_nation"], "sim site_nation"
            else:
                continue
            check(nation, f"{what} for {edge}")
            decls.append(_site("edge", edge, ["logistics"], nation,
                               f"{what} for {edge}", edge))
        for edge in sorted(set(sim["edge_defaults"]) - set(src.get("edges") or [])):
            owed.append({"what": f"sim edge default for {edge}",
                         "why": "no running workload names this edge; not "
                                "translated"})
        for site, nation in sorted(sim["sites"].items()):
            if not nation:
                continue
            check(nation, f"spares site {site}")
            decls.append(_site("logistics-site", site, ["spares"], nation,
                               f"spares nation for site {site}", None))

    if doc.get("default_originator_nation"):
        nation = doc["default_originator_nation"]
        check(nation, "mapper document default")
        for edge in sorted(src.get("edges") or []):
            decls.append(_site("edge", edge, ["entity"], nation,
                               f"mapper document default for {edge}", edge))

    for urn, row in sorted(file_rows.items()):
        row = row or {}
        if not (row.get("declared_by") and row.get("declared_at")):
            owed.append({"what": f"file row {urn}",
                         "why": "no declared_by/declared_at: a default under "
                                "ADR-0055 §1a; the bundle owner dates it"})

    return {"declarations": decls, "for_person": for_person, "owed": owed}


# --------------------------------------------------------------------------
# Pure: overlap (DESIGN §6.1, §7.2)
# --------------------------------------------------------------------------

def _lon_spans(west: float, east: float) -> list[tuple[float, float]]:
    return [(west, east)] if west <= east else [(west, 180.0), (-180.0, east)]


def boxes_overlap(a: dict, b: dict) -> bool:
    if a["south"] > b["north"] or b["south"] > a["north"]:
        return False
    return any(x0 <= y1 and y0 <= x1
               for x0, x1 in _lon_spans(a["west"], a["east"])
               for y0, y1 in _lon_spans(b["west"], b["east"]))


def matches_overlap(a: dict, b: dict) -> bool | None:
    """True / False when decidable, None when not. A marking regex, or two
    different match kinds, is not decidable from the declarations alone."""
    (ka, va), = a.items()
    (kb, vb), = b.items()
    if ka != kb or ka == "marking":
        return None
    if ka == "geofence":
        return boxes_overlap(va, vb)
    if ka == "country":
        return bool(set(va) & set(vb))
    return None


def _scope_key(d: dict) -> tuple:
    s = d.get("scope") or {}
    return (s.get("kind"), s.get("id"))


def find_conflicts(decls: list[dict]) -> list[dict]:
    """Pairs that could cover one record with different values. ADR-0055
    §1a has no first-match and no narrowest-scope rule, so each is a refusal:
    loaded, it would turn today's answer into no answer."""
    out = []
    covering = [d for d in decls if d["kind"] in ("site", "rule")]
    for i, a in enumerate(covering):
        for b in covering[i + 1:]:
            if _scope_key(a) != _scope_key(b):
                continue
            if not set(a["scope"]["records"]) & set(b["scope"]["records"]):
                continue
            if a["labels"] == b["labels"]:
                continue
            if a["kind"] == "rule" and b["kind"] == "rule":
                ov = matches_overlap(a["match"], b["match"])
            else:
                ov = True            # a site covers every record at its scope
            if ov is False:
                continue
            out.append({"a": a["replaces"], "b": b["replaces"],
                        "decided": ov is True})
    return out


# --------------------------------------------------------------------------
# Pure: census, hashes, prediction
# --------------------------------------------------------------------------

def census_rows(tsv: str) -> list[list]:
    """psql -tA -F '\\t' output of (asset_id, nation, releasable_to) with
    NULLs written as \\N -> sorted unique rows, None for NULL."""
    rows = set()
    for line in tsv.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            raise Refusal(f"census: malformed row {line!r}")
        rows.add(tuple(None if p == "\\N" else p for p in parts))
    return [list(r) for r in sorted(rows, key=lambda r: tuple("" if x is None else x for x in r))]


def census_diff(before: dict, after: dict) -> list[dict]:
    """{store: {table: rows}} x2 -> every row added or removed, and every
    store or table that appeared or vanished. Empty means equal."""
    diffs = []
    for store in sorted(set(before) | set(after)):
        if store not in after or store not in before:
            diffs.append({"store": store, "change": "store missing from "
                          + ("after" if store not in after else "before")})
            continue
        tb, ta = before[store], after[store]
        for table in sorted(set(tb) | set(ta)):
            rb = {tuple(r) for r in tb.get(table, [])}
            ra = {tuple(r) for r in ta.get(table, [])}
            if table not in ta or table not in tb:
                diffs.append({"store": store, "table": table,
                              "change": "table missing from "
                              + ("after" if table not in ta else "before")})
                continue
            for r in sorted(rb - ra, key=str):
                diffs.append({"store": store, "table": table,
                              "change": "removed", "row": list(r)})
            for r in sorted(ra - rb, key=str):
                diffs.append({"store": store, "table": table,
                              "change": "added", "row": list(r)})
    return diffs


def sha256_file(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(d: dict) -> str:
    """What makes two declarations the same statement: kind, scope, match,
    asset, labels. Not the owner, not the date, not the reason."""
    keep = {k: d.get(k) for k in ("kind", "scope", "match", "asset_id", "labels")}
    return json.dumps(keep, sort_keys=True, separators=(",", ":"))


def build_prediction(plan: dict, plan_sha: str, census_sha: str) -> dict:
    decls = plan["declarations"]
    by_door: dict[str, int] = {}
    for d in decls:
        if d.get("already_active"):
            continue
        by_door[d["door"]] = by_door.get(d["door"], 0) + 1
    return {
        "plan_sha256": plan_sha,
        "census_before_sha256": census_sha,
        "written_at": _now(),
        "load": {
            "declarations_to_post": sum(by_door.values()),
            "already_active": sum(1 for d in decls if d.get("already_active")),
            "by_door": by_door,
            "census": "equal to census-before.json, to the row",
            "label_exception_rows": 0,
            "label_source_default": 0,
        },
        "amend": {
            "census": "equal to census-before.json, to the row",
            "requires_declared_first": plan["for_person"],
            "if_not_declared": [
                f"{p['asset_id']} moves to unlabelled at {p['edge_id']}"
                for p in plan["for_person"]],
        },
        "owed": plan["owed"],
    }


def prediction_md(pred: dict) -> str:
    ld, am = pred["load"], pred["amend"]
    lines = [
        "# Prediction: site declarations, load before amend", "",
        f"- plan sha256: `{pred['plan_sha256']}`",
        f"- census-before sha256: `{pred['census_before_sha256']}`",
        f"- written: {pred['written_at']}", "",
        "## Load", "",
        f"- declarations to post: {ld['declarations_to_post']} "
        f"(already active, skipped: {ld['already_active']})",
    ]
    lines += [f"  - {door}: {n}" for door, n in sorted(ld["by_door"].items())]
    lines += [
        f"- census: {ld['census']}",
        f"- label_exception rows: {ld['label_exception_rows']}",
        f"- label_source=default on every evaluator: {ld['label_source_default']}",
        "", "## Amend (a person's change, not this script's)", "",
        f"- census: {am['census']}",
        f"- per-asset declarations a person makes first: "
        f"{len(am['requires_declared_first'])}",
    ]
    lines += [f"  - {x}" for x in am["if_not_declared"]] or []
    lines += ["", "## Owed by others", ""]
    lines += [f"- {o['what']}: {o['why']}" for o in pred["owed"]] or ["- none"]
    return "\n".join(lines) + "\n"


def first_line(path: pathlib.Path) -> str:
    """A credential file's first non-empty line, and nothing else."""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            return line.strip()
    raise Refusal(f"{path}: no non-empty line")


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------
# Cluster and HTTP (never run; see the module docstring)
# --------------------------------------------------------------------------

def run_guard(helm_dir: pathlib.Path) -> str:
    guard = helm_dir / "scripts" / "lib" / "require-cluster.sh"
    if not guard.is_file():
        raise Refusal(f"no cluster guard at {guard}")
    p = subprocess.run(["bash", "-c", '. "$1"', "_", str(guard)],
                       capture_output=True, text=True)
    sys.stderr.write(p.stderr)
    if p.returncode != 0:
        sys.exit(EXIT_GUARD if p.returncode == EXIT_GUARD else EXIT_REFUSED)
    m = re.search(r"^cluster: (\S+) \(asserted\)$", p.stdout, re.M)
    if not m:
        raise Refusal("the guard passed but printed no asserted context")
    return m.group(1)


class Kube:
    def __init__(self, context: str, namespace: str):
        self.base = ["kubectl", "--context", context, "-n", namespace]

    def _run(self, *args: str) -> str:
        p = subprocess.run(self.base + list(args), capture_output=True, text=True)
        if p.returncode != 0:
            raise Refusal(f"kubectl {' '.join(args[:3])}: {p.stderr.strip()}")
        return p.stdout

    def pods(self) -> dict:
        return json.loads(self._run("get", "pods", "-o", "json"))

    def cat(self, pod: str, container: str, path: str) -> str:
        return self._run("exec", pod, "-c", container, "--", "cat", path)

    def psql(self, pod: str, sql: str) -> str:
        return self._run("exec", pod, "--", "psql", "-U", "openddil", "-d",
                         "openddil", "-v", "ON_ERROR_STOP=1", "-tA", "-F", "\t",
                         "-c", sql)


STORE_RE = re.compile(r"-(tier-pg-.+-0|postgres-hq(-0)?)$")
CENSUS_TABLES = ("SELECT table_name FROM information_schema.columns "
                 "WHERE table_schema='public' AND column_name IN "
                 "('asset_id','originator_nation') "
                 "GROUP BY table_name HAVING count(DISTINCT column_name) = 2 "
                 "ORDER BY 1")


def stores(pods: dict) -> list[str]:
    return sorted(p["metadata"]["name"] for p in pods.get("items") or []
                  if STORE_RE.search(p["metadata"]["name"])
                  and (p.get("status") or {}).get("phase") == "Running")


def read_census(kube: Kube, store_pods: list[str]) -> dict:
    out = {}
    for pod in store_pods:
        tables = {}
        for t in filter(None, kube.psql(pod, CENSUS_TABLES).split()):
            has_rel = kube.psql(pod, "SELECT 1 FROM information_schema.columns "
                                f"WHERE table_schema='public' AND table_name='{t}' AND column_name="
                                "'releasable_to'").strip() == "1"
            rel = "coalesce(releasable_to::text, '\\N')" if has_rel else "'\\N'"
            tsv = kube.psql(pod, f"SELECT DISTINCT asset_id, coalesce("
                            f"originator_nation, '\\N'), {rel} FROM \"{t}\"")
            tables[t] = census_rows(tsv)
        out[pod] = tables
    return out


def require_increment(kube: Kube, store_pods: list[str]) -> None:
    missing = [p for p in store_pods if kube.psql(
        p, "SELECT to_regclass('public.site_declaration') IS NOT NULL").strip() != "t"]
    if missing:
        raise Refusal("increment not deployed: no site_declaration table at "
                      + ", ".join(missing))


class Pep:
    def __init__(self, url: str, session_file: pathlib.Path, ca: str | None):
        self.url = url.rstrip("/")
        self.cookie = first_line(session_file)
        self.ctx = ssl.create_default_context(cafile=ca) if ca else None

    def _req(self, method: str, body: dict | None = None) -> tuple[int, dict]:
        req = urllib.request.Request(
            self.url + "/declarations/site", method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={"Cookie": self.cookie, "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, context=self.ctx, timeout=30) as r:
                return r.status, json.loads(r.read() or b"{}")
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read() or b"{}")
            except ValueError:
                return e.code, {}

    def describe(self) -> dict:
        status, body = self._req("GET")
        if status == 404:
            raise Refusal(f"increment not deployed: {self.url}/declarations/site is 404")
        if status != 200:
            raise Refusal(f"{self.url}: GET /declarations/site answered {status}")
        return body

    def post(self, decl: dict) -> tuple[int, dict]:
        body = {k: decl[k] for k in ("kind", "scope", "match", "asset_id", "labels")
                if decl.get(k) is not None}
        body["reason"] = f"load before amend: replaces {decl['replaces']}"
        return self._req("POST", body)


def route(decls: list[dict], peps: dict[str, dict]) -> None:
    """Each declaration to the PEP whose tier serves its edge; a
    logistics-site declaration to the root tier's PEP. From the PEPs' own
    GET answers, so the plan never restates their configuration."""
    by_edge, roots = {}, []
    for url, desc in peps.items():
        if desc.get("root"):
            roots.append(url)
        for e in desc.get("edges") or []:
            if e in by_edge:
                raise Refusal(f"edge {e} is served by two PEPs: {by_edge[e]}, {url}")
            by_edge[e] = url
    for d in decls:
        if d["door_edge"] is None:
            if len(roots) != 1:
                raise Refusal(f"{d['replaces']}: needs exactly one root PEP, "
                              f"have {len(roots)}")
            d["door"] = roots[0]
        elif d["door_edge"] in by_edge:
            d["door"] = by_edge[d["door_edge"]]
        else:
            raise Refusal(f"{d['replaces']}: no PEP serves edge {d['door_edge']}")
        active = {canonical(x) for x in peps[d["door"]].get("declarations") or []
                  if x.get("status") == "active"}
        d["already_active"] = canonical(d) in active


# --------------------------------------------------------------------------
# Steps
# --------------------------------------------------------------------------

def _write(out: pathlib.Path, name: str, obj) -> pathlib.Path:
    path = out / name
    text = obj if isinstance(obj, str) else json.dumps(obj, indent=2, sort_keys=True) + "\n"
    path.write_text(text, encoding="utf-8")
    print(f"wrote {path}")
    return path


def _peps(args) -> dict[str, Pep]:
    if len(args.pep) != len(args.session):
        raise Refusal("each --pep needs its own --session")
    return {u.rstrip("/"): Pep(u, pathlib.Path(s), args.ca_file)
            for u, s in zip(args.pep, args.session)}


def step_plan(args) -> int:
    ctx = run_guard(pathlib.Path(args.helm_dir))
    kube = Kube(ctx, args.namespace)
    pods = kube.pods()
    found = sources_from_pods(pods)
    store_pods = stores(pods)
    if not store_pods:
        raise Refusal("no tier store pods found")
    require_increment(kube, store_pods)
    peps = {u: p.describe() for u, p in _peps(args).items()}

    rel_doc = {}
    if found["ontology_pods"]:
        texts = {kube.cat(p, c, "/ontology/releasability.yaml")
                 for p, c in found["ontology_pods"]}
        if len(texts) != 1:
            raise Refusal(f"/ontology/releasability.yaml differs across "
                          f"{len(texts)} pods; one deployment, one file")
        rel_doc = _yaml(texts.pop())
    sim = None
    if len(found["sim"]) > 1 and len({json.dumps(s["env"], sort_keys=True)
                                      for s in found["sim"]}) > 1:
        raise Refusal("two logistics sims with different env")
    if found["sim"]:
        s = found["sim"][0]
        cfg = _yaml(kube.cat(s["pod"], s["container"], s["env"]["LOGISTICS_SIM_CONFIG_PATH"]))
        sim_rel_path = s["env"].get("LOGISTICS_SIM_RELEASABILITY_PATH",
                                    cfg.get("releasability_path", "/ontology/releasability.yaml"))
        sim_rel = _yaml(kube.cat(s["pod"], s["container"], sim_rel_path))
        sim = sim_defaults(s["env"], cfg, sim_rel)

    src = {"edges": found["edges"], "ingest": found["ingest"],
           "sim": sim, "document": rel_doc}
    plan = translate(src, args.vocabulary.split(","))
    conflicts = find_conflicts(plan["declarations"])
    if conflicts:
        raise Refusal("translated declarations conflict; §1a has no first-match. "
                      "Restate them disjoint, or declare the assets per asset",
                      {"conflicts": conflicts})
    route(plan["declarations"], peps)
    census = read_census(kube, store_pods)
    out = pathlib.Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    _write(out, "census-before.json", census)
    plan.update({"context": ctx, "namespace": args.namespace, "read_at": _now(),
                 "sources": src, "stores": store_pods,
                 "vocabulary": args.vocabulary.split(",")})
    _write(out, "plan.json", plan)
    print(f"plan: {len(plan['declarations'])} declarations, "
          f"{len(plan['for_person'])} for a person, {len(plan['owed'])} owed. "
          "Next: predict, as its own step.")
    return EXIT_OK


def step_predict(args) -> int:
    out = pathlib.Path(args.out)
    plan_p, census_p = out / "plan.json", out / "census-before.json"
    for p in (plan_p, census_p):
        if not p.is_file():
            raise Refusal(f"no {p}; run plan first")
    plan = json.loads(plan_p.read_text(encoding="utf-8"))
    pred = build_prediction(plan, sha256_file(plan_p), sha256_file(census_p))
    _write(out, "prediction.json", pred)
    _write(out, "prediction.md", prediction_md(pred))
    print("Confirm prediction.json on disk before load.")
    return EXIT_OK


def check_prediction(out: pathlib.Path) -> tuple[dict, dict]:
    plan_p, pred_p = out / "plan.json", out / "prediction.json"
    if not pred_p.is_file():
        raise Refusal("no prediction.json: predict is a separate step, before load")
    pred = json.loads(pred_p.read_text(encoding="utf-8"))
    if pred.get("plan_sha256") != sha256_file(plan_p):
        raise Refusal("prediction.json was written for a different plan.json")
    if pred.get("census_before_sha256") != sha256_file(out / "census-before.json"):
        raise Refusal("prediction.json was written for a different census-before.json")
    return json.loads(plan_p.read_text(encoding="utf-8")), pred


def step_load(args) -> int:
    out = pathlib.Path(args.out)
    plan, _ = check_prediction(out)
    ctx = run_guard(pathlib.Path(args.helm_dir))
    if ctx != plan["context"] or args.namespace != plan["namespace"]:
        raise Refusal(f"plan was read at {plan['context']}/{plan['namespace']}, "
                      f"this run is at {ctx}/{args.namespace}")
    peps = _peps(args)
    log = {"started_at": _now(), "context": ctx, "loaded": [], "skipped": [],
           "refused": None, "not_attempted": []}
    todo = plan["declarations"]
    for i, d in enumerate(todo):
        if d.get("already_active"):
            log["skipped"].append(d["replaces"])
            continue
        if d["door"] not in peps:
            log["refused"] = {"replaces": d["replaces"], "status": None,
                              "reason": f"no --pep {d['door']} on this run"}
        else:
            status, body = peps[d["door"]].post(d)
            if 200 <= status < 300:
                log["loaded"].append({"replaces": d["replaces"],
                                      "declaration_id": body.get("declaration_id"),
                                      "decision_id": body.get("decision_id")})
                continue
            log["refused"] = {"replaces": d["replaces"], "status": status,
                              "reason": body.get("error"),
                              "decision_id": body.get("decision_id")}
        log["not_attempted"] = [x["replaces"] for x in todo[i + 1:]
                                if not x.get("already_active")]
        log["ended_at"] = _now()
        _write(out, "load-log.json", log)
        raise Refusal(f"load refused at {d['replaces']}", log)
    log["ended_at"] = _now()
    _write(out, "load-log.json", log)
    print(f"loaded {len(log['loaded'])}, skipped {len(log['skipped'])}. "
          "Next: verify. Reads hit postgres; allow for the projector.")
    return EXIT_OK


def read_metric(url: str, name: str) -> dict[str, float]:
    with urllib.request.urlopen(url, timeout=15) as r:
        text = r.read().decode()
    out = {}
    for m in re.finditer(rf'^{re.escape(name)}\{{source="([^"]+)"\}} (\S+)$', text, re.M):
        out[m.group(1)] = out.get(m.group(1), 0.0) + float(m.group(2))
    return out


def step_verify(args) -> int:
    out = pathlib.Path(args.out)
    plan, pred = check_prediction(out)
    ctx = run_guard(pathlib.Path(args.helm_dir))
    if ctx != plan["context"]:
        raise Refusal(f"plan was read at {plan['context']}, this run is at {ctx}")
    kube = Kube(ctx, args.namespace)
    store_pods = stores(kube.pods())
    before = json.loads((out / "census-before.json").read_text(encoding="utf-8"))
    after = read_census(kube, store_pods)
    report = {"at": _now(), "after_amend": args.after_amend,
              "census_diff": census_diff(before, after)}
    report["label_exception_rows"] = {
        p: int(kube.psql(p, "SELECT count(*) FROM label_exception").strip() or 0)
        for p in store_pods}
    ids = [p["asset_id"] for p in plan["for_person"]]
    declared = {}
    if ids:
        arr = ",".join("'" + i.replace("'", "''") + "'" for i in ids)
        for p in store_pods:
            for line in kube.psql(p, "SELECT asset_id, originator_nation FROM "
                                  f"asset_declaration WHERE asset_id IN ({arr})").splitlines():
                if line.strip():
                    a, n = line.split("\t")
                    declared[a] = n
    report["amend_ready"] = [
        {"asset_id": x["asset_id"], "want": x["originator_nation"],
         "declared": declared.get(x["asset_id"])} for x in plan["for_person"]]
    not_ready = [x for x in report["amend_ready"] if x["declared"] != x["want"]]
    defaults = {u: read_metric(u, "openddil_label_source_total").get("default", 0.0)
                for u in args.metrics_url}
    report["label_source_default"] = defaults
    _write(out, f"verify-{_now().replace(':', '')}.json", report)

    bad = bool(report["census_diff"]) or any(report["label_exception_rows"].values()) \
        or any(defaults.values()) or (args.after_amend and not_ready)
    if bad:
        print(f"verify: DIFFERS. census rows changed: {len(report['census_diff'])}, "
              f"exceptions: {sum(report['label_exception_rows'].values())}, "
              f"default-sourced: {sum(defaults.values())}, "
              f"undeclared overrides: {len(not_ready)}")
        return EXIT_DIFF
    if not args.metrics_url:
        print("verify: census equal; citations NOT read (no --metrics-url). "
              "This is not a pass.")
        return EXIT_UNCHECKED
    print(f"verify: equal. amend ready: {'yes' if not not_ready else 'no, ' + str(len(not_ready)) + ' overrides undeclared'}")
    return EXIT_OK


def _yaml(text: str) -> dict:
    import yaml  # only the cluster steps need it
    return yaml.safe_load(text) or {}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="step", required=True)
    for name in ("plan", "predict", "load", "verify"):
        sp = sub.add_parser(name)
        sp.add_argument("--out", required=True)
        if name == "predict":
            continue
        sp.add_argument("--helm-dir", required=True)
        sp.add_argument("-n", "--namespace", required=True)
        if name in ("plan", "load"):
            sp.add_argument("--pep", action="append", default=[])
            sp.add_argument("--session", action="append", default=[])
            sp.add_argument("--ca-file")
        if name == "plan":
            sp.add_argument("--vocabulary", required=True)
        if name == "verify":
            sp.add_argument("--after-amend", action="store_true")
            sp.add_argument("--metrics-url", action="append", default=[])
    args = ap.parse_args(argv)
    try:
        return {"plan": step_plan, "predict": step_predict,
                "load": step_load, "verify": step_verify}[args.step](args)
    except Refusal as r:
        print(f"REFUSED: {r.reason}", file=sys.stderr)
        if r.state:
            print(json.dumps(r.state, indent=2, sort_keys=True), file=sys.stderr)
        return EXIT_REFUSED


if __name__ == "__main__":
    sys.exit(main())
