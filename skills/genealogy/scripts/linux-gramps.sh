#!/usr/bin/env bash
# Install Gramps on this container (Ubuntu 26.04, arm64, Python 3.14).
#
# Deterministic and idempotent: fixed package list, pinned gramps version,
# no timestamps/randomness. Safe to re-run — apt and pip no-op on
# already-installed items, and the venv is not recreated if it exists.
#
# Verified procedure: see /workspace/LINUX_GRAMPS.md
set -euo pipefail

VENV="${VENV:-/home/user/gramps-venv}"
GRAMPS_VERSION="${GRAMPS_VERSION:-6.0.8}"

# Exact package list — do not substitute. glib uses the t64 suffix on 26.04.
APT_PACKAGES=(
  # 1. Runtime libraries
  libglib2.0-0t64 libgirepository-1.0-1 libcairo2 \
  libpango-1.0-0 libpangocairo-1.0-0 libgdk-pixbuf-2.0-0 \
  gir1.2-gtk-3.0 fontconfig fonts-dejavu-core
  # 2. Prebuilt Python bindings — PyPI publishes no Linux wheels for
  #    pycairo/PyGObject/PyICU, so these must come from apt, not pip.
  python3-gi python3-gi-cairo python3-cairo \
  python3-pil python3-icu python3-pycountry python3-imagesize
  # 3. poppler-utils — pdftoppm, needed to visually verify generated PDFs
  poppler-utils
)

SUDO=""
if [ "$(id -u)" -ne 0 ]; then
  SUDO="sudo"
fi

echo "==> apt: runtime libraries + prebuilt Python bindings"
$SUDO apt-get update -qq
$SUDO apt-get install -y "${APT_PACKAGES[@]}"

echo "==> venv: $VENV (created only if missing)"
if [ ! -x "$VENV/bin/python" ]; then
  # --system-site-packages lets the venv see the apt bindings above.
  python3 -m venv --system-site-packages "$VENV"
fi

echo "==> pip: gramps==$GRAMPS_VERSION (plain, NOT [all]/[gui]/[i18n] extras)"
# Plain 'gramps' avoids the PyPI copies of pycairo/PyGObject/PyICU,
# which would be compiled from source.
"$VENV/bin/pip" install -q "gramps==$GRAMPS_VERSION"

echo "==> verify"
GRAMPS_VERSION="$GRAMPS_VERSION" "$VENV/bin/python" - <<'EOF'
import os
import gramps, cairo, gi
from gramps.version import VERSION
expected = os.environ["GRAMPS_VERSION"]
assert VERSION == expected, f"expected gramps {expected}, got {VERSION}"
print(f"OK: gramps {VERSION}, cairo, gi all import")
EOF
"$VENV/bin/gramps" --version | sed -n '1,5p'

echo
echo "Done. Before using the genealogy skill scripts, activate the venv:"
echo "  source $VENV/bin/activate"
