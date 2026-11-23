#!/usr/bin/env bash
# One-shot: creates the public GitHub repo VTLO/VTLOdr3m3r (if missing) and pushes everything.
# Usage:  ./push-to-github.sh [owner] [repo]        (defaults: VTLO VTLOdr3m3r)
# Auth (any one):  `gh auth login` already done  |  export GITHUB_TOKEN=ghp_xxx (scope: repo)  |  git credential helper
set -euo pipefail
OWNER="${1:-VTLO}"; REPO="${2:-VTLOdr3m3r}"; DESC="VTLOdr3m3r — paranormal research · New Era warfare studies (Operation Lightning)"
cd "$(dirname "$0")"
command -v git >/dev/null || { echo "git is required (Termux: pkg install git)"; exit 1; }
[ -d .git ] || git init -q -b main
git config user.name  >/dev/null 2>&1 || git config user.name  "$OWNER"
git config user.email >/dev/null 2>&1 || git config user.email "$OWNER@users.noreply.github.com"
git add -A; git diff --cached --quiet || git commit -qm "VTLOdr3m3r — paranormal research / New Era warfare studies"
git branch -M main
TOKEN="${GITHUB_TOKEN:-${GH_TOKEN:-}}"
exists() { git ls-remote "https://github.com/$OWNER/$REPO.git" >/dev/null 2>&1; }
if ! exists; then
  echo "Creating public repo $OWNER/$REPO …"
  if command -v gh >/dev/null && gh auth status >/dev/null 2>&1; then
    gh repo create "$OWNER/$REPO" --public --description "$DESC" >/dev/null
  elif [ -n "$TOKEN" ] && command -v curl >/dev/null; then
    code=$(curl -s -o /tmp/ghcreate.json -w '%{http_code}' -X POST -H "Authorization: Bearer $TOKEN" -H "Accept: application/vnd.github+json" \
      https://api.github.com/user/repos -d "{\"name\":\"$REPO\",\"description\":\"$DESC\",\"private\":false}")
    [ "$code" = 201 ] || [ "$code" = 422 ] || { echo "GitHub API error $code:"; cat /tmp/ghcreate.json; exit 1; }
  else
    echo "No GitHub auth found. Either run 'gh auth login', or export GITHUB_TOKEN=<token with repo scope>,"
    echo "or create the empty public repo at https://github.com/new (name: $REPO) and re-run."; exit 1
  fi
fi
URL="https://github.com/$OWNER/$REPO.git"
git remote remove origin 2>/dev/null || true
git remote add origin "$URL"
if [ -n "$TOKEN" ]; then
  git -c "http.extraheader=Authorization: Basic $(printf 'x-access-token:%s' "$TOKEN" | base64 | tr -d '\n')" push -u origin main
else
  git push -u origin main
fi
echo "✔ Done: https://github.com/$OWNER/$REPO"
echo "  Optional — web app on GitHub Pages: Settings → Pages → Source: GitHub Actions"
