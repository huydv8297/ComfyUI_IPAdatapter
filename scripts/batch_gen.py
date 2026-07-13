#!/usr/bin/env python3
"""
Batch generation script: 20 style images × 10 prompts = 200 images
Gọi ComfyUI API để queue workflow cho từng ảnh.

Cách dùng:
  python scripts/batch_gen.py
  python scripts/batch_gen.py --num-per-style 5 --seed-start 100
  python scripts/batch_gen.py --prompts "Prompt 1" "Prompt 2" ...
  python scripts/batch_gen.py --dry-run  # chỉ show kế hoạch
"""

import os
import sys
import json
import time
import argparse
import logging
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mặc định
# ---------------------------------------------------------------------------
REPO_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SETTINGS = REPO_DIR / "config" / "settings.env"
WORKFLOW_TEMPLATE = REPO_DIR / "config" / "workflows" / "flux_ipadapter_batch.json"

# Prompts mẫu (20 prompts khác nhau cho 20 ảnh style)
DEFAULT_PROMPTS = [
    "A majestic mountain landscape at sunset, golden light, highly detailed, 8k",
    "A serene beach with crystal clear water, palm trees, tropical vibe, summer",
    "A bustling cyberpunk city street at night, neon lights, rain reflections, futuristic",
    "A cozy cabin in the snowy woods, warm light from windows, winter atmosphere",
    "A lush enchanted forest with glowing mushrooms, magical ambiance, fairy tale",
    "A minimalist zen garden with raked sand and bonsai trees, peaceful, serene",
    "A vibrant marketplace in Marrakech, colorful textiles, spices, bustling crowd",
    "A medieval castle on a cliff overlooking the sea, foggy morning, epic",
    "A steampunk airship flying above floating islands, gears and propellers, adventure",
    "A tranquil Japanese temple surrounded by cherry blossoms, spring, harmonious",
    "An aurora borealis over a frozen lake in Iceland, starry night, magical",
    "A roaring waterfall in a tropical jungle, mist, rainbow, lush vegetation",
    "A futuristic space station orbiting a ringed planet, vast cosmos, sci-fi",
    "A cozy bookstore cafe with warm lighting, bookshelves, cats, relaxing",
    "A desert oasis with camels and tents, golden dunes, sunset, nomadic",
    "An underwater coral reef with colorful fish, sun rays filtering through water",
    "A vintage 1950s diner at night, neon sign, classic cars, retro Americana",
    "A bamboo forest path with light filtering through, peaceful, natural, harmonious",
    "A grand library with spiral staircases, ancient tomes, stained glass windows",
    "A lavender field in Provence at golden hour, rolling hills, rustic farmhouse",
]


def load_settings(settings_path: Path) -> dict:
    """Load settings từ file .env"""
    settings = {}
    if settings_path.exists():
        with open(settings_path) as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    settings[key.strip()] = value.strip().strip('"').strip("'")
    return settings


# ---------------------------------------------------------------------------
# ComfyUI API helpers
# ---------------------------------------------------------------------------

def upload_image(image_path: Path, server_address: str = "127.0.0.1:8188") -> Optional[str]:
    """
    Upload ảnh lên ComfyUI qua /upload/image endpoint.
    Trả về tên file đã upload (để reference trong workflow).
    """
    import http.client
    import mimetypes

    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    filename = image_path.name

    # Đọc nội dung ảnh
    with open(image_path, "rb") as f:
        file_data = f.read()

    # Tạo multipart body
    body = []
    body.append(f"--{boundary}\r\n".encode())
    body.append(f'Content-Disposition: form-data; name="image"; filename="{filename}"\r\n'.encode())
    body.append(f"Content-Type: {mimetypes.guess_type(filename)[0] or 'image/png'}\r\n".encode())
    body.append(b"\r\n")
    body.append(file_data)
    body.append(b"\r\n")
    body.append(f"--{boundary}--\r\n".encode())

    data = b"".join(body)
    content_type = f"multipart/form-data; boundary={boundary}"

    url = f"http://{server_address}/upload/image"
    req = urllib.request.Request(url, data=data)
    req.add_header("Content-Type", content_type)

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            uploaded_name = result.get("name", filename)
            log.debug(f"  Uploaded: {uploaded_name}")
            return uploaded_name
    except Exception as e:
        log.error(f"  Lỗi upload ảnh {filename}: {e}")
        return None


