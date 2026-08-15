#!/usr/bin/env bash
# Index-drift checks for decisions/.
#
# ONE COPY, run by both CI and humans. FOLLOW-UPS.md points here rather than
# repeating the commands, because a documented copy and a CI copy are two
# things to keep in sync — which is the exact drift these checks exist to
# catch. Do not inline them into the workflow.
#
#   ./scripts/check-decision-indexes.sh
#
# Exit 0 = clean. Exit 1 = drift, with the specifics printed.
#
# WHAT THESE PROVE, AND WHAT THEY DO NOT
#   check 1  every register ID has an index row, and every row is a real ID
#   check 2  every decisions/ document is referenced by README.md
#   NOT checked: whether a row's STATUS is still true. That is deliberate and
#   is not an oversight — see PLAN-register-status-tokens.md. Status is
#   currently prose, and every attempt to infer it by pattern produced both
#   false positives and false negatives, because register blocks vary in
#   length so no context window is correct. A check tuned until it passes is
#   a check whose green means nothing.
set -uo pipefail

cd "$(dirname "$0")/../decisions" || exit 2
fail=0

# --- check 1: IDs <-> index rows -------------------------------------------
# The `grep -v FOLLOW-UPS.md` is LOAD-BEARING, not tidiness. Scanning *.md
# would include the index in its own corpus, so every row would vouch for
# itself and the phantom-row direction could never fail. A verification that
# includes its own subject in its evidence is not a verification.
corpus=$(grep -ohE "\b(GD|UD|VE|IH|AE)-[0-9]{1,2}\b" \
           $(ls *.md | grep -v '^FOLLOW-UPS.md$') | sort -u)
rows=$(grep -ohE "^\| (GD|UD|VE|IH|AE)-[0-9]{1,2} " FOLLOW-UPS.md \
         | tr -d '| ' | sort -u)

missing=$(comm -23 <(echo "$corpus") <(echo "$rows"))
phantom=$(comm -13 <(echo "$corpus") <(echo "$rows"))

if [ -n "$missing" ]; then
  echo "FAIL: register IDs with no row in FOLLOW-UPS.md:"
  echo "$missing" | sed 's/^/    /'
  fail=1
fi
if [ -n "$phantom" ]; then
  echo "FAIL: rows in FOLLOW-UPS.md whose ID exists nowhere else:"
  echo "$phantom" | sed 's/^/    /'
  echo "    (a renamed or deleted ID, or a typo in the row)"
  fail=1
fi

# --- check 2: every document is indexed ------------------------------------
# Blind spot of check 1: a whole document can go unlisted without affecting
# any ID. First run of this found ELEVEN, including PRINCIPLES.md and
# GENERALIZATION-DEBT.md — the two most-cited files in the corpus.
unindexed=""
for f in ADR-*.md AUDIT-*.md PLAN-*.md DESIGN-*.md BRIEF-*.md \
         GENERALIZATION-DEBT.md PRINCIPLES.md FOLLOW-UPS.md EXCHANGE-LEDGER.md; do
  [ -e "$f" ] || continue
  grep -q "$f" README.md || unindexed="${unindexed}    ${f}"$'\n'
done
if [ -n "$unindexed" ]; then
  echo "FAIL: documents not referenced by decisions/README.md:"
  printf '%s' "$unindexed"
  fail=1
fi

if [ "$fail" -eq 0 ]; then
  echo "decision indexes clean: $(echo "$corpus" | wc -l | tr -d ' ') IDs, all documents indexed"
fi
exit "$fail"
