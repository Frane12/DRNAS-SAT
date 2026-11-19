#!/usr/bin/env bash
# Import SAT-only code from the public research repository; never mutate it.
set -Eeuo pipefail
OLD_REPO=https://github.com/Frane12/AndroidGameTest.git
BASELINE=experiment/drnas-xorlin-cdcl1-prospective-mixed12b-20261117
ROOT="$(git rev-parse --show-toplevel)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
SRC="$TMP/source"
STAGE="$TMP/stage"
mkdir -p "$STAGE"
echo "SOURCE_BASELINE=$BASELINE"
git clone --quiet --depth 1 --single-branch --branch "$BASELINE" "$OLD_REPO" "$SRC"

# SAT source and accompanying research. No old APK, app, cat assets or CI.
for path in CMakeLists.txt README_PCMAX.md src research tests docs experiments mi_ltm4 mi_ltm5 mi_ltm6 third_party; do
  if test -e "$SRC/$path"; then cp -a "$SRC/$path" "$STAGE/"; fi
done
for f in "$SRC"/README_X*.md; do
  if test -f "$f"; then cp -a "$f" "$STAGE/"; fi
done
mkdir -p "$STAGE/docs" "$STAGE/evidence/pcmax-m14-3640-14524"
printf 'branch,sha,mode\n%s,%s,baseline\n' "$BASELINE" "$(git -C "$SRC" rev-parse HEAD)" > "$STAGE/docs/SOURCE_REFS.csv"

# Each experimental line may have extra source files missing from baseline.
# Add these without overwriting baseline files; preserve exact branch SHAs.
for branch in \
  experiment/drnas-ipg7b-original-source-configbridge-20261116 \
  experiment/drnas-match3-flow-hall-poly1-20261116 \
  experiment/drnas-ipg5c-source-onehot-general-20261116 \
  experiment/drnas-pcmax-veripb-weighted2-20261115 \
  experiment/drnas-graphclique-veripb-real67-20261116 \
  experiment/drnas-math5-veripb-real67-20261116 \
  experiment/drnas-xor234-grid-veripb-20261117; do
  echo "SOURCE_OVERLAY=$branch"
  if ! git -C "$SRC" fetch --quiet --no-tags --depth 1 origin "$branch"; then
    echo "WARNING: overlay fetch failed for $branch"
    continue
  fi
  printf '%s,%s,missing-files-only\n' "$branch" "$(git -C "$SRC" rev-parse FETCH_HEAD)" >> "$STAGE/docs/SOURCE_REFS.csv"
  while IFS= read -r file; do
    if test ! -e "$STAGE/$file"; then
      mkdir -p "$STAGE/$(dirname "$file")"
      git -C "$SRC" show "FETCH_HEAD:$file" > "$STAGE/$file"
    fi
  done < <(git -C "$SRC" ls-tree -r --name-only FETCH_HEAD -- src research tests docs experiments mi_ltm4 mi_ltm5 mi_ltm6 third_party)
done

# All historic SAT branches remain available as exact provenance.
{
  printf '# Historic DRNAS SAT experiment branches\n\n'
  printf 'Old repository: https://github.com/Frane12/AndroidGameTest\n\n'
  printf 'These branch refs remain in the old project; run artifacts do not migrate with Git commits.\n\n'
  printf '| Old branch | Commit |\n|---|---|\n'
  git ls-remote --heads "$OLD_REPO" 'refs/heads/experiment/drnas-*' \
    | while read -r sha ref; do
        branch="$(printf '%s' "$ref" | sed 's#refs/heads/##')"
        printf '| [%s](https://github.com/Frane12/AndroidGameTest/tree/%s) | %s |\n' "$branch" "$branch" "$sha"
      done
} > "$STAGE/docs/LEGACY_SAT_BRANCHES.md"

cat > "$STAGE/evidence/pcmax-m14-3640-14524/README.md" <<'EOF'
# Independent PCMAX m14 UNSAT certificate
Original: pcmax-scheduling-m14-3640-14524-UNSAT.sanitized.cnf
Source SHA-256: a540b7d1aa098217bde5145b56f1f8e4898e9fedd73ea1ad99259ed43fa1e275
DRNAS Weighted VeriPB2 on one logical CPU: VERIFIED_UNSAT.
VeriPB 3.0.2 accepted the proof (exit code 0); proof size: 557597 bytes.
Weighted demand 31 > capacity 30. This is not 31 literal jobs.
Verified source run: https://github.com/Frane12/AndroidGameTest/actions/runs/43719601339
Proof artifact: https://github.com/Frane12/AndroidGameTest/actions/runs/43719601339/artifacts/14164325633
The 2024 PCMAX publication already reported this instance UNSAT.
EOF

# Copy files only if absent. Keep this repository's own README and workflows.
rsync -a --ignore-existing "$STAGE/" "$ROOT/"
test -f "$ROOT/CMakeLists.txt"
test -f "$ROOT/src/drnas_x59.cpp"
test -f "$ROOT/research/pcmax_capacity/emit_veripb_capacity_weighted2.py"
git -C "$ROOT" add CMakeLists.txt README_PCMAX.md README_X*.md src research tests docs experiments mi_ltm4 mi_ltm5 mi_ltm6 third_party evidence
if ! git -C "$ROOT" diff --cached --quiet; then
  git -C "$ROOT" config user.name "github-actions[bot]"
  git -C "$ROOT" config user.email "41898282+github-actions[bot]@users.noreply.github.com"
  git -C "$ROOT" commit -m "Import SAT research source, mathematical modules and reproducibility evidence"
  git -C "$ROOT" push origin HEAD:main
fi
echo "DRNAS_SAT_MIGRATION_COMPLETED"
