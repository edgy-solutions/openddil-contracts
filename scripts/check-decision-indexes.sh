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

# --- checks 3 & 4: declared status tokens ----------------------------------
# Status used to be prose, and every attempt to infer it by pattern produced
# both false positives and false negatives — no context window is correct
# because register blocks vary in length. So it is DECLARED now, and this is
# an exact string comparison with no window and no heuristic.
# See PLAN-register-status-tokens.md.
#
# Two homes, one grammar:
#   GD  — the Status COLUMN of the table in GENERALIZATION-DEBT.md is the
#         token. A second token there would be two truths.
#   others — a `Status: …` line immediately above the row's **ID — heading.
home_status() {
  # GD rows: | **GD-01** | … | … | open |
  sed -nE 's/^\| \*\*(GD-[0-9]{2})\*\* \|.*\| ([^|]*) \|$/\1\t\2/p' GENERALIZATION-DEBT.md \
    | sed -E 's/[[:space:]]+$//'
  # prose rows: a Status line, then (blank lines), then the heading it labels
  awk '
    /^`Status: / { s=$0; sub(/^`Status: /,"",s); sub(/`$/,"",s); pending=s; next }
    /^\*\*(UD|VE|IH|AE)-[0-9]+ —/ {
      if (pending != "") {
        match($0,/(UD|VE|IH|AE)-[0-9]+/)
        print substr($0,RSTART,RLENGTH) "\t" pending
        pending=""
      }
    }
  ' ADR-0035-*.md ADR-0036-*.md ADR-0037-*.md ADR-0038-*.md
}

index_status() {
  sed -nE 's/^\| ((GD|UD|VE|IH|AE)-[0-9]{1,2}) \|.*\| ([^|]*) \|$/\1\t\3/p' FOLLOW-UPS.md \
    | sed -E 's/[[:space:]]+$//'
}

home_status | sort > /tmp/.dec_homes.$$
index_status | sort > /tmp/.dec_idx.$$
trap 'rm -f /tmp/.dec_homes.$$ /tmp/.dec_idx.$$' EXIT

# Both checks in one awk pass, exact field comparison — no regex against
# prose, no window, nothing to tune.
#
# check 4 runs first in effect: a row whose home carries NO token would
# otherwise drop out of the comparison silently — absence answering as
# agreement, which is the exact disease this tooling exists to fight.
status_report=$(awk -F'\t' '
  NR==FNR { home[$1]=$2; next }
  { idx[$1]=$2 }
  END {
    for (id in idx) {
      if (!(id in home))
        print "FAIL: " id " has no declared Status token in its home document"
      else if (home[id] != idx[id])
        print "FAIL: " id " status disagrees — home says \x27" home[id] "\x27, index says \x27" idx[id] "\x27 (the home is authoritative; fix the index)"
    }
  }
' /tmp/.dec_homes.$$ /tmp/.dec_idx.$$ | sort)

if [ -n "$status_report" ]; then
  printf '%s\n' "$status_report"
  fail=1
fi

if [ "$fail" -eq 0 ]; then
  echo "decision indexes clean: $(echo "$corpus" | wc -l | tr -d ' ') IDs, all documents indexed, all statuses agree"
  echo "note: 'agree' means the index matches the home, NOT that either is true."
fi
exit "$fail"
