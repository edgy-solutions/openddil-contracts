#!/usr/bin/env python3
"""capability_floor.py - the render as a floor under the capability phases.

A capability with no `built` citation is understated: capability_phases.py
only reads what the record cites, so a missing citation lowers a phase and
nothing catches it. This module reads the render the other way. Every
workload, kind, flag and route the chart renders has to be claimed in the
record's `rendered:` section by the capabilities it serves (or marked
infrastructure with a reason), and a capability that claims a rendered item
cannot sit below `built unmeasured`.

`rendered:` maps a section (workload, kind, flag, route) to a map of item to
a claim. A claim is a non-empty list of capability names, or
`{infrastructure: "<reason>"}`.

Used by check_views.py (the `floor` rule). Writes no file; the render is
held in memory and dropped. Stdlib and PyYAML only.
"""
from __future__ import annotations

from pathlib import Path

import data_exchange
from capability_phases import CheckError, phase_of

FLOOR_PHASES = ("measured", "built unmeasured")
SECTIONS = ("workload", "kind", "flag", "route")
NAME_LABELS = ("app.kubernetes.io/component", "component", "app")


def workload_name(doc: dict, release: str, tiers: list[str]) -> str:
    """The workload's name as the record claims it: component label, release prefix and tier suffix gone."""
    meta = doc.get("metadata") or {}
    labels = meta.get("labels") if isinstance(meta.get("labels"), dict) else {}
    raw = next((str(labels[k]) for k in NAME_LABELS if labels.get(k)), str(meta.get("name", "")))
    name = data_exchange.strip_prefix(raw, release)
    for tier in sorted(tiers, key=lambda t: (-len(t), t)):
        if name.endswith("-" + tier):
            return name[:-len(tier) - 1] or name
    return name


def merge(layers: list[dict]) -> dict:
    """Helm's merge for maps: later wins per key, a dict merges, anything else replaces."""
    out: dict = {}
    for layer in layers:
        for key, v in (layer or {}).items():
            if isinstance(v, dict) and isinstance(out.get(key), dict):
                out[key] = merge([out[key], v])
            else:
                out[key] = merge([v]) if isinstance(v, dict) else v
    return out


def enabled_paths(d: dict, prefix: str = "") -> set[str]:
    """Dotted path of every dict with `enabled: true`. Lists are not walked."""
    found = set()
    if d.get("enabled") is True and prefix:
        found.add(prefix)
    for key, v in d.items():
        if isinstance(v, dict):
            found |= enabled_paths(v, f"{prefix}.{key}" if prefix else str(key))
    return found


def rendered_items(docs: list[dict], model, value_layers: list[dict],
                   release: str | None = None) -> dict[str, set[str]]:
    """Section to the items the render shows. `release` defaults to the render's instance label."""
    release = data_exchange.resolve_release(docs, release)
    items: dict[str, set[str]] = {s: set() for s in SECTIONS}
    for d in docs:
        if d.get("kind") in data_exchange.WORKLOAD_KINDS:
            items["workload"].add(workload_name(d, release, model.tiers))
        if d.get("kind") == "Ingress":
            for rule in (d.get("spec") or {}).get("rules") or []:
                for p in ((rule or {}).get("http") or {}).get("paths") or []:
                    if (p or {}).get("path"):
                        items["route"].add(f"ingress {p['path']}")
    items["kind"] = set(model.kinds)
    items["flag"] = enabled_paths(merge(value_layers))
    items["route"] |= {str(r["name"]) for r in model.routes if r.get("name")}
    return items


def check_floor(record: dict, capabilities, statuses: dict, items: dict[str, set[str]]) -> list[str]:
    """Every failure, one line each, prefixed `floor: `. Raises CheckError on an empty render."""
    if not any(items.get(s) for s in SECTIONS):
        raise CheckError("floor: the render shows no workload, kind, flag or route")
    claims = record.get("rendered")
    if not isinstance(claims, dict):
        return ["floor: the record has no rendered section"]
    fails = []
    caps = record["capabilities"]
    for section in claims:
        if section not in SECTIONS:
            fails.append(f"floor: rendered has an unknown section {section}")
    for section in SECTIONS:
        have = items.get(section) or set()
        claimed = claims.get(section) or {}
        if not isinstance(claimed, dict):
            fails.append(f"floor: rendered {section} is not a map")
            continue
        for item in sorted(have):
            if item not in claimed:
                fails.append(f"floor: {section} {item} is in the render and the record does not claim it")
        for item in sorted(claimed, key=str):
            claim = claimed[item]
            if item not in have:
                fails.append(f"floor: {section} {item} is claimed but the render does not show it")
            if isinstance(claim, dict):
                reason = claim.get("infrastructure")
                if set(claim) != {"infrastructure"} or not isinstance(reason, str) or not reason.strip():
                    fails.append(f"floor: {section} {item} has a malformed claim")
                continue
            if not isinstance(claim, list) or not claim or not all(isinstance(c, str) for c in claim):
                fails.append(f"floor: {section} {item} has a malformed claim")
                continue
            for name in claim:
                if name not in capabilities:
                    fails.append(f"floor: {section} {item} names {name}, which is not a capability in the model")
                    continue
                phase = phase_of(caps.get(name) or {}, statuses)
                if phase not in FLOOR_PHASES:
                    fails.append(f"floor: {name} is {phase or 'no phase'}, but the render shows "
                                 f"{section} {item}, so it cannot be below built unmeasured")
    return fails


def render_inputs(chart, values, release) -> tuple[dict[str, set[str]], list[dict]]:
    """Render the chart in memory and return (rendered_items, docs). Raises data_exchange.InputError."""
    text = data_exchange.helm_render(str(chart), [str(v) for v in values], release)
    docs = data_exchange.load_docs(text)
    del text  # never kept, never written
    if not docs:
        raise data_exchange.InputError("no documents in the render")
    release = data_exchange.resolve_release(docs, release)
    layers = [data_exchange.load_yaml_file(str(v)) for v in values]
    chart_values = Path(chart) / "values.yaml"
    chart_layer = data_exchange.load_yaml_file(str(chart_values)) if chart_values.is_file() else {}
    model = data_exchange.build_model(docs, release, layers, chart_layer, True)
    return rendered_items(docs, model, [chart_layer] + layers, release), docs
