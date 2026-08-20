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
#   check 3  every row's status equals its home's declared token, exactly
#   check 4  every row's home HAS a token (so check 3 cannot be skipped by
#            absence — absence answering as agreement is the disease this
#            tooling exists to fight)
#
#   NOT checked: whether a status is TRUE. Check 3 proves the index AGREES
#   with the home; both can be wrong together. Only a human reading the home
#   document establishes truth, and the clean-run output says so out loud.
#
#   Status is compared, not inferred. It used to be prose, and every attempt
#   to pattern-match it produced both false positives and false negatives —
#   register blocks vary in length, so no context window is correct. A check
#   tuned until it passes is a check whose green means nothing. The fix was
#   to declare the property, not to write a better regex.
#   See PLAN-register-status-tokens.md.
set -uo pipefail

cd "$(dirname "$0")/../decisions" || exit 2
fail=0

# --- scope, derived rather than listed --------------------------------------
# REGISTER HOMES are enumerated from the directory. An earlier version named
# ADR-0035..0038 literally, so a register introduced in ADR-0039+ was invisible
# to checks 3 and 4 — the third instance in this repo of scope-as-literal-list,
# after the §7 completeness gate hardcoding its table set and the migration's
# scope comment. Same fix each time: ASK THE DIRECTORY, not the author's memory
# of it.
homes_files=$(ls ADR-*.md GENERALIZATION-DEBT.md 2>/dev/null)

# REGISTER PREFIXES are derived from declaration sites in those homes — both
# shapes: a bolded heading (`**UD-7 — …`) and a table row (`| **GD-01** |`).
#
# Deliberately NOT a generic [A-Z]{2}-[0-9]+ scan over prose. In this domain
# that pattern also matches platform designations — UH-60, CH-47, AH-64, MQ-9 —
# and a check that demands an index row for "AH-64" is a false-positive
# generator whose failures teach people to ignore it. None appear in decisions/
# today; the point is that they legitimately could.
#
# Also deliberately not scanned from PLAN-*/README: PLAN-register-status-
# tokens.md contains an EXAMPLE row, and an example is not a declaration.
prefixes=$( { grep -ohE "^\*\*[A-Z]{2}-[0-9]{1,2} —" $homes_files
              grep -ohE "^\| \*\*[A-Z]{2}-[0-9]{1,2}\*\* \|" $homes_files
            } 2>/dev/null | grep -oE "[A-Z]{2}" | sort -u | paste -sd'|' -)
if [ -z "$prefixes" ]; then
  echo "FAIL: no register prefixes found — the derivation is broken, not the corpus"
  exit 1
fi

# --- check 1: IDs <-> index rows -------------------------------------------
# The `grep -v FOLLOW-UPS.md` is LOAD-BEARING, not tidiness. Scanning *.md
# would include the index in its own corpus, so every row would vouch for
# itself and the phantom-row direction could never fail. A verification that
# includes its own subject in its evidence is not a verification.
corpus=$(grep -ohE "\b($prefixes)-[0-9]{1,2}\b" \
           $(ls *.md | grep -v '^FOLLOW-UPS.md$') | sort -u)
rows=$(grep -ohE "^\| ($prefixes)-[0-9]{1,2} " FOLLOW-UPS.md \
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
  # table-shaped rows: | **GD-01** | … | … | open |
  sed -nE "s/^\| \*\*(($prefixes)-[0-9]{1,2})\*\* \|.*\| ([^|]*) \|\$/\1\t\3/p" $homes_files \
    | sed -E 's/[[:space:]]+$//'
  # prose rows: a `Status: …` line, then the **ID — heading it labels.
  # `prefixes` is passed in with -v; awk is single-quoted, so a shell variable
  # written inline here would silently be the literal string '$prefixes' and
  # match nothing — a scope bug that would look exactly like "no rows found".
  awk -v pre="$prefixes" '
    /^`Status: / { s=$0; sub(/^`Status: /,"",s); sub(/`$/,"",s); pending=s; next }
    $0 ~ "^\\*\\*(" pre ")-[0-9]+ —" {
      if (pending != "") {
        match($0, "(" pre ")-[0-9]+")
        print substr($0,RSTART,RLENGTH) "\t" pending
        pending=""
      }
    }
  ' $homes_files
}

index_status() {
  sed -nE "s/^\| (($prefixes)-[0-9]{1,2}) \|.*\| ([^|]*) \|\$/\1\t\3/p" FOLLOW-UPS.md \
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
