#!/usr/bin/env bash
# Cross-seam citation pins: an ADR here that cites an iagent record pins the
# iagent commit it read.
#
# This mirrors invincible-agent's reference-ADR pin check, in the other
# direction (scripts/check_reference_adr_pins.py and
# .github/workflows/reference-adr-pins.yml there, which pin this repo).
#
# AN ADR THAT CITES `iagent:ADR-NNNN` CARRIES, under its title, one line per
# cited record:
#
#     **Cites:** `invincible-agent/docs/adr/ADR-NNNN-<slug>.md` at `<sha>`
#
# and .github/invincible-agent.ref holds the one full 40-hex sha this tree
# pins that repo at. The pin moves only in the same commit as the Cites lines.
#
# THIS IS THE LOCAL HALF, and it is hermetic: both directions of inline
# citation <-> Cites line, the Cites line's form, the pin file's shape, and
# that every cited sha is a prefix of the pin. It cannot see the other repo.
# decision-indexes.yml fetches the pin and checks each cited file exists at
# it, on every PR and daily, because the cited commit can disappear without a
# change here.
#
# Scope: ADR files. An index row in README.md names a record and is not one.
#
#   ./scripts/check-iagent-citation-pins.sh [ROOT]
#
# Stdout: `<adr-file> invincible-agent <full-pin-sha> <path>` per Cites line.
# Errors go to stderr, exit 1. Zero Cites lines is an error, not a pass.
set -uo pipefail

root="${1:-$(dirname "$0")/..}"
repo="invincible-agent"
ref="$root/.github/$repo.ref"
cites_re='^\*\*Cites:\*\* `'"$repo"'/(docs/adr/ADR-([0-9]{4})-[^`]+\.md)` at `([0-9a-f]{7,40})`$'
errs=0
rows=()
err() { echo "error: $*" >&2; errs=$((errs + 1)); }

pin=""
if [ ! -f "$ref" ]; then
  err ".github/$repo.ref is missing (cited as a source repo)"
else
  body=$(tr -d '\r' < "$ref" | grep -vE '^[[:space:]]*(#|$)' | sed -E 's/^[[:space:]]+|[[:space:]]+$//g')
  if [ "$(printf '%s' "$body" | grep -c .)" -ne 1 ] || ! [[ "$body" =~ ^[0-9a-f]{40}$ ]]; then
    err ".github/$repo.ref must hold exactly one full 40-hex sha, got: $(printf '%s' "$body" | tr '\n' ' ')"
  else
    pin="$body"
  fi
fi

for f in "$root"/decisions/ADR-[0-9][0-9][0-9][0-9]-*.md; do
  [ -f "$f" ] || continue
  name=$(basename "$f")
  text=$(tr -d '\r' < "$f")
  cited=$(printf '%s\n' "$text" | grep -vE '^\*\*Cites:\*\*' | grep -oE 'iagent:ADR-[0-9]{4}' | sed 's/^iagent:ADR-//' | sort -u)
  pinned=" "
  while IFS= read -r line; do
    [ -n "$line" ] || continue
    if ! [[ "$line" =~ $cites_re ]]; then
      err "$name: Cites line is malformed: $line"
      continue
    fi
    path="${BASH_REMATCH[1]}"; num="${BASH_REMATCH[2]}"; sha="${BASH_REMATCH[3]}"
    pinned="$pinned$num "
    if ! printf '%s\n' "$cited" | grep -qx "$num"; then
      err "$name: has a Cites line for iagent ADR-$num and never cites iagent:ADR-$num"
      continue
    fi
    [ -n "$pin" ] || continue
    if [ "${pin#"$sha"}" = "$pin" ]; then
      err "$name: cites $repo at $sha, which is not a prefix of the pin $pin in .github/$repo.ref"
      continue
    fi
    rows+=("$name $repo $pin $path")
  done < <(printf '%s\n' "$text" | grep -E '^\*\*Cites:\*\*')
  for num in $cited; do
    case "$pinned" in
      *" $num "*) ;;
      *) err "$name: cites iagent:ADR-$num with no Cites line pinning it" ;;
    esac
  done
done

if [ "${#rows[@]}" -eq 0 ]; then
  if [ "$errs" -eq 0 ]; then
    err "no Cites line found; an empty list is not a pass"
  else
    err "no Cites line passed; an empty list is not a pass"
  fi
fi
[ "$errs" -eq 0 ] || exit 1
printf '%s\n' "${rows[@]}"