def queue_prompt(prompt_workflow: dict, server_address: str = "127.0.0.1:8188") -> Optional[str]:
    """Gửi workflow tới ComfyUI API và trả về prompt_id"""
    url = f"http://{server_address}/prompt"
    data = json.dumps({"prompt": prompt_workflow}).encode("utf-8")
    headers = {"Content-Type": "application/json"}

    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return result.get("prompt_id")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")
        log.error(f"  HTTP {e.code}: {body[:300]}")
        return None
    except Exception as e:
        log.error(f"  Lỗi gửi prompt: {e}")
        return None


def wait_for_image(prompt_id: str, server_address: str = "127.0.0.1:8188", timeout: int = 300) -> Optional[bytes]:
    """Đợi ảnh được gen xong và trả về dữ liệu ảnh"""
    url = f"http://{server_address}/history/{prompt_id}"
    start = time.time()

    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(url, timeout=30) as resp:
                history = json.loads(resp.read().decode("utf-8"))
                if prompt_id in history:
                    outputs = history[prompt_id].get("outputs", {})
                    for node_id, node_output in outputs.items():
                        images = node_output.get("images", [])
                        if images:
                            img_info = images[0]
                            img_url = (
                                f"http://{server_address}/view"
                                f"?filename={img_info['filename']}"
                                f"&subfolder={img_info['subfolder']}"
                                f"&type={img_info['type']}"
                            )
                            with urllib.request.urlopen(img_url, timeout=30) as img_resp:
                                return img_resp.read()
                    # Output có images nhưng không tìm thấy? return None
                    return None
        except Exception:
            time.sleep(2)

    log.warning(f"  Timeout chờ ảnh {prompt_id}")
    return None


def load_workflow(template_path: Path) -> dict:
    """Load workflow template từ file JSON"""
    if not template_path.exists():
        log.error(f"Workflow template không tìm thấy: {template_path}")
        log.error("Hãy export workflow từ ComfyUI và lưu vào đó.")
        sys.exit(1)
    with open(template_path) as f:
        return json.load(f)


def inject_workflow(workflow: dict, image_filename: str, prompt_text: str, seed: int) -> dict:
    """
    Inject image filename, prompt, và seed vào workflow.
    Các node IDs phải match với workflow template.
    """
    workflow = json.loads(json.dumps(workflow))  # deep copy

    for node_id, node in workflow.items():
        if not isinstance(node, dict):
            continue
        cls_type = node.get("class_type", "")
        inputs = node.get("inputs", {})

        # LoadImage node - inject filename
        if cls_type == "LoadImage":
            if "image" in inputs:
                inputs["image"] = image_filename

        # CLIPTextEncode (positive prompt) - inject prompt text
        if cls_type == "CLIPTextEncode" and "text" in inputs:
            # Kiểm tra không phải negative prompt (thường là text rỗng)
            current_text = str(inputs.get("text", "")).strip()
            if current_text and current_text != "":
                inputs["text"] = prompt_text

        # RandomNoise hoặc KSampler - inject seed
        for key in ("noise_seed", "seed"):
            if key in inputs:
                inputs[key] = seed

    return workflow


