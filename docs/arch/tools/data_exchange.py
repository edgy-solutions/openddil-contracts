#!/usr/bin/env python3
"""data_exchange.py - generate the data-exchange view from a helm render.

Reads `helm template` output (or a render file) and writes a markdown
document of who writes and who reads every broker topic, which record kinds
the egress gate carries, where they may go, and which labels are declared.
Everything comes from what the render declares: the
`openddil.io/produces-topics` and `openddil.io/consumer-groups` annotations,
the ConfigMaps the workloads mount, and the egress ConfigMaps. Nothing is
measured and nothing is inferred from a name; a declaration that is missing
is printed as an exception, never filled in.

Usage:
    python docs/arch/tools/data_exchange.py --chart PATH --values FILE
        [--values FILE ...] [--rendered FILE] [--profile uaf|dodaf202|naf4]
        [--out FILE] [--allow-no-kinds REASON] [--check] [--check-file FILE]

What --check validates, on the document text (Exchanges table read by
column position, so profile renames do not matter): at least one tier and
one exchange row; every tier of the universe appears in the Tier or Broker
column; every kind of the universe appears in the Kind column; every route
destination appears in a row; kinds exist or --allow-no-kinds says why not
(and not both); no kind is named without a schema.

Exit codes: 0 ok, 1 check failed, 2 bad input (helm failed, no documents,
zero tiers). Secrets are dropped at parse time. Egress fields other than the
destination registry's display fields are never read into the output.
Stdlib and PyYAML only.
"""
from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

import yaml

EXIT_OK, EXIT_CHECK, EXIT_INPUT = 0, 1, 2
RELEASE_PREFIX = "openddil-"
WORKLOAD_KINDS = {"Deployment", "StatefulSet", "DaemonSet", "Job", "CronJob"}
PRODUCES = "openddil.io/produces-topics"
GROUPS = "openddil.io/consumer-groups"
NONE_DECLARED = "none declared"
NOT_DECLARED = "not declared"
STAMP_NOT_MEASURED = ("Declared, not measured: this table reads a render; "
                      "nothing here was observed running.")
PROFILES_PATH = Path(__file__).resolve().parent.parent / "profiles.yaml"
LOADER = getattr(yaml, "CSafeLoader", yaml.SafeLoader)

MEANINGS = {
    "consumer-without-writer": "A consumer is bound to this topic; no workload declares writing it.",
    "destination-without-entry": "A route names a destination the registry in this bundle does not list.",
    "group-without-topic": "A consumer group is declared; no mounted config or env binds it to a topic. No topic is inferred.",
    "kind-without-schema": "A kind is named; no schema for it is declared in the kinds ConfigMap.",
    "labels-not-declared": "No kind label and no labelled table is declared for this topic. Absence is not defaulted.",
    "releasability-disabled": "Declared labels are not enforced by this bundle (releasability.enabled is false).",
    "releasability-unknown": "releasability.enabled is not known: no chart values or values file set it.",
    "workload-no-declaration": "Information: a Deployment or StatefulSet declares neither annotation.",
    "writer-not-annotated": "The writer is known from config; no produces-topics annotation names it.",
    "writer-without-consumer": "A workload declares writing this topic; no consumer is bound to it.",
}


class InputError(Exception):
    """Bad input: exit 2."""


# --- parse ------------------------------------------------------------------

def load_docs(text: str) -> list[dict]:
    docs = []
    for doc in yaml.load_all(text, Loader=LOADER):
        if not isinstance(doc, dict):
            continue
        if doc.get("kind") == "Secret":
            continue  # drop at once; nothing is read from a Secret
        docs.append(doc)
    return docs


def strip_prefix(name: str) -> str:
    return name[len(RELEASE_PREFIX):] if name.startswith(RELEASE_PREFIX) else name


def split_pairs(value) -> list[tuple[str, str]]:
    out = []
    for entry in str(value or "").split():
        if "/" in entry:
            broker, name = entry.split("/", 1)
            out.append((broker, name))
    return out


