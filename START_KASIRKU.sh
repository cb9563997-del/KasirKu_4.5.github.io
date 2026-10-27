#!/data/data/com.termux/files/usr/bin/bash
set -e
cd "$(dirname "$0")"
echo "=== KasirKu Pro 4.5 ==="
if ! command -v python >/dev/null 2>&1; then
  echo "Python belum ada. Jalankan: pkg install python"
  exit 1
fi
python -m pip install -r requirements.txt
echo
echo "Membuka server KasirKu..."
python app.py
