#!/usr/bin/env bash
#
# Publish the current version of JellyELEC as a GitHub release, which boxes pick up through
# Settings > Check for updates (and their daily check).
#
# Usage:   bash tools/release.sh
#
# It builds the add-on zip, tags the commit with the version from addon.xml (v0.0.43, say),
# pushes the tag, and creates the release with the zip attached. That last step needs the
# GitHub command-line tool, gh (https://cli.github.com), signed in with "gh auth login";
# without it, the script says how to finish the release on github.com instead.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

fail() { echo "Error: $*" >&2; exit 1; }

VERSION="$(python3 -c "import xml.etree.ElementTree as e; print(e.parse('script.jellyelec/addon.xml').getroot().get('version'))")"
TAG="v$VERSION"
ZIP="dist/script.jellyelec-$VERSION.zip"

# Only release what's committed and pushed, so the release matches the code on GitHub.
[ -z "$(git status --porcelain)" ] || fail "there are uncommitted changes. Commit them first."
git fetch --quiet origin
[ "$(git rev-parse HEAD)" = "$(git rev-parse @{u})" ] || fail "this commit isn't pushed yet. Run: git push"
git rev-parse -q --verify "refs/tags/$TAG" >/dev/null && fail "$TAG already exists. Bump the version in addon.xml first."

echo "Releasing JellyELEC $VERSION"
python3 tools/build.py
git tag -a "$TAG" -m "JellyELEC $VERSION"
git push --quiet origin "$TAG"

if command -v gh >/dev/null; then
    gh release create "$TAG" "$ZIP" --title "JellyELEC $VERSION" --generate-notes
    echo "Done: boxes will find $VERSION under Settings > Check for updates."
else
    echo
    echo "Tag $TAG is pushed. To finish the release on github.com:"
    echo "  1. Open https://github.com/fattykidd/jellyelec/releases/new?tag=$TAG"
    echo "  2. Title: JellyELEC $VERSION (click 'Generate release notes' for the change list)"
    echo "  3. Attach $REPO_DIR/$ZIP"
    echo "  4. Click 'Publish release'."
fi
