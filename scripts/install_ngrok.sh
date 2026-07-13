#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "[Ngrok] Kiểm tra ngrok..."

if command -v ngrok &>/dev/null; then
    echo "  → ngrok đã được cài: $(ngrok version)"
    exit 0
fi

echo "  → Download ngrok..."
cd /tmp
curl -sSL https://ngrok-agent.s3.amazonaws.com/ngrok.asc \
    | sudo tee /etc/apt/trusted.gpg.d/ngrok.asc >/dev/null || true

# Cài đặt ngrok vào user directory
ARCH=$(uname -m)
if [ "$ARCH" = "x86_64" ]; then
    wget -q https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-amd64.tgz -O ngrok.tgz
elif [ "$ARCH" = "aarch64" ]; then
    wget -q https://bin.equinox.io/c/bNyj1mQVY4c/ngrok-v3-stable-linux-arm64.tgz -O ngrok.tgz
else
    echo "  LỖI: Architecture không hỗ trợ: $ARCH"
    exit 1
fi

tar xzf ngrok.tgz -C "$REPO_DIR"
rm ngrok.tgz

# Thêm vào PATH thông qua ~/.bashrc
if ! grep -q "$REPO_DIR" ~/.bashrc 2>/dev/null; then
    echo "export PATH=\"\$PATH:$REPO_DIR\"" >> ~/.bashrc
    echo "  → Đã thêm $REPO_DIR vào PATH trong ~/.bashrc"
fi

echo "  → ngrok đã cài tại $REPO_DIR/ngrok"
echo ""
echo "  ⚠  Tiếp theo: Cấu hình token ngrok"
echo "     Mở https://dashboard.ngrok.com/get-started/your-authtoken"
echo "     Chạy: $REPO_DIR/ngrok config add-authtoken YOUR_TOKEN"
echo "     Hoặc sửa file config/settings.env"