class Workload:
    def __init__(self, doc: dict):
        self.kind = doc["kind"]
        meta = doc.get("metadata") or {}
        self.name = strip_prefix(str(meta.get("name", "")))
        spec = doc.get("spec") or {}
        if self.kind == "CronJob":
            tmpl = ((spec.get("jobTemplate") or {}).get("spec") or {}).get("template") or {}
        else:
            tmpl = spec.get("template") or {}
        ann = {}
        ann.update(meta.get("annotations") or {})
        ann.update((tmpl.get("metadata") or {}).get("annotations") or {})
        self.has_declaration = PRODUCES in ann or GROUPS in ann
        self.produces = split_pairs(ann.get(PRODUCES))
        self.groups = split_pairs(ann.get(GROUPS))
        pod = tmpl.get("spec") or {}
        self.cms: list[str] = []
        for vol in pod.get("volumes") or []:
            if (vol.get("configMap") or {}).get("name"):
                self.cms.append(strip_prefix(vol["configMap"]["name"]))
            for src in (vol.get("projected") or {}).get("sources") or []:
                if (src.get("configMap") or {}).get("name"):
                    self.cms.append(strip_prefix(src["configMap"]["name"]))
        self.env: list[tuple[str, str]] = []
        for c in (pod.get("containers") or []) + (pod.get("initContainers") or []):
            for e in c.get("env") or []:
                if isinstance(e.get("value"), str):
                    self.env.append((e["name"], e["value"]))


def tier_of(name: str, tiers: set[str]) -> str:
    best = ""
    for t in tiers:
        if t != "hq" and name.endswith("-" + t) and len(t) > len(best):
            best = t
    return best or "hq"


