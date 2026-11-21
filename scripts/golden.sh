#!/usr/bin/env bash
# The golden comparison: the architecture export built from one tree by the arch-kit at its old pin and by the
# arch-kit at its new pin, with the same commands, flags and lists. Every difference must be named in
# docs/arch/golden-allow.txt under a `# pins:` line for this pair (scripts/golden_compare.py), or this fails.
#
# usage: scripts/golden.sh TREE OLD_KIT NEW_KIT OUT
#   TREE      this repository, checked out with full history (decision stamps come from git)
#   OLD_KIT   an arch-kit checkout at the old pin
#   NEW_KIT   an arch-kit checkout at the new pin
#   OUT       a new directory for both builds and their logs
# Each kit's Python requirements are installed by the caller; `npm ci` is run in a kit's export directory when
# it has no node_modules.
# env, all paths: CHART, BUNDLE, READINESS, RELABEL (the relabel list, as the check job passes it), BARRED.
# PUPPETEER_EXECUTABLE_PATH names Chrome. PYTHON defaults to python.
#
# Both sides get the same flags. If the old kit's tool rejects one the new side passes, that side fails and the
# log names the tool; no flag is dropped.
set -u
TREE=$(cd "$1" && pwd); OLD_KIT=$(cd "$2" && pwd); NEW_KIT=$(cd "$3" && pwd); OUT=$4
: "${CHART:?}" "${BUNDLE:?}" "${READINESS:?}" "${RELABEL:?}" "${BARRED:?}"
PY=${PYTHON:-python}
export PYTHONIOENCODING=utf-8 PYTHONUTF8=1 PUPPETEER_SKIP_DOWNLOAD=true
mkdir -p "$OUT" || exit 2
OUT=$(cd "$OUT" && pwd)
VALUES=(--values "$BUNDLE/k8s/tier-node-values.yaml" --values "$BUNDLE/k8s/egress-values.yaml")
echo '{"args": ["--no-sandbox"]}' > "$OUT/puppeteer.json"
rc=0; rm -f "$OUT/FAILED"
run() { local name=$1; shift; "$@" > "$OUT/$name.log" 2>&1; local r=$?; echo "$name rc=$r"; [ "$r" = 0 ] || touch "$OUT/FAILED"; }

OLD_SHA=$(git -C "$OLD_KIT" rev-parse HEAD) || exit 2
NEW_SHA=$(git -C "$NEW_KIT" rev-parse HEAD) || exit 2
mkdir -p "$OUT/old" "$OUT/new"
for K in "$OLD_KIT" "$NEW_KIT"; do
  [ -d "$K/arch_kit/tools/export/node_modules" ] || (cd "$K/arch_kit/tools/export" && npm ci > "$OUT/npm-$(basename "$K").log" 2>&1) || exit 2
done

# One side: the same commands from the same tree, with PYTHONPATH at the side's own kit.
side() {
  local label=$1 kit=$2
  (
    cd "$TREE" || exit 2
    export PYTHONPATH="$kit"
    ak() { "$PY" -m arch_kit --config docs/arch/arch-kit.yaml "$@"; }
    run "$label/render_html" ak render_html --out "$OUT/$label/export.html" --chart "$CHART" "${VALUES[@]}" --release openddil \
      --readiness "$READINESS" --relabel "$RELABEL" --barred "$BARRED" --puppeteer-config "$OUT/puppeteer.json"
    run "$label/check_export" ak check_export --export "$OUT/$label/export.html" --barred "$BARRED" --relabel "$RELABEL"
    run "$label/check_views" ak check_views --chart "$CHART" --release openddil "${VALUES[@]}" --readiness "$READINESS" --barred "$BARRED"
    run "$label/browser_facts" ak browser_facts --out "$OUT/$label/facts.json"
    (cd "$kit/arch_kit/tools/export" && run "$label/browser" node check_export_browser.mjs "$OUT/$label/export.html" \
      --shots "$OUT/$label/shots" --facts "$OUT/$label/facts.json" --puppeteer-config "$OUT/puppeteer.json")
  ) | sed "s/^/$label: /"
}

# A rejected flag shows as usage text in the log; say which tool, never print what it read.
side old "$OLD_KIT"
side new "$NEW_KIT"
for label in old new; do
  for f in "$OUT/$label"/*.log; do
    [ -f "$f" ] || continue
    if grep -qiE 'unrecognized arguments|unknown (option|argument)|no such option' "$f"; then
      echo "$label: $(basename "$f" .log) rejected a flag the other side passes"
    fi
  done
done

# The comparison.
"$PY" "$TREE/scripts/golden_compare.py" "$OUT/old/export.html" "$OUT/new/export.html" "$TREE/docs/arch/golden-allow.txt" \
  --out "$OUT/compare" --pins "$OLD_SHA" "$NEW_SHA" | tee "$OUT/compare.log" || rc=1
[ -e "$OUT/FAILED" ] && rc=1
if [ -f "$OUT/compare/old.reduced" ]; then cmp "$OUT/compare/old.reduced" "$OUT/compare/new.reduced" || rc=1; fi
echo "check_export (old kit): $(tail -n 1 "$OUT/old/check_export.log")"
echo "check_export (new kit): $(tail -n 1 "$OUT/new/check_export.log")"
exit $rc
