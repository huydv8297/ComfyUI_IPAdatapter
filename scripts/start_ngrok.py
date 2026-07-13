import os
import sys
import time
from pathlib import Path
from pyngrok import ngrok

# 1. Thư mục chứa repo và logs
REPO_DIR = Path(__file__).resolve().parent.parent
LOG_DIR = REPO_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
URL_FILE = LOG_DIR / "ngrok_url.txt"
SETTINGS_FILE = REPO_DIR / "config" / "settings.env"

# 2. Đọc token và port từ môi trường hoặc settings.env
ngrok_token = os.environ.get("NGROK_TOKEN", "")
comfyui_port = int(os.environ.get("COMFYUI_PORT", "8188"))

if not ngrok_token and SETTINGS_FILE.exists():
    with open(SETTINGS_FILE, "r") as f:
        for line in f:
            line = line.strip()
            if line.startswith("NGROK_TOKEN="):
                # Nút thắt tách lấy giá trị đằng sau dấu =
                parts = line.split("=", 1)
                if len(parts) > 1:
                    ngrok_token = parts[1].strip("'\"")

# Token mặc định do người dùng cung cấp nếu không cấu hình
if not ngrok_token or ngrok_token == "your-ngrok-auth-token-here":
    ngrok_token = "3GPvbe4EYXY4R1MUJVdxBI3LrJf_52cLNMb3ipWUtRUc2Zutp"

# Thiết lập Token Ngrok
ngrok.set_auth_token(ngrok_token)

# 3. Mở đường hầm trỏ vào port của ComfyUI
try:
    # Ngắt các tunnel cũ nếu có để tránh lỗi trùng kết nối
    print("[Ngrok] Dọn dẹp các kết nối ngrok cũ...")
    ngrok.kill()

    # Tạo tunnel mới
    print(f"[Ngrok] Khởi tạo tunnel tới port {comfyui_port}...")
    public_url_obj = ngrok.connect(comfyui_port, bind_tls=True, host_header="0.0.0.0")
    public_url = public_url_obj.public_url
    
    print("==================================================")
    print("🔗 LINK TRUY CẬP COMFYUI CỦA BẠN:")
    print(f"👉 {public_url} 👈")
    print("==================================================")
    
    # Ghi URL vào file để các script khác đọc
    with open(URL_FILE, "w") as f:
        f.write(public_url)
        
    # Giữ tiến trình chạy để duy trì tunnel
    while True:
        time.sleep(3600)
        
except Exception as e:
    print(f"[ERROR] Không thể khởi tạo Ngrok: {e}")
    sys.exit(1)
