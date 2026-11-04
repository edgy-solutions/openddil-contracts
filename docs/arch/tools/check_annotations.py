#!/usr/bin/env python3
"""check_annotations.py - check the topic and consumer-group annotations of a render.

Reads `helm template` output (or a render file) and checks the two
annotations `openddil.io/produces-topics` and `openddil.io/consumer-groups`
that data_exchange.py reads. It does not go in check_views.py because it
needs a render.

Usage:
    python docs/arch/tools/check_annotations.py --chart PATH --release NAME --values FILE
        [--values FILE ...] [--exceptions FILE]
    python docs/arch/tools/check_annotations.py --rendered FILE [--release NAME] [--exceptions FILE]
    python docs/arch/tools/check_annotations.py ... --print-rows

Rules, against the render:
  grammar    every token is <broker-id>/<name>, with no repeats in one annotation
  placement  neither annotation sits in a pod template
  broker     a token's broker-id is a broker the render has
  owner      one (broker, group) is declared by one workload only
  ledger     the rows of writer-not-annotated, workload-no-declaration and
             group-without-topic equal the ledger, class by class

--exceptions defaults to docs/arch/annotation-exceptions.yaml. --print-rows
prints the current rows of the three ledger classes as YAML and exits 0.

Exit codes: 0 ok, 1 a rule failed, 2 could not evaluate (helm failed, no
documents, unreadable ledger). Stdlib and PyYAML only.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))
from data_exchange import (EXIT_CHECK, EXIT_INPUT, EXIT_OK, GROUPS, PRODUCES,  # noqa: E402
                           WORKLOAD_KINDS, InputError, Workload, build_model,
                           helm_render, load_docs, load_yaml_file, resolve_release,
                           split_pairs)

DEFAULT_EXCEPTIONS = Path(__file__).resolve().parent.parent / "annotation-exceptions.yaml"
ANNOTATIONS = (PRODUCES, GROUPS)
BROKER_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")
TOPIC_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")

REASONS = {
    "writer-not-annotated": (
        "A bridge writes these to its parent broker. Its annotation lists only the topics "
        "it originates, so the write is inferred from the bridge's config. ADR-0054 "
        "decision 5 lists them, and is not built."),
    "workload-no-declaration": (
        "These workloads render with neither annotation. They touch no broker topic, or "
        "their use of one is not yet declared. ADR-0054 keeps them as named "
        "exceptions."),
    "group-without-topic": (
        "The annotation names the consumer group and not its topics, so the generator "
        "cannot bind this group to a topic from the render. ADR-0054 decision 6 adds "
        "the topics, and is not built."),
}
LEDGER_CLASSES = tuple(REASONS)
LEDGER_HEADER = (
    "# Rows the annotation check does not cover, named with a reason. Generated rows are from\n"
    "# the public twin render: `python docs/arch/tools/check_annotations.py --print-rows ...`.\n"
    "# A new row or a stale row fails the check.\n")


def pod_template(doc: dict) -> dict:
    spec = doc.get("spec") or {}
    if doc.get("kind") == "CronJob":
        return ((spec.get("jobTemplate") or {}).get("spec") or {}).get("template") or {}
    return spec.get("template") or {}


def check_tokens(wname: str, ann: str, value, where: str) -> list[str]:
    fails, seen = [], set()
    for tok in str(value or "").split():
        parts = tok.split("/")
        if len(parts) != 2 or not BROKER_ID.match(parts[0]) or not TOPIC_NAME.match(parts[1]):
            fails.append(f"FAIL: grammar: {wname} {ann}{where}: token {tok!r} is not <broker-id>/<name>")
        if tok in seen:
            fails.append(f"FAIL: grammar: {wname} {ann}{where}: token {tok!r} is repeated")
        seen.add(tok)
    return fails


def check_render(docs: list[dict], release: str, model, ledger) -> list[str]:
    """Return FAIL lines for rules 1-5."""
    grammar, placement, broker, owner = [], [], [], []
    declared: dict[tuple[str, str], list[str]] = {}
    for doc in docs:
        if doc.get("kind") not in WORKLOAD_KINDS:
            continue
        w = Workload(doc, release)
        own = (doc.get("metadata") or {}).get("annotations") or {}
        tmpl = (pod_template(doc).get("metadata") or {}).get("annotations") or {}
        for ann in ANNOTATIONS:
            if ann in own:
                grammar += check_tokens(w.name, ann, own[ann], "")
            if ann in tmpl:
                placement.append(f"FAIL: placement: {w.name} carries {ann} in its pod template; "
                                 "put it on the workload's own metadata")
                grammar += check_tokens(w.name, ann, tmpl[ann], " (pod template)")
        for ann in ANNOTATIONS:
            for src in (own, tmpl):
                for b, _ in split_pairs(src.get(ann)):
                    if b not in model.brokers:
                        broker.append(f"FAIL: broker: {w.name} {ann} names broker {b!r}; "
                                      f"the render has {sorted(model.brokers)}")
        for b, g in sorted(set(w.groups)):
            declared.setdefault((b, g), []).append(w.name)
    for (b, g), names in sorted(declared.items()):
        if len(names) > 1:
            owner.append(f"FAIL: owner: group {b}/{g} is declared by {' and '.join(sorted(names))}")
    return grammar + placement + broker + owner + check_ledger(model, ledger)


def check_ledger(model, ledger) -> list[str]:
    fails = []
    if not isinstance(ledger, dict):
        return ["FAIL: ledger: the ledger is not a mapping of class to {reason, rows}"]
    for extra in sorted(set(map(str, ledger)) - set(LEDGER_CLASSES)):
        fails.append(f"FAIL: ledger: unknown class {extra!r} in the ledger")
    for cls in LEDGER_CLASSES:
        entry = ledger.get(cls)
        if entry is None:
            fails.append(f"FAIL: ledger: class {cls} is missing from the ledger")
            continue
        if not isinstance(entry, dict):
            fails.append(f"FAIL: ledger: class {cls} is not a {{reason, rows}} mapping")
            continue
        reason = entry.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            fails.append(f"FAIL: ledger: class {cls} has an empty reason")
        rows = entry.get("rows")
        if rows is None:
            rows = []
        if not isinstance(rows, list) or not all(isinstance(r, str) for r in rows):
            fails.append(f"FAIL: ledger: class {cls} rows is not a list of strings")
            continue
        have = set(model.exceptions.get(cls, []))
        for r in sorted(have - set(rows)):
            fails.append(f"FAIL: ledger: new {cls} row not in the ledger: {r}")
        for r in sorted(set(rows) - have):
            fails.append(f"FAIL: ledger: stale {cls} row not in the render: {r}")
    return fails


def current_rows(model) -> dict:
    return {cls: {"reason": REASONS[cls], "rows": sorted(set(model.exceptions.get(cls, [])))}
            for cls in LEDGER_CLASSES}


def load_ledger(path: Path):
    try:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f)
    except (OSError, yaml.YAMLError) as e:
        raise InputError(f"cannot read the ledger {path}: {e}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Check the topic and consumer-group annotations of a render.")
    ap.add_argument("--chart")
    ap.add_argument("--values", action="append", default=[])
    ap.add_argument("--rendered")
    ap.add_argument("--release", help="the Helm release name the render was made under")
    ap.add_argument("--exceptions", default=str(DEFAULT_EXCEPTIONS))
    ap.add_argument("--print-rows", action="store_true")
    a = ap.parse_args(argv)
    try:
        if a.rendered:
            text = Path(a.rendered).read_text(encoding="utf-8")
        elif a.chart:
            if not a.release:
                raise InputError("--chart needs --release (the Helm release name)")
            text = helm_render(a.chart, a.values, a.release)
        else:
            raise InputError("need --chart or --rendered")
        docs = load_docs(text)
        del text
        if not docs:
            raise InputError("no documents in the render")
        release = resolve_release(docs, a.release)
        layers = [load_yaml_file(v) for v in a.values]
        chart_layer = {}
        if a.chart and (Path(a.chart) / "values.yaml").is_file():
            chart_layer = load_yaml_file(str(Path(a.chart) / "values.yaml"))
        model = build_model(docs, release, layers, chart_layer, bool(a.values))
        if a.print_rows:
            sys.stdout.write(yaml.safe_dump(current_rows(model), sort_keys=False,
                                            width=1000, allow_unicode=True))
            return EXIT_OK
        ledger = load_ledger(Path(a.exceptions))
    except (InputError, OSError) as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_INPUT
    fails = check_render(docs, release, model, ledger)
    for f in fails:
        print(f)
    if fails:
        return EXIT_CHECK
    counts = ", ".join(f"{cls} {len(set(model.exceptions.get(cls, [])))}" for cls in LEDGER_CLASSES)
    workloads = sum(1 for d in docs if d.get("kind") in WORKLOAD_KINDS)
    print(f"ok: {workloads} workloads, {len(model.brokers)} brokers, ledger rows: {counts}")
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
