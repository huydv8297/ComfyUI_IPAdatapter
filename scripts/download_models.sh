#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
COMFYUI_DIR="$REPO_DIR/ComfyUI"

echo "[Download Models] Tạo thư mục models..."
mkdir -p "$COMFYUI_DIR/models/unet"
mkdir -p "$COMFYUI_DIR/models/clip"
mkdir -p "$COMFYUI_DIR/models/vae"
mkdir -p "$COMFYUI_DIR/models/ipadapter"
mkdir -p "$COMFYUI_DIR/models/controlnet"

download_file() {
    local url="$1"
    local output_dir="$2"
    local filename="$3"
    
    if [ -f "$output_dir/$filename" ]; then
        echo "  → $filename đã tồn tại, bỏ qua..."
        return 0
    fi
    
    echo "  → Downloading $filename..."
    wget -q --show-progress -O "$output_dir/$filename" "$url"
    
    # Verify file không bị lỗi (check size > 1MB)
    local size=$(stat -c%s "$output_dir/$filename" 2>/dev/null || stat -f%z "$output_dir/$filename" 2>/dev/null)
    if [ "$size" -lt 1048576 ]; then
        echo "  LỖI: $filename quá nhỏ (${size} bytes), download thất bại!"
        rm -f "$output_dir/$filename"
        return 1
    fi
    echo "  → OK! ($(( size / 1048576 )) MB)"
}

echo ""
echo "=================================================="
echo "  Download FLUX.1-schnell + IPAdapter models"
echo "=================================================="
echo ""

# 1. FLUX.1-schnell UNET (fp8)
download_file \
    "https://huggingface.co/Kijai/flux-fp8/resolve/main/flux1-schnell-fp8.safetensors" \
    "$COMFYUI_DIR/models/unet" \
    "flux1-schnell-fp8.safetensors"

# 2. CLIP-L
download_file \
    "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/clip_l.safetensors" \
    "$COMFYUI_DIR/models/clip" \
    "clip_l.safetensors"

# 3. T5-XXL fp8
download_file \
    "https://huggingface.co/comfyanonymous/flux_text_encoders/resolve/main/t5xxl_fp8.safetensors" \
    "$COMFYUI_DIR/models/clip" \
    "t5xxl_fp8.safetensors"

# 4. VAE (ae.safetensors)
download_file \
    "https://huggingface.co/black-forest-labs/FLUX.1-schnell/resolve/main/ae.safetensors" \
    "$COMFYUI_DIR/models/vae" \
    "ae.safetensors"

# 5. IPAdapter FLUX fp8
download_file \
    "https://huggingface.co/h94/IP-Adapter-Flux/resolve/main/ip-adapter-flux-fp8.safetensors" \
    "$COMFYUI_DIR/models/ipadapter" \
    "ip-adapter-flux-fp8.safetensors"

echo ""
echo "=================================================="
echo "  Download hoàn tất!"
echo "=================================================="

# Show tổng dung lượng
echo ""
echo "Thống kê models:"
echo "  UNET:       $(ls -lh "$COMFYUI_DIR/models/unet/" 2>/dev/null | awk '{print $5, $NF}')"
echo "  CLIP:       $(ls -lh "$COMFYUI_DIR/models/clip/" 2>/dev/null | awk '{print $5, $NF}')"
echo "  VAE:        $(ls -lh "$COMFYUI_DIR/models/vae/" 2>/dev/null | awk '{print $5, $NF}')"
echo "  IPAdapter:  $(ls -lh "$COMFYUI_DIR/models/ipadapter/" 2>/dev/null | awk '{print $5, $NF}')"
echo ""
echo "Tổng dung lượng:"
du -sh "$COMFYUI_DIR/models/unet" "$COMFYUI_DIR/models/clip" "$COMFYUI_DIR/models/vae" "$COMFYUI_DIR/models/ipadapter" 2>/dev/null