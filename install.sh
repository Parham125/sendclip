#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="${HOME}/.local/bin"
TARGET="${BIN_DIR}/sendclip"
VENV_DIR="${SCRIPT_DIR}/.venv"

mkdir -p "${BIN_DIR}"
chmod +x "${SCRIPT_DIR}/sendclip.py"
python3.13 -m venv "${VENV_DIR}"
"${VENV_DIR}/bin/pip" install -r "${SCRIPT_DIR}/requirements.txt"

cat > "${TARGET}" <<EOF
#!/usr/bin/env bash
exec "${VENV_DIR}/bin/python" "${SCRIPT_DIR}/sendclip.py" "\$@"
EOF

chmod +x "${TARGET}"
rm -f "${BIN_DIR}/sendclip-alias"
printf 'Installed sendclip to %s\n' "${TARGET}"
