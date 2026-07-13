#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
VENV_DIR="$REPO_DIR/venv"

echo "[Ngrok] Cài đặt thư viện pyngrok..."

# Kiểm tra và cài đặt pyngrok vào virtualenv
if [ -f "$VENV_DIR/bin/pip" ]; then
    echo "  → Đang cài đặt vào virtualenv..."
    "$VENV_DIR/bin/pip" install pyngrok
else
    echo "  → Đang cài đặt toàn cục..."
    pip3 install pyngrok || pip install pyngrok
fi

echo "  → Cài đặt pyngrok thành công!"
echo ""
echo "  ⚠  Tiếp theo: Cấu hình token ngrok (nếu có) trong config/settings.env"
echo "     Hoặc hệ thống sẽ tự động dùng token mặc định được thiết lập."