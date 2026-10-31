#!/usr/bin/env bash
# Install rustup + Verus (prebuilt x86-linux release, bundles z3) into ./tools/.
set -euo pipefail

VERUS_TAG="${VERUS_TAG:-release/0.2026.10.26.d17fbd0}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
TOOLS="$ROOT/tools"
mkdir -p "$TOOLS"

if ! command -v rustup >/dev/null 2>&1 && [ ! -x "$HOME/.cargo/bin/rustup" ]; then
  curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --default-toolchain none --profile minimal
fi
export PATH="$HOME/.cargo/bin:$PATH"

VER="${VERUS_TAG#release/}"
ZIP="verus-${VER}-x86-linux.zip"
if [ ! -x "$TOOLS/verus-x86-linux/verus" ]; then
  curl -sSfL -o "$TOOLS/$ZIP" "https://github.com/verus-lang/verus/releases/download/${VERUS_TAG}/${ZIP}"
  python3 -c "import zipfile,sys; zipfile.ZipFile(sys.argv[1]).extractall(sys.argv[2])" "$TOOLS/$ZIP" "$TOOLS" && rm "$TOOLS/$ZIP"
  chmod +x "$TOOLS"/verus-x86-linux/{verus,rust_verify,z3,cargo-verus} 2>/dev/null || true
fi

# Verus prints the toolchain it needs; install it.
TC="$(grep -oE '[0-9]+\.[0-9]+\.[0-9]+-x86_64-unknown-linux-gnu' "$TOOLS/verus-x86-linux/version.json" | head -1 || true)"
if [ -n "$TC" ]; then
  rustup toolchain install "$TC" --profile minimal
fi

# The bundled z3 needs glibc >= 2.38. Use the manylinux_2_27 build from the
# z3-solver wheel instead, so the install also works on Ubuntu 22.04.
Z3_VERSION="${Z3_VERSION:-4.16.0}"
Z3_DIR="$TOOLS/z3-$Z3_VERSION"
if [ ! -x "$Z3_DIR/z3" ]; then
  mkdir -p "$Z3_DIR"
  python3 -m pip download --no-deps --only-binary=:all: --platform manylinux_2_27_x86_64 \
    --python-version 3.12 "z3-solver==$Z3_VERSION.0" -d "$Z3_DIR" -q
  python3 -I -c "import zipfile,glob,sys; z=zipfile.ZipFile(glob.glob(sys.argv[1]+'/*.whl')[0]); n=[x for x in z.namelist() if x.endswith('bin/z3')][0]; open(sys.argv[1]+'/z3','wb').write(z.read(n))" "$Z3_DIR"
  chmod +x "$Z3_DIR/z3" && rm -f "$Z3_DIR"/*.whl
fi
export VERUS_Z3_PATH="$Z3_DIR/z3"

cat > "$TOOLS/smoke.rs" <<'EOF'
use vstd::prelude::*;
verus! {
fn add1(x: u32) -> (r: u32) requires x < 100 ensures r == x + 1 { x + 1 }
fn main() {}
}
EOF
"$TOOLS/verus-x86-linux/verus" "$TOOLS/smoke.rs"
echo "Verus OK: $TOOLS/verus-x86-linux/verus (z3: $VERUS_Z3_PATH)"