def walk(obj):
    """Yield every dict inside a parsed YAML/JSON value."""
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from walk(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from walk(v)


def as_list(v) -> list[str]:
    if isinstance(v, str):
        return [v]
    if isinstance(v, list):
        return [x for x in v if isinstance(x, str)]
    return []


def broker_of_address(addr: str) -> str | None:
    m = re.match(r"^redpanda-(.+?)(?:\.[^:/]*)?(?::\d+)?$", strip_prefix(addr))
    return m.group(1) if m else None


# --- values -----------------------------------------------------------------

def dig(d, path: list[str]):
    for p in path:
        if not isinstance(d, dict) or p not in d:
            return None, False
        d = d[p]
    return d, True


def merged_value(layers: list[dict], path: list[str]):
    """Last layer that sets the path wins; returns (value, found)."""
    val, found = None, False
    for layer in layers:
        v, ok = dig(layer, path)
        if ok:
            val, found = v, True
    return val, found


def load_yaml_file(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        data = yaml.load(f, Loader=LOADER)
    return data if isinstance(data, dict) else {}


# --- model ------------------------------------------------------------------

class Model:
    def __init__(self):
        self.tiers: list[str] = []
        self.brokers: dict[str, str] = {}
        self.rows: list[dict] = []
        self.kinds: dict[str, dict | None] = {}
        self.kind_universe: list[str] = []
        self.routes: list[dict] = []
        self.destinations: dict[str, dict | None] = {}
        self.exceptions: dict[str, list[str]] = defaultdict(list)
        self.label_tables: list[str] = []


def build_model(docs: list[dict], value_layers: list[dict], chart_layer: dict,
                has_values: bool) -> Model:
    m = Model()
    workloads = [Workload(d) for d in docs if d.get("kind") in WORKLOAD_KINDS]
    cms: dict[str, dict] = {}
    for d in docs:
        if d.get("kind") == "ConfigMap":
            cms[strip_prefix(str((d.get("metadata") or {}).get("name", "")))] = d.get("data") or {}
    parsed_cache: dict[tuple[str, str], object] = {}

    def parsed(cm: str, key: str):
        k = (cm, key)
        if k not in parsed_cache:
            raw = (cms.get(cm) or {}).get(key)
            try:
                parsed_cache[k] = yaml.load(raw, Loader=LOADER) if isinstance(raw, str) else None
            except yaml.YAMLError:
                parsed_cache[k] = None
        return parsed_cache[k]

    layers = ([chart_layer] if chart_layer else []) + value_layers

    # tier universe
    tier_ids: set[str] = set()
    for key in ("edges", "regions"):
        v, ok = merged_value(value_layers, [key])
        if ok and isinstance(v, list):
            tier_ids.update(str(e["id"]) for e in v if isinstance(e, dict) and "id" in e)
    for w in workloads:
        if w.kind == "StatefulSet" and w.name.startswith("redpanda-"):
            tier_ids.add(w.name[len("redpanda-"):])
            m.brokers[w.name[len("redpanda-"):]] = w.name[len("redpanda-"):]
    if any(b == "hq" for w in workloads for b, _ in w.produces + w.groups):
        tier_ids.add("hq")
    m.tiers = sorted(tier_ids)
    if not m.tiers:
        raise InputError("zero tiers in the render and values")
    tset = set(m.tiers)

    # labels
    tables, _ = merged_value(layers, ["releasability", "labeledTables"])
    m.label_tables = sorted(str(t) for t in tables) if isinstance(tables, list) else []
    enabled, enabled_known = merged_value(layers, ["releasability", "enabled"])
    if enabled_known and not enabled:
        m.exceptions["releasability-disabled"].append("releasability.enabled=false")
    elif not enabled_known:
        m.exceptions["releasability-unknown"].append("not set in any input")

    # kinds
    kinds_cm = cms.get("egress-kinds") or {}
    schemas: dict[str, dict] = {}
    for key, raw in kinds_cm.items():
        if key.endswith(".schema.json"):
            try:
                s = yaml.load(raw, Loader=LOADER)
            except yaml.YAMLError:
                s = None
            schemas[key[: -len(".schema.json")]] = s if isinstance(s, dict) else {}
    routes = [r for r in (parsed("egress-routes", "routes.json") or []) if isinstance(r, dict)]
    assembler = [e for e in (parsed("egress-assembler-config", "config.json") or []) if isinstance(e, dict)]
    intake = [e for e in (parsed("egress-intake-config", "config.json") or []) if isinstance(e, dict)]
    dest_doc = parsed("destinations-deployment", "data.yaml")
    entries = dest_doc.get("entries") if isinstance(dest_doc, dict) else None
    dests: dict[str, dict] = {}
    if isinstance(entries, dict):
        dests = {str(k): v for k, v in entries.items() if isinstance(v, dict)}
    elif isinstance(entries, list):
        for e in entries:
            if isinstance(e, dict) and (e.get("name") or e.get("id")):
                dests[str(e.get("name") or e.get("id"))] = e
    named: set[str] = set(schemas)
    for r in routes + assembler + intake:
        if isinstance(r.get("kind"), str):
            named.add(r["kind"])
    for e in dests.values():
        named.update(as_list(e.get("accepts")))
    m.kind_universe = sorted(named)
    for k in m.kind_universe:
        if k in schemas:
            decl = schemas[k].get("x-openddil") if isinstance(schemas[k].get("x-openddil"), dict) else {}
            m.kinds[k] = {p: decl.get(p) for p in ("key", "label", "owning_tier")}
        else:
            m.kinds[k] = None
            m.exceptions["kind-without-schema"].append(k)
    for r in routes:
        m.routes.append({f: r.get(f) for f in ("name", "source_topic", "destination", "sink_topic", "kind")})
    for name in sorted(dests):
        e = dests[name]
        m.destinations[name] = {f: e.get(f) for f in ("display_name", "nations", "accepts", "asserted_by", "asserted_on")}
    for r in m.routes:
        if r["destination"] and r["destination"] not in dests and r["destination"] not in m.destinations:
            m.destinations[r["destination"]] = None
            m.exceptions["destination-without-entry"].append(str(r["destination"]))

    # writers
    writers: dict[tuple[str, str], dict[str, tuple[str, str]]] = defaultdict(dict)
    for w in workloads:
        for b, t in w.produces:
            writers[(b, t)][w.name] = (tier_of(w.name, tset), "annotation")
    for cm_name in sorted(cms):
        data = cms[cm_name]
        if "connect.yaml" not in data:
            continue
        conn = parsed(cm_name, "connect.yaml")
        if not isinstance(conn, dict):
            continue
        inp = ((conn.get("input") or {}).get("kafka") or {})
        out = ((conn.get("output") or {}).get("kafka") or {})
        out_broker = next((b for b in map(broker_of_address, as_list(out.get("addresses"))) if b), None)
        otopic = out.get("topic")
        if not out_broker or not isinstance(otopic, str):
            continue
        topics = as_list(inp.get("topics")) if "kafka_topic" in otopic else [otopic]
        for w in workloads:
            if cm_name not in w.cms:
                continue
            for t in topics:
                if w.name not in writers[(out_broker, t)]:
                    writers[(out_broker, t)][w.name] = (tier_of(w.name, tset), "connect.yaml")
                    m.exceptions["writer-not-annotated"].append(f"{out_broker}/{t} ({w.name})")

    # consumers
    consumers: dict[tuple[str, str], set[str]] = defaultdict(set)
    topic_tables: dict[str, set[str]] = defaultdict(set)
    for w in workloads:
        for cm in w.cms:
            for key in (cms.get(cm) or {}):
                for d in walk(parsed(cm, key)):
                    if isinstance(d.get("topic"), str) and isinstance(d.get("table"), str):
                        topic_tables[d["topic"]].add(d["table"])
    for w in workloads:
        for broker, group in w.groups:
            topics = set()
            for cm in w.cms:
                for key in (cms.get(cm) or {}):
                    for d in walk(parsed(cm, key)):
                        if d.get("consumer_group") == group:
                            topics.update(as_list(d.get("topics")) + as_list(d.get("topic")))
            if not topics:
                for name, val in w.env:
                    if name.endswith("_INPUT_TOPIC") or name.endswith("_INPUT_TOPICS") or name == "BRIDGE_TOPICS":
                        topics.update(s.strip() for s in val.split(",") if s.strip())
            if not topics and w.name.startswith("egress-gate"):
                for cm in w.cms:
                    for r in parsed(cm, "routes.json") or []:
                        if isinstance(r, dict) and isinstance(r.get("source_topic"), str):
                            topics.add(r["source_topic"])
            if not topics and w.name == "egress-forwarder":
                for cm in w.cms:
                    for r in parsed(cm, "config.json") or []:
                        if isinstance(r, dict) and isinstance(r.get("sink_topic"), str):
                            topics.add(r["sink_topic"])
            if not topics and w.name == "egress-assembler":
                for cm in w.cms:
                    for r in parsed(cm, "config.json") or []:
                        if isinstance(r, dict) and isinstance(r.get("trigger_topic"), str):
                            topics.add(r["trigger_topic"])
            if not topics:
                m.exceptions["group-without-topic"].append(f"{broker}/{group} ({w.name})")
            for t in topics:
                consumers[(broker, t)].add(w.name)

    # topics implied by egress config, added when nothing annotated writes them
    implied: list[tuple[str, str]] = []
    topic_kinds: dict[str, set[str]] = defaultdict(set)
    topic_dests: dict[str, set[str]] = defaultdict(set)
    for r in m.routes:
        for f, writer in (("sink_topic", "egress-gate-c2"), ("source_topic", None)):
            t = r.get(f)
            if not isinstance(t, str):
                continue
            if r.get("destination"):
                topic_dests[t].add(str(r["destination"]))
            if r.get("kind"):
                topic_kinds[t].add(str(r["kind"]))
            if writer and (r.get("kind") or f == "sink_topic"):
                implied.append((t, writer))
    for e in assembler:
        if isinstance(e.get("output_topic"), str):
            implied.append((e["output_topic"], "egress-assembler"))
            if isinstance(e.get("kind"), str):
                topic_kinds[e["output_topic"]].add(e["kind"])
    for e in intake:
        if isinstance(e.get("onward_topic"), str):
            implied.append((e["onward_topic"], "egress-intake"))
            if isinstance(e.get("kind"), str):
                topic_kinds[e["onward_topic"]].add(e["kind"])
    for t, writer in sorted(set(implied)):
        if not writers.get(("hq", t)):
            writers[("hq", t)][writer] = (tier_of(writer, tset), "egress config")
            m.exceptions["writer-not-annotated"].append(f"hq/{t} ({writer})")

    # rows
    keys = sorted(set(writers) | set(consumers))
    for (broker, topic) in keys:
        cons = sorted(consumers.get((broker, topic), ()))
        ws = writers.get((broker, topic)) or {}
        kinds = sorted(topic_kinds.get(topic, ())) if broker == "hq" else []
        dst = sorted(topic_dests.get(topic, ())) if broker == "hq" else []
        label = label_for(m, kinds, topic, topic_tables)
        if ws:
            for wname in sorted(ws):
                tier, by = ws[wname]
                m.rows.append(row(tier, broker, topic, wname, by, cons, kinds, dst, label))
                if not cons:
                    m.exceptions["writer-without-consumer"].append(f"{broker}/{topic} ({wname})")
        else:
            by_tier: dict[str, list[str]] = defaultdict(list)
            for c in cons:
                by_tier[tier_of(c, tset)].append(c)
            for tier in sorted(by_tier):
                m.rows.append(row(tier, broker, topic, NONE_DECLARED, "-", by_tier[tier], kinds, dst, label))
                for c in by_tier[tier]:
                    m.exceptions["consumer-without-writer"].append(f"{broker}/{topic} ({c})")
    n_nolabel = sum(1 for r in m.rows if r["labels"] == NOT_DECLARED)
    if n_nolabel:
        m.exceptions["labels-not-declared"].append(f"{n_nolabel} rows")
    for w in workloads:
        if w.kind in ("Deployment", "StatefulSet") and w.name and not w.has_declaration:
            m.exceptions["workload-no-declaration"].append(w.name)
    m.rows.sort(key=lambda r: (r["tier"], r["broker"], r["topic"], r["writer"]))
    return m


def row(tier, broker, topic, writer, by, cons, kinds, dst, labels) -> dict:
    return {"tier": tier, "broker": broker, "topic": topic, "writer": writer, "by": by,
            "consumers": cons, "kinds": kinds, "destinations": dst, "labels": labels}


def label_for(m: Model, kinds: list[str], topic: str, topic_tables: dict[str, set[str]]) -> str:
    ptrs = [f"kind label {m.kinds[k]['label']}" for k in kinds
            if m.kinds.get(k) and m.kinds[k].get("label")]
    if ptrs:
        return "; ".join(ptrs)
    labelled = sorted(t for t in topic_tables.get(topic, ()) if t in m.label_tables)
    if labelled:
        return "; ".join(f"table {t}" for t in labelled)
    return NOT_DECLARED


# --- document ---------------------------------------------------------------

def cell(v) -> str:
    s = str(v) if v not in (None, "") else "-"
    return s.replace("|", "\\|").replace("\n", " ")


def table(header: list[str], rows: list[list]) -> list[str]:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(cell(c) for c in r) + " |" for r in rows]
    return out


def load_profiles() -> dict:
    with open(PROFILES_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def render_document(m: Model, profile: str, stamps: list[str], allow_no_kinds: str | None) -> str:
    prof = load_profiles()
    dx = prof["data_exchange"]
    ident, title = dx[profile]["id"], dx[profile]["title"]
    cols = dx["columns"][profile]
    lines = [f"# {ident} {title} ({prof['profiles'][profile]['label']})", ""]
    lines += [s for s in stamps] + [STAMP_NOT_MEASURED, ""]
    for d in prof.get("deviations") or []:
        if d.get("profile") == profile and d.get("export") == ident:
            lines += [f"Naming set in profiles.yaml; UAF 1.2 Appendix A names {d['appendix_a_home']} for "
                      f"{d['export']}. Decision open.", ""]
    lines += ["## Tiers", ""]
    lines += table(["Tier", "Broker", "Exchange rows"], [
        [t, m.brokers.get(t, "none rendered"),
         sum(1 for r in m.rows if r["tier"] == t or r["broker"] == t)] for t in m.tiers])
    lines += ["", "## Kinds", ""]
    if not m.kind_universe:
        lines.append("None declared by this bundle.")
        if allow_no_kinds:
            lines.append(f"Reason given: {allow_no_kinds}")
    else:
        krows = []
        for k in m.kind_universe:
            d = m.kinds[k] or {}
            dst = sorted({str(r["destination"]) for r in m.routes if r["kind"] == k and r["destination"]}
                         | {n for n, e in m.destinations.items() if e and k in as_list(e.get("accepts"))})
            krows.append([k, d.get("key") or NOT_DECLARED, d.get("label") or NOT_DECLARED,
                          d.get("owning_tier") or NOT_DECLARED,
                          sum(1 for r in m.rows if k in r["kinds"]), ", ".join(dst) or "-"])
        lines += table(["Kind", "Key", "Label", "Owning tier", "Exchange rows", "Destinations"], krows)
    lines += ["", "## Destinations", ""]
    drows = []
    for n in sorted(m.destinations):
        e = m.destinations[n]
        rn = ", ".join(sorted(str(r["name"]) for r in m.routes if r["destination"] == n)) or "-"
        if e is None:
            drows.append([n, "none in this bundle", "-", "-", "-", "-", rn])
        else:
            drows.append([n, e["display_name"], ", ".join(as_list(e["nations"])),
                          ", ".join(as_list(e["accepts"])), e["asserted_by"], e["asserted_on"], rn])
    lines += table(["Destination", "Display name", "Nations", "Accepts", "Asserted by", "Asserted on", "Routes"], drows)
    lines += ["", "## Exchanges", ""]
    lines += table(["Tier", "Broker", cols["topic"], cols["writer"], "Declared by", cols["consumers"],
                    "Kind", "Destination", "Labels"],
                   [[r["tier"], r["broker"], r["topic"], r["writer"], r["by"],
                     ", ".join(r["consumers"]) or NONE_DECLARED, ", ".join(r["kinds"]) or "-",
                     ", ".join(r["destinations"]) or "-", r["labels"]] for r in m.rows])
    lines += ["", "## Exceptions", ""]
    erows = []
    for name in sorted(m.exceptions):
        items = sorted(set(m.exceptions[name]))
        erows.append([name, len(items) if name != "labels-not-declared" else
                      int(items[0].split()[0]), "; ".join(items), MEANINGS.get(name, "")])
    lines += table(["Exception", "Count", "Items", "Meaning"], erows) if erows else ["None."]
    return "\n".join(lines) + "\n"


# --- check ------------------------------------------------------------------

def table_after(text: str, heading: str) -> list[list[str]]:
    """Cells of the table under `## heading`, header excluded, by position."""
    out, inside, seen_sep = [], False, False
    for line in text.splitlines():
        if line.startswith("## "):
            inside = line[3:].strip() == heading
            seen_sep = False
            continue
        if inside and line.startswith("|"):
            if not seen_sep:
                seen_sep = line.startswith("|---")
                continue
            out.append([c.strip().replace("\\|", "|")
                        for c in re.split(r"(?<!\\)\|", line.strip())[1:-1]])
    return out


def check_document(text: str, m: Model, allow_no_kinds: str | None) -> list[str]:
    fails = []
    tier_rows = table_after(text, "Tiers")
    if not m.tiers or not tier_rows:
        fails.append("zero tiers")
    ex = table_after(text, "Exchanges")
    if not ex:
        fails.append("zero exchange rows")
    seen_tiers = {r[0] for r in ex if len(r) > 1} | {r[1] for r in ex if len(r) > 1}
    for t in m.tiers:
        if t not in seen_tiers:
            fails.append(f"tier {t} is in neither the Tier nor the Broker column")
    seen_kinds = {k.strip() for r in ex if len(r) > 6 for k in r[6].split(",")}
    for k in m.kind_universe:
        if k not in seen_kinds:
            fails.append(f"kind {k} is not in the Kind column")
        if m.kinds.get(k) is None:
            fails.append(f"kind {k} is named without a schema")
    seen_dests = {d.strip() for r in ex if len(r) > 7 for d in r[7].split(",")}
    for r in m.routes:
        if r["destination"] and str(r["destination"]) not in seen_dests:
            fails.append(f"route {r['name']}: no row carries destination {r['destination']}")
    if not m.kind_universe and not allow_no_kinds:
        fails.append("no kinds declared and --allow-no-kinds not given")
    if m.kind_universe and allow_no_kinds:
        fails.append("--allow-no-kinds given but kinds exist (stale exception)")
    return fails


# --- main -------------------------------------------------------------------

def helm_render(chart: str, values: list[str]) -> str:
    cmd = ["helm", "template", "openddil", chart, "-n", "openddil"]
    for v in values:
        cmd += ["-f", v]
    env = dict(os.environ, KUBECONFIG="/nonexistent")
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, env=env)
    except FileNotFoundError:
        raise InputError("helm not found")
    if p.returncode != 0:
        raise InputError("helm template failed: " + "\n".join(p.stderr.strip().splitlines()[-8:]))
    return p.stdout


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Generate the data-exchange view from a helm render.")
    ap.add_argument("--chart")
    ap.add_argument("--values", action="append", default=[])
    ap.add_argument("--rendered")
    ap.add_argument("--profile", default="uaf", choices=["uaf", "dodaf202", "naf4"])
    ap.add_argument("--out")
    ap.add_argument("--allow-no-kinds", metavar="REASON")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--check-file")
    a = ap.parse_args(argv)
    try:
        if a.rendered:
            text = Path(a.rendered).read_text(encoding="utf-8")
        elif a.chart:
            text = helm_render(a.chart, a.values)
        else:
            raise InputError("need --chart or --rendered")
        docs = load_docs(text)
        del text  # never kept, never written
        if not docs:
            raise InputError("no documents in the render")
        layers = [load_yaml_file(v) for v in a.values]
        chart_layer, stamps = {}, []
        if a.chart:
            cdir = Path(a.chart)
            if (cdir / "values.yaml").is_file():
                chart_layer = load_yaml_file(str(cdir / "values.yaml"))
            if (cdir / "Chart.yaml").is_file():
                c = load_yaml_file(str(cdir / "Chart.yaml"))
                stamps.append(f"Chart: {c.get('name')} {c.get('version')}")
        stamps += [f"Values: {os.path.basename(v)}" for v in a.values]
        model = build_model(docs, layers, chart_layer, bool(a.values))
    except InputError as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_INPUT
    doc = render_document(model, a.profile, stamps, a.allow_no_kinds)
    if a.out:
        Path(a.out).write_text(doc, encoding="utf-8", newline="\n")
    else:
        sys.stdout.flush()
        sys.stdout.buffer.write(doc.encode("utf-8"))
        sys.stdout.buffer.flush()
    if a.check or a.check_file:
        target = Path(a.check_file).read_text(encoding="utf-8") if a.check_file else doc
        fails = check_document(target, model, a.allow_no_kinds)
        for f in fails:
            print(f"FAIL: {f}", file=sys.stderr)
        if fails:
            return EXIT_CHECK
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