def main():
    parser = argparse.ArgumentParser(description="Batch gen 200 ảnh với FLUX + IPAdapter")
    parser.add_argument("--input-dir", default=None, help="Thư mục chứa ảnh style")
    parser.add_argument("--output-dir", default=None, help="Thư mục output")
    parser.add_argument("--num-per-style", type=int, default=None, help="Số ảnh gen mỗi style (default: 10)")
    parser.add_argument("--seed-start", type=int, default=None, help="Seed bắt đầu (default: 42)")
    parser.add_argument("--server", default=None, help="ComfyUI server address (default: 127.0.0.1:8188)")
    parser.add_argument("--prompts", nargs="+", help="Danh sách prompts (mặc định 20 prompts mẫu)")
    parser.add_argument("--workflow", default=None, help="Path tới workflow JSON template")
    parser.add_argument("--dry-run", action="store_true", help="Không gọi API, chỉ show kế hoạch")
    args = parser.parse_args()

    # Load settings
    settings = load_settings(DEFAULT_SETTINGS)

    input_dir = Path(args.input_dir or settings.get("BATCH_INPUT_DIR", "./input/styles"))
    output_dir = Path(args.output_dir or settings.get("BATCH_OUTPUT_DIR", "./output"))
    num_per_style = args.num_per_style or int(settings.get("NUM_IMAGES_PER_STYLE", "10"))
    seed_start = args.seed_start or int(settings.get("SEED_START", "42"))
    server = args.server or settings.get("COMFYUI_API_URL", "127.0.0.1:8188")
    server = server.replace("http://", "").replace("https://", "")

    # Prompts
    if args.prompts:
        prompts = args.prompts
    else:
        prompts = DEFAULT_PROMPTS

    # Workflow template
    wf_path = Path(args.workflow) if args.workflow else WORKFLOW_TEMPLATE

    # Tìm ảnh style
    style_images = sorted(input_dir.glob("*"))
    style_images = [f for f in style_images if f.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp")]
    if not style_images:
        log.error(f"Không tìm thấy ảnh style nào trong {input_dir}")
        log.info(f"Hỗ trợ định dạng: .png, .jpg, .jpeg, .webp")
        log.info(f"Đặt ảnh style vào thư mục: {input_dir.resolve()}")
        sys.exit(1)

    total_expected = len(style_images) * num_per_style
    log.info(f"Tìm thấy {len(style_images)} ảnh style")
    log.info(f"Sẽ gen {num_per_style} ảnh mỗi style → tổng {total_expected} ảnh")
    log.info(f"Input:  {input_dir.resolve()}")
    log.info(f"Output: {output_dir.resolve()}")
    log.info("")

    # Tạo output dir
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load workflow template
    workflow_template = load_workflow(wf_path)
    log.info(f"Workflow: {wf_path.resolve()} ({len(workflow_template)} nodes)")

    total = total_expected
    current = 0
    failed = 0
    skipped = 0

    for img_idx, img_path in enumerate(style_images):
        style_name = img_path.stem
        log.info(f"[{img_idx + 1}/{len(style_images)}] Style: {style_name}")

        # Upload ảnh lên ComfyUI
        log.info(f"  Uploading {img_path.name}...")
        uploaded_name = upload_image(img_path, server)
        if not uploaded_name:
            log.error(f"  ✗ Không thể upload {img_path.name}, bỏ qua style này")
            failed += num_per_style
            continue

        # Prompt cho style này
        prompt = prompts[img_idx % len(prompts)]
        log.info(f"  Prompt: {prompt[:80]}...")

        for seed_offset in range(num_per_style):
            seed = seed_start + current
            current += 1

            if args.dry_run:
                log.info(f"  [DRY RUN] Seed {seed}: {style_name}_seed{seed}.png")
                continue

            # Inject vào workflow
            workflow = inject_workflow(workflow_template, uploaded_name, prompt, seed)

            # Gửi tới ComfyUI
            log.info(f"  [{current}/{total}] Queue seed={seed}...")
            prompt_id = queue_prompt(workflow, server)
            if not prompt_id:
                log.error(f"  ✗ Queue failed for seed {seed}")
                failed += 1
                continue

            # Chờ ảnh
            log.info(f"  Waiting (id={prompt_id[:8]}...)")
            img_data = wait_for_image(prompt_id, server, timeout=300)
            if img_data:
                out_path = output_dir / f"{style_name}_seed{seed}.png"
                with open(out_path, "wb") as f:
                    f.write(img_data)
                log.info(f"  ✓ {out_path.name} (size={len(img_data) // 1024}KB)")
            else:
                log.error(f"  ✗ No image for seed {seed}")
                failed += 1

            # Delay nhẹ
            time.sleep(0.3)

    # Summary
    log.info("")
    log.info("=" * 60)
    log.info("  BATCH GEN COMPLETE")
    log.info(f"  Total:     {total}")
    log.info(f"  Success:   {total - failed - skipped}")
    log.info(f"  Failed:    {failed}")
    log.info(f"  Skipped:   {skipped}")
    log.info(f"  Output:    {output_dir.resolve()}")
    log.info("=" * 60)


if __name__ == "__main__":
    main()