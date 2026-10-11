#!/bin/sh
# Shared application-build/QA patch application. All runtime security hunks
# are preserved; source and patch downloads are verified by the caller.
set -eu
task_source="${1:?source directory required}"
task_patches="${2:?verified upstream patch directory required}"
task_evidence="${3:?new evidence directory required}"
task_assets="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
test -f "$task_source/src/classify/adaptmatch.cpp"
test ! -e "$task_evidence/applied-patches.tsv"
mkdir -p "$task_evidence"
cd "$task_source"
while read -r task_cve task_commit task_sha; do
  case "$task_cve" in ''|'#'*) continue ;; esac
  task_patch="$task_patches/$task_commit.patch"
  printf '%s  %s\n' "$task_sha" "$task_patch" | sha256sum -c -
  if test "$task_cve" = CVE-2026-88053; then
    # CONTEXT-only ports to5.5.0: old matcher flag/declaration argument and
    # a removed constructor loop absent here. Every ADDED guard is unchanged.
    test "$(grep -F -c 'CLASSIFY_ENABLE_ADAPTIVE_MATCHER_OVERRIDE' "$task_patch")" -eq 1
    test "$(grep -F -c 'void program_editdown();' "$task_patch")" -eq 2
    test "$(grep -F -c -- '-  for (int i = 0; i < MAX_NUM_CLASS_PRUNERS; i++) {' "$task_patch")" -eq 1
    sed -e 's/CLASSIFY_ENABLE_ADAPTIVE_MATCHER_OVERRIDE/classify_enable_adaptive_matcher/' \
        -e 's/void program_editdown();/void program_editdown(int32_t elapsed_time);/' \
        -e '/^-  for (int i = 0; i < MAX_NUM_CLASS_PRUNERS; i++) {$/,+2d' \
        "$task_patch" > "$task_evidence/inttemp-stable-backport.patch"
    git diff --no-index "$task_patch" "$task_evidence/inttemp-stable-backport.patch" \
      > "$task_evidence/inttemp-context-adaptations.diff" || test "$?" -eq 1
    task_patch="$task_evidence/inttemp-stable-backport.patch"
    printf '%s  %s\n' '718594436d7fa5f6fedb194484f8d75a4f3cb91c38398c71310d3005177b8675' \
      "$task_patch" | sha256sum -c -
    sha256sum "$task_patch" > "$task_evidence/inttemp-stable-backport.sha256"
  fi
  # No later-version build-system changes or fuzzy matching. Preserve the
  # original upstream regression bodies and ALL affected runtime source.
  git apply --recount --check --include='src/*' --include='unittest/*.cc' "$task_patch"
  git apply --recount --include='src/*' --include='unittest/*.cc' "$task_patch"
  printf '%s %s %s\n' "$task_cve" "$task_commit" "$task_sha" >> "$task_evidence/applied-patches.tsv"
done < "$task_assets/backports.tsv"
test "$(wc -l < "$task_evidence/applied-patches.tsv")" -eq 6
printf '%s  %s\n' '1646a66c1e340b6f71fa4852945b77d42c91189d8599a6e1746128cd4869ceab' \
  "$task_assets/stable-callsite.diff" | sha256sum -c -
# Old pointer-taking call: data() preserves its contract after std::array.
# No bounds check/capacity/deserializer is weakened.
git apply --check "$task_assets/stable-callsite.diff"
git apply "$task_assets/stable-callsite.diff"
cp "$task_assets/stable-callsite.diff" "$task_evidence/stable-callsite.patch"
