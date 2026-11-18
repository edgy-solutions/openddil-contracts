#!/usr/bin/env bash
# The golden comparison: the architecture export built by the tools this repository had of its own, and by the
# pinned arch-kit, from the same tree and the same lists. Every difference must be named in
# docs/arch/golden-allow.txt (scripts/golden_compare.py), or this fails.
#
# usage: scripts/golden.sh TREE OLD_TOOLS KIT OUT
#   TREE       this repository, checked out with full history (decision stamps come from git)
#   OLD_TOOLS  a docs/arch/tools directory from the last commit that had the repository's own tools
#   KIT        an arch-kit checkout (its Python requirements installed; `npm ci` is run in its export directory)
#   OUT        a new directory for both builds and their logs
# env, all paths: CHART, BUNDLE, READINESS, RELABEL (the relabel list, as the check job passes it), BARRED.
# PUPPETEER_EXECUTABLE_PATH names Chrome. PYTHON defaults to python.
#
# The old tools cannot read the new tools' flags (render_html has no --barred, the browser check has no --facts),
# so each side is given the flags it knows. The inputs are the same.
set -u
TREE=$(cd "$1" && pwd); OLD_TOOLS=$(cd "$2" && pwd); KIT=$(cd "$3" && pwd); OUT=$4
: "${CHART:?}" "${BUNDLE:?}" "${READINESS:?}" "${RELABEL:?}" "${BARRED:?}"
PY=${PYTHON:-python}
export PYTHONIOENCODING=utf-8 PYTHONUTF8=1 PUPPETEER_SKIP_DOWNLOAD=true
mkdir -p "$OUT" || exit 2
OUT=$(cd "$OUT" && pwd)
OLD="$OUT/old-tree"
VALUES=(--values "$BUNDLE/k8s/tier-node-values.yaml" --values "$BUNDLE/k8s/egress-values.yaml")
echo '{"args": ["--no-sandbox"]}' > "$OUT/puppeteer.json"
rc=0; rm -f "$OUT/FAILED"
run() { local name=$1; shift; "$@" > "$OUT/$name.log" 2>&1; local r=$?; echo "$name rc=$r"; [ "$r" = 0 ] || touch "$OUT/FAILED"; }

# 1. The old side: a copy of the tree (history included, tools left out) whose docs/arch/tools is the old directory.
rm -rf "$OLD"; mkdir -p "$OLD" || exit 2
(cd "$TREE" && tar -cf - --exclude=./docs/arch/tools .) | (cd "$OLD" && tar -xf -) || exit 2
cp -a "$OLD_TOOLS" "$OLD/docs/arch/tools" || exit 2
[ -d "$OLD/docs/arch/tools/export/node_modules" ] || (cd "$OLD/docs/arch/tools/export" && npm ci > "$OUT/old-npm.log" 2>&1) || exit 2
[ -d "$KIT/arch_kit/tools/export/node_modules" ] || (cd "$KIT/arch_kit/tools/export" && npm ci > "$OUT/kit-npm.log" 2>&1) || exit 2

mkdir -p "$OUT/old" "$OUT/kit"
(
  cd "$OLD" || exit 2
  old() { local t=$1; shift; "$PY" "docs/arch/tools/$t.py" "$@"; }
  run old/render_html old render_html --out "$OUT/old/export.html" --chart "$CHART" "${VALUES[@]}" --release openddil \
    --readiness "$READINESS" --relabel "$RELABEL" --puppeteer-config "$OUT/puppeteer.json"
  run old/check_export old check_export --export "$OUT/old/export.html" --barred "$BARRED" --relabel "$RELABEL"
  run old/check_views old check_views --chart "$CHART" --release openddil "${VALUES[@]}" --readiness "$READINESS" --barred "$BARRED"
  (cd docs/arch/tools/export && run old/browser node check_export_browser.mjs "$OUT/old/export.html" --shots "$OUT/old/shots" \
    --puppeteer-config "$OUT/puppeteer.json")
) | sed 's/^/old: /'

# 2. The kit side, from the tree itself.
(
  cd "$TREE" || exit 2
  export PYTHONPATH="$KIT"
  ak() { "$PY" -m arch_kit --config docs/arch/arch-kit.yaml "$@"; }
  run kit/render_html ak render_html --out "$OUT/kit/export.html" --chart "$CHART" "${VALUES[@]}" --release openddil \
    --readiness "$READINESS" --relabel "$RELABEL" --barred "$BARRED" --puppeteer-config "$OUT/puppeteer.json"
  run kit/check_export ak check_export --export "$OUT/kit/export.html" --barred "$BARRED" --relabel "$RELABEL"
  run kit/check_views ak check_views --chart "$CHART" --release openddil "${VALUES[@]}" --readiness "$READINESS" --barred "$BARRED"
  run kit/browser_facts ak browser_facts --out "$OUT/kit/facts.json"
  (cd "$KIT/arch_kit/tools/export" && run kit/browser node check_export_browser.mjs "$OUT/kit/export.html" --shots "$OUT/kit/shots" \
    --facts "$OUT/kit/facts.json" --puppeteer-config "$OUT/puppeteer.json")
) | sed 's/^/kit: /'

# 3. The comparison.
"$PY" "$TREE/scripts/golden_compare.py" "$OUT/old/export.html" "$OUT/kit/export.html" "$TREE/docs/arch/golden-allow.txt" \
  --out "$OUT/compare" | tee "$OUT/compare.log" || rc=1
[ -e "$OUT/FAILED" ] && rc=1
if [ -f "$OUT/compare/old.reduced" ]; then cmp "$OUT/compare/old.reduced" "$OUT/compare/new.reduced" || rc=1; fi
echo "check_export (old): $(tail -n 1 "$OUT/old/check_export.log")"
echo "check_export (kit): $(tail -n 1 "$OUT/kit/check_export.log")"
exit $rc
