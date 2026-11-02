# ADR-0054 — Workload annotations declare a workload's broker use

## Status

**ACCEPTED (decisions 1 to 4) — 2026-11-02.** Decisions 1 to 4 record what the chart already renders. Decisions 5 and 6 are the next increment and are not built.
- Nothing in the chart changes for 1 to 4.
- 5 and 6 are chart changes, to be made in the chart's own repository.
- The render check in the Check section exists and has been run. No workflow runs it yet.

## Findings first

Counts are from the chart at 0.1.161, rendered with the public twin (`k8s/tier-node-values.yaml` and `k8s/egress-values.yaml` in the example bundle). `docs/arch/annotation-exceptions.yaml` holds the rows.

1. **No decision record defines these annotations.**
   - Their definition is a comment on one template and the code of two scripts (`openddil:openddil-helm/openddil-demo/templates/edge.yaml:241-245, 452-458`).
   - That comment cites a specification that is not in `decisions/`.
2. **A reset depends on one of them.**
   - The reset used to resolve a consumer group's owner from its member's connection source IP. A consumer reaching a broker through a proxy resolved to the proxy and was skipped.
   - It now reads the owner from `openddil.io/consumer-groups`, or from Restate's own subscription list. An owner it cannot resolve is a refusal (`openddil:openddil-helm/scripts/reset-scenario.sh:574-588`).
3. **A bridge's writes to its parent broker are not declared.** 26 writes to a parent broker have no annotation naming the writer. They are 13 topics, each written by the `edge-hq-bridge` of both edges. The bridge's own annotation lists what it originates, so these writes can only be inferred from its config.
4. **A consumer-group declaration does not say which topics the group reads.** 27 declared groups cannot be bound to a topic from the render.
5. **24 workloads declare neither annotation.** Some touch no broker. The render alone cannot tell those from a workload whose broker use is simply undeclared.

## Decision

1. **Grammar.** Each annotation value is a space-separated list of `<broker-id>/<name>` tokens.
   - `<broker-id>` is the id of a broker the release renders. `<name>` is a topic or a group, according to the annotation.
   - A token holds exactly one `/`. A token does not repeat within one annotation.
2. **Placement.** The annotations sit on the workload's own metadata, never on its pod template. A pod template annotation would roll the pod on every edit to a declaration.
3. **`openddil.io/produces-topics` names what the workload originates.**
   - The producing repository's `produces.yaml` is the source for the topic names. The chart is the source for which broker each one is placed on.
   - `openddil:openddil-helm/scripts/check-produces-declarations.py` compares the names as sets, and a missing manifest is a failure (`:6, 14`).
4. **`openddil.io/consumer-groups` names the groups the workload owns.**
   - One group on one broker has one owner. Two workloads may produce one topic; two workloads may not own one group.
   - `openddil:openddil-helm/scripts/check_consumer_declarations.py` compares declared pairs with a deployment's expected list.
5. **Next increment: `openddil.io/forwards-topics` names what a bridge writes without originating it.**
   - It uses the same grammar and the same placement.
   - It is a separate key because the meaning differs. Adding forwarded topics to `produces-topics` would make that annotation disagree with the bridge's `produces.yaml`, and would stop saying who originated a record. Decision 3 needs to keep saying that.
6. **Next increment: `openddil.io/consumer-topics` names the topics a workload reads.**
   - It uses the same grammar and the same placement.
   - It names topics per workload, not per group. A reset needs the group and the architecture view needs the topic, so neither needs the two joined.

A workload with neither annotation stays a named exception with a reason, under the declared-exceptions rule. This record does not add a third state to declare "no broker use".

## Check

`docs/arch/tools/check_annotations.py` runs against a render and fails on:
- `grammar`: a malformed or repeated token;
- `placement`: either annotation in a pod template;
- `broker`: a token naming a broker the render does not have;
- `owner`: one group on one broker declared by two workloads;
- `ledger`: a row in the three exception classes that `annotation-exceptions.yaml` does not list, a listed row the render no longer has, or a class with no reason.

Each direction of the ledger fails, so a new undeclared workload and a stale exception both go red. Findings 3, 4 and 5 are the three classes. Decisions 5 and 6 would empty the first two.

The check needs a chart checkout and `helm`, so it does not run with `docs/arch/tools/check_views.py`, and it has no workflow. `openddil:openddil-helm/.github/workflows/chart-checks.yml` is the place for it, because that is where a chart change would turn it red.

## What this does not establish

A declaration is a claim about a workload. These checks compare claims with a render, a manifest and an expected list. They do not compare any of them with traffic on a broker, so nothing here shows that a workload writes or reads what it declares.

## Consequences

- The data-exchange view keeps reading these annotations, and now cites this record for them.
- Decision 5 adds a key to each bridge template, and decision 6 adds one to each consumer. Annotations on workload metadata do not roll pods, so neither forces a restart.
- Once decision 5 is built, `check-produces-declarations.py` still reads only `produces-topics`, so it does not change.
