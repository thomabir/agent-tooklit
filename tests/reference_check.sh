#!/bin/sh
# End-to-end check against the reference project. Reads its committed outputs only.
# Usage: sh tests/reference_check.sh <reference project folder>
set -eu
HERE="$(cd "$(dirname "$0")/.." && pwd)"
REF="$(cd "$1" && pwd)"
OUT="$HERE/build/reference"
cd "$HERE"
uv run --python 3.12 hwkit bambu flatten --out "$OUT/profiles"
uv run --python 3.12 hwkit bambu template --profiles "$OUT/profiles" --out "$OUT/template.json" --work "$OUT/template-work"
uv run --python 3.12 python - "$OUT/template.json" "$REF/case/bambu-project-settings.config" <<'EOF'
import json, sys
new, ref = (json.load(open(p)) for p in sys.argv[1:3])
diff = sorted(k for k in set(new) | set(ref) if new.get(k) != ref.get(k))
print(f"template keys different from reference: {diff}")
EOF
uv run --python 3.12 hwkit bambu verify "$REF/case/out/print-case.3mf" --labels "$REF/case/out/print-lid-labels.stl" --body "$REF/case/out/print-lid.stl" --out "$OUT/verify"
