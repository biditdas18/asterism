#!/usr/bin/env bash
#
# restore.sh — undo anonymize.sh: return the tracked tree to the exact state it
# had before that script ran, commit, and push.
#
# Correctness is checked, not assumed: after restoring, the script requires
#   git diff <restore-point> HEAD
# to be empty. If a single byte differs anywhere in the tree, it aborts before
# pushing.
#
# Usage:  ./restore.sh          (prompts before pushing)
#         ./restore.sh -y       (no prompt)
#         PUSH=0 ./restore.sh -y   (restore locally, skip the push)
#
set -euo pipefail

REPO="${ASTERISM_REPO:-/Users/biditdas/Desktop/learn/projects/asterism}"
BRANCH="${BRANCH:-main}"
PUSH="${PUSH:-1}"

ASSUME_YES=0
[ "${1:-}" = "-y" ] && ASSUME_YES=1

cd "$REPO"
STAMP="$(git rev-parse --git-dir)/anon_restore_point"

say()  { printf '\n\033[1m%s\033[0m\n' "$*"; }
ok()   { printf '  ok  %s\n' "$*"; }
die()  { printf '\nABORT: %s\n' "$*" >&2; exit 1; }

# ─── 1. preflight ────────────────────────────────────────────────────────────
say "1/6  Preflight"
[ -f "$STAMP" ] || die "no restore point at $STAMP — anonymize.sh was not run from this clone, or restore already completed"
BASE="$(cat "$STAMP")"
git rev-parse --verify -q "$BASE^{commit}" >/dev/null || die "restore point $BASE is not a commit in this repo"
[ "$(git rev-parse --abbrev-ref HEAD)" = "$BRANCH" ] || die "not on branch $BRANCH"
git diff --quiet        || die "unstaged changes present — commit or stash first"
git diff --cached --quiet || die "staged changes present — commit or stash first"
ok "restore point ${BASE:0:7} ($(git log -1 --format=%s "$BASE"))"

# ─── 2. restore every tracked path to its state at the restore point ─────────
say "2/6  Restoring tracked tree from ${BASE:0:7}"
# Make the index and worktree exactly match the restore point.
#
# Deliberately NOT `git checkout $BASE -- .` followed by `git add -A -- .`:
# that second command also sweeps UNTRACKED files sitting in the repo root
# — including anonymize.sh and restore.sh themselves — into the restore
# commit, so the tree ends up as "$BASE plus two scripts" and the equality
# gate below rightly refuses to push. read-tree only touches paths that are
# in the index or in $BASE, so untracked helpers are left where they are.
git read-tree -u --reset "$BASE"
if git diff --cached --quiet; then
  rm -f "$STAMP"
  die "nothing to restore — tree already matches ${BASE:0:7} (restore point cleared)"
fi
git diff --cached --name-status | sed 's/^/  /'

# ─── 3. commit ───────────────────────────────────────────────────────────────
say "3/6  Commit"
git commit -q -m "chore: restore docs assets and built PDFs"
ok "committed $(git rev-parse --short HEAD)"

# ─── 4. prove the tree is byte-identical to the restore point ────────────────
say "4/6  Verifying full-tree equality with ${BASE:0:7}"
if ! git diff --quiet "$BASE" HEAD; then
  printf '\n  differences:\n'; git diff --stat "$BASE" HEAD | sed 's/^/  /'
  die "tree does NOT match the restore point — nothing pushed"
fi
ok "git diff ${BASE:0:7} HEAD is empty — every file back to its original bytes"

for f in docs/screenshot-zoomed.png docs/screenshot-hover.png \
         papers/Asterism_SSRN_revised.pdf papers/Asterism_workshop_paper.pdf; do
  git ls-files --error-unmatch "$f" >/dev/null 2>&1 || die "$f is not tracked again"
  ok "tracked again: $f"
done

# ─── 5. push ─────────────────────────────────────────────────────────────────
if [ "$PUSH" != "1" ]; then
  say "5/6  Push skipped (PUSH=0)"
  rm -f "$STAMP"
else
  say "5/6  Push"
  git fetch -q origin
  git push --dry-run origin "$BRANCH"
  if [ "$ASSUME_YES" != 1 ]; then
    read -r -p "  push the above to origin/$BRANCH? [y/N] " reply
    [ "$reply" = y ] || [ "$reply" = Y ] || die "not pushed (restore commit stands locally; re-run to push)"
  fi
  git push -q origin "$BRANCH"
  ok "pushed"

  # ─── 6. verify the server matches the restore point ──────────────────────
  say "6/6  Verifying the remote tree"
  git fetch -q origin
  if ! git diff --quiet "$BASE" "origin/$BRANCH"; then
    die "origin/$BRANCH does not match the restore point"
  fi
  ok "origin/$BRANCH tree is identical to ${BASE:0:7}"
  rm -f "$STAMP"
  ok "restore point cleared"
fi

say "Done — repo is back to its pre-anonymize state"
