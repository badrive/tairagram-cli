#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$(realpath "$0")")"
APP_DIR="$(pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  echo 'Python 3 is required.' >&2; exit 1
fi
if ! python3 -c 'import sys; sys.exit(sys.version_info < (3,10))'; then
  echo 'Python 3.10+ is required.' >&2; exit 1
fi

printf '\nInstalling Tairagram into %s\n\n' "$APP_DIR"
if ! python3 -m venv .venv; then
  echo 'Could not create a Python venv. Ubuntu: sudo apt install python3-venv' >&2
  exit 1
fi
"$APP_DIR/.venv/bin/python" -m pip install --disable-pip-version-check -r "$APP_DIR/requirements.txt"
mkdir -p "$HOME/.local/bin"
cat > "$HOME/.local/bin/tairagram" <<EOF
#!/usr/bin/env bash
exec "$APP_DIR/.venv/bin/python" "$APP_DIR/tairagram.py" "\$@"
EOF
chmod 755 "$HOME/.local/bin/tairagram"
printf '\nInstalled. Run: tairagram\n'
case ":$PATH:" in
  *":$HOME/.local/bin:"*) ;;
  *) printf 'If command not found, run: export PATH="$HOME/.local/bin:$PATH"\n';;
esac
printf 'Downloads will be saved under: %s/tairagram_downloads\n' "$APP_DIR"
