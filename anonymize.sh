#!/usr/bin/env bash
#
# anonymize.sh — temporarily strip author identity from the tracked tree of the
# public repo and push, so an Anonymous GitHub resync picks up a clean tree.
#
# Scope, honestly: this rewrites the CURRENT tree only. It does not and cannot
# touch git history, commit author metadata, or the repo's own owner/URL.
# That is sufficient for the mirror, which serves the tree, not the history.
#
# Pair with restore.sh, which returns the repo to the exact pre-run state.
#
# Usage:  ./anonymize.sh          (prompts before pushing)
#         ./anonymize.sh -y       (no prompt)
#         PUSH=0 ./anonymize.sh -y   (do everything locally, skip the push)
#
set -euo pipefail

REPO="${ASTERISM_REPO:-/Users/biditdas/Desktop/learn/projects/asterism}"
BRANCH="${BRANCH:-main}"
PUSH="${PUSH:-1}"
PLACEHOLDER="Anonymous"
ANON_URL="https://anonymous.4open.science/r/asterism-7023"

ASSUME_YES=0
[ "${1:-}" = "-y" ] && ASSUME_YES=1

cd "$REPO"
STAMP="$(git rev-parse --git-dir)/anon_restore_point"   # inside .git — never committed

say()  { printf '\n\033[1m%s\033[0m\n' "$*"; }
ok()   { printf '  ok  %s\n' "$*"; }
die()  { printf '\nABORT: %s\n' "$*" >&2; exit 1; }

# Files that must lose the name but stay in the tree (rewritten in place).
# Files that cannot be rewritten (rendered images, built PDFs) are untracked instead.
UNTRACK=(
  docs/screenshot-zoomed.png
  docs/screenshot-hover.png
  papers/Asterism_SSRN_revised.pdf
  papers/Asterism_workshop_paper.pdf
)

# ─── 1. preflight ────────────────────────────────────────────────────────────
say "1/8  Preflight"
[ "$(git rev-parse --abbrev-ref HEAD)" = "$BRANCH" ] || die "not on branch $BRANCH"
git diff --quiet        || die "unstaged changes present — commit or stash first"
git diff --cached --quiet || die "staged changes present — commit or stash first"
[ -f "$STAMP" ] && die "restore point already exists ($(cat "$STAMP")) — the repo looks already sanitized; run ./restore.sh first"

git fetch -q origin
read -r behind ahead < <(git rev-list --left-right --count "origin/$BRANCH...HEAD")
[ "$behind" = 0 ] && [ "$ahead" = 0 ] || die "local and origin/$BRANCH diverge (behind=$behind ahead=$ahead) — sync first"

BASE="$(git rev-parse HEAD)"
ok "on $BRANCH, clean, level with origin at ${BASE:0:7}"

# Pick a PDF text extractor NOW, not at step 4. Verifying the tracked PDFs is
# not optional, so a missing extractor must stop the run before anything is
# mutated rather than half way through it.
if python3 -c 'import pypdfium2' 2>/dev/null; then
  PDFTEXT=pypdfium2
elif command -v pdftotext >/dev/null 2>&1; then
  PDFTEXT=pdftotext
else
  die "no PDF text extractor found — install one, then re-run:
       pip install pypdfium2      (or)  brew install poppler
     The tracked PDFs must be checked for the name; refusing to skip that."
fi
ok "PDF text extractor: $PDFTEXT"

# From here on the tree gets mutated. Preflight proved it was clean, so if any
# later stage fails we can safely put every file back and leave no half-run
# state behind — that is what made the previous failure need manual cleanup.
COMMITTED=0
rollback() {
  [ "$COMMITTED" = 1 ] && return 0
  git reset -q 2>/dev/null || true
  git checkout -q -- . 2>/dev/null || true
  rm -f "$STAMP"
  printf '  ..  rolled back to %s — tree is clean, safe to re-run\n' "${BASE:0:7}" >&2
}
trap rollback EXIT

# ─── 2. rewrite identity strings in tracked text files ───────────────────────
say "2/8  Rewriting identity strings in tracked text files"
MODIFIED="$(
python3 - "$PLACEHOLDER" "$ANON_URL" <<'PY'
import re, subprocess, sys
placeholder, anon_url = sys.argv[1], sys.argv[2]
bare_url = anon_url.split("://", 1)[1]

files = subprocess.run(["git", "ls-files"], capture_output=True, text=True).stdout.splitlines()

# Ordered: longest / most specific first, so a later rule never eats a earlier one.
RULES = [
    ("https://github.com/biditdas18/asterism", anon_url),
    ("github.com/biditdas18/asterism",         bare_url),
    ("https://github.com/biditdas18",          anon_url),
    ("github.com/biditdas18",                  bare_url),
    ("biditdas18",                             "anonymous"),
    ("biditdas",                               "anonymous"),
    ("Bidit Das",                              placeholder),
    ("Bidit",                                  placeholder),
]

changed = []
for f in files:
    try:
        s = open(f, encoding="utf-8").read()
    except (UnicodeDecodeError, IsADirectoryError, FileNotFoundError):
        continue          # binary or absent — handled by the untrack list
    orig = s
    for old, new in RULES:
        s = s.replace(old, new)
    # Comment out README embeds of the two images this run untracks, so the
    # mirror shows no broken-image icons.
    if f == "README.md":
        s = re.sub(r'^(!\[[^\]]*\]\(docs/screenshot-(?:zoomed|hover)\.png\))$',
                   r'<!-- \1 -->', s, flags=re.M)
        # A 4open.science URL is not git-cloneable, so do not hand the reader
        # a command that cannot work. Keep the instruction, drop the address.
        s = s.replace("git clone " + anon_url, "git clone <repository-url>")
    if s != orig:
        open(f, "w", encoding="utf-8").write(s)
        changed.append(f)

