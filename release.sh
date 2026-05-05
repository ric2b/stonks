#!/usr/bin/env bash
set -euo pipefail

if [ $# -ne 1 ]; then
  echo "Usage: $0 <version>"
  echo "Example: $0 0.2.0"
  exit 1
fi

VERSION="$1"

if ! echo "$VERSION" | grep -qE '^[0-9]+\.[0-9]+\.[0-9]+$'; then
  echo "Error: version must be in semver format (e.g. 0.2.0)"
  exit 1
fi

if [ -n "$(git status --porcelain)" ]; then
  echo "Error: working tree is not clean. Commit or stash changes first."
  exit 1
fi

CURRENT=$(grep '^version' pyproject.toml | head -1 | sed 's/.*"\(.*\)"/\1/')
if [ "$CURRENT" = "$VERSION" ]; then
  echo "Error: version is already $VERSION"
  exit 1
fi

tmp=$(mktemp)
sed "s/^version = \".*\"/version = \"$VERSION\"/" pyproject.toml > "$tmp"
mv "$tmp" pyproject.toml

git add pyproject.toml
git commit -m "Release v$VERSION"
git tag "v$VERSION"

echo ""
echo "Created commit and tag v$VERSION."
echo "Run the following to push the release:"
echo ""
echo "  git push && git push --tags"