print("\n".join(changed))
PY
)"
[ -n "$MODIFIED" ] || die "no files were modified — nothing matched; check the rules"
while IFS= read -r f; do ok "rewrote $f"; done <<< "$MODIFIED"

# ─── 3. untrack files whose identity cannot be rewritten ─────────────────────
say "3/8  Untracking files that render or embed the name (kept on disk)"
for f in "${UNTRACK[@]}"; do
  if git ls-files --error-unmatch "$f" >/dev/null 2>&1; then
    git rm --cached --quiet "$f"
    ok "untracked $f  (still on disk: $([ -f "$f" ] && echo yes || echo NO))"
  else
    ok "$f already untracked"
  fi
done

# ─── 4. verify the tree is clean BEFORE committing ───────────────────────────
say "4/8  Verifying the staged tree carries no identity"
LEFT="$(git ls-files -z | xargs -0 grep -lIiE 'bidit' 2>/dev/null || true)"
[ -z "$LEFT" ] || die "identity string still present in: $LEFT"
ok "no 'bidit' in any tracked text file"

for f in $(git ls-files | grep -E '\.pdf$' || true); do
  if [ "$PDFTEXT" = pypdfium2 ]; then
    hits="$(python3 -c "
import pypdfium2 as p, re, sys
d = p.PdfDocument(sys.argv[1])
t = ' '.join(d[i].get_textpage().get_text_range() for i in range(len(d)))
print(len(re.findall(r'(?i)bidit', t)) + (1 if 'bidit' in (d.get_metadata_value('Author') or '').lower() else 0))
" "$f")"
  else
    # page text + document metadata, both checked
    hits="$( { pdftotext -q "$f" - 2>/dev/null; pdfinfo "$f" 2>/dev/null; } \
             | grep -ciE 'bidit' || true )"
  fi
  [ "$hits" = 0 ] || die "$f still contains the name ($hits hits)"
  ok "$f clean"
done

for f in $(git ls-files docs/ | grep -Ei '\.(png|gif|jpg)$' || true); do
  [ "$f" = "docs/asterism.gif" ] || die "unexpected tracked image $f — verify it shows no name"
done
ok "docs/ tracked images: only asterism.gif (Alex demo seed)"

python3 -m compileall -q crawler.py tests/ >/dev/null || die "substitution broke Python syntax"
ok "crawler.py and tests/ still compile"

# ─── 5. secret scan (project rule: never push without one) ───────────────────
say "5/8  Secret scan"
git add -- $MODIFIED
SECRETS="$(git diff --cached -U0 \
  | grep -E '^\+' | grep -v '^+++' \
  | grep -EiI '(api[_-]?key|secret|passwd|password|bearer |sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36})' \
  || true)"
[ -z "$SECRETS" ] || { printf '%s\n' "$SECRETS"; die "possible secret in staged diff"; }
if git ls-files | grep -qx '\.env'; then die ".env is tracked"; fi
ok "no credential patterns in the staged diff; no tracked .env"

# ─── 6. commit ───────────────────────────────────────────────────────────────
say "6/8  Commit"
printf '%s\n' "$BASE" > "$STAMP"
git commit -q -m "chore: drop generated assets pending a docs refresh

Temporarily removes two screenshots and two built PDFs from the tree and
normalises author strings in text files. Reverted by the follow-up commit."
COMMITTED=1        # disarm the rollback trap: past this point the run is real
ok "committed $(git rev-parse --short HEAD)  (restore point ${BASE:0:7} saved to .git/anon_restore_point)"

# ─── 7. push ─────────────────────────────────────────────────────────────────
if [ "$PUSH" != "1" ]; then
  say "7/8  Push skipped (PUSH=0)"
else
  say "7/8  Push"
  git push --dry-run origin "$BRANCH"
  if [ "$ASSUME_YES" != 1 ]; then
    read -r -p "  push the above to origin/$BRANCH? [y/N] " reply
    [ "$reply" = y ] || [ "$reply" = Y ] || die "not pushed (local commit stands; ./restore.sh undoes it)"
  fi
  git push -q origin "$BRANCH"
  ok "pushed"

  # ─── 8. verify what the SERVER actually has ────────────────────────────────
  say "8/8  Verifying the remote tree"
  git fetch -q origin
  for f in "${UNTRACK[@]}"; do
    if git ls-tree -r --name-only "origin/$BRANCH" | grep -qx "$f"; then
      die "$f is STILL on the remote"
    fi
  done
  ok "removed files absent from origin/$BRANCH"
  for f in $(git ls-tree -r --name-only "origin/$BRANCH" | grep -E '\.(md|py|tex|txt)$|^LICENSE$'); do
    if git show "origin/$BRANCH:$f" | grep -qiI 'bidit'; then die "remote $f still contains the name"; fi
  done
  ok "no identity string in any text file on origin/$BRANCH"
fi

say "Done — resync the Anonymous GitHub mirror now, then run ./restore.sh"
cat <<'NOTE'

  While the repo is in this state:
    - do NOT rebuild the PDFs. papers/asterism.tex currently has "Anonymous"
      in \author/pdfauthor and the anonymised URL in BOTH \ifanon branches,
      so a named build would come out wrong. restore.sh puts it back.
    - do NOT run `git add -A`. Four files are deliberately untracked and it
      would silently re-add them.
  Not covered by this script, because a tree rewrite cannot reach it:
    commit author metadata (every commit is authored by your name/email),
    git history, and the repository owner/URL itself. The mirror serves the
    tree, not the history, so this is sufficient for the mirror only.
NOTE
