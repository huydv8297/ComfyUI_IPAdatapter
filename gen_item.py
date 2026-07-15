from diffusers import DiffusionPipeline
from transformers import AutoModelForImageSegmentation
from torchvision import transforms
from PIL import Image
from huggingface_hub import login

import os
import gc
import csv
import re
import torch

# ==========================================================
# CONFIG
# ==========================================================

HF_TOKEN = "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"

PROMPT_FILE = "cooking_merge_puzzle_prompts_200.csv"

OUTPUT_DIR = "output"
RAW_DIR = os.path.join(OUTPUT_DIR, "raw")
FINAL_DIR = os.path.join(OUTPUT_DIR, "transparent")

DEVICE = "cuda"

WIDTH = 1024
HEIGHT = 1024

GUIDANCE_SCALE = 3.5
INFERENCE_STEPS = 24
MAX_SEQUENCE_LENGTH = 512

LORA_WEIGHT = 1.0

SEED = 1234

PROMPT_PREFIX = "wbgmsst"
PROMPT_SUFFIX = "white background"

# ==========================================================
# CREATE FOLDERS
# ==========================================================

os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(RAW_DIR, exist_ok=True)
os.makedirs(FINAL_DIR, exist_ok=True)

# ==========================================================
# LOGIN HUGGINGFACE
# ==========================================================

print("=" * 60)
print("Login HuggingFace...")
print("=" * 60)

login(token=HF_TOKEN)

# ==========================================================
# LOAD PROMPTS
# ==========================================================

print("=" * 60)
print("Loading prompts...")
print("=" * 60)

def safe_filename_part(value):
    value = str(value).strip()
    value = re.sub(r"[\\/:*?\"<>|]+", "_", value)
    value = re.sub(r"\s+", "_", value)
    value = re.sub(r"_+", "_", value)
    return value.strip("._")


with open(PROMPT_FILE, "r", encoding="utf-8-sig", newline="") as f:
    reader = csv.DictReader(f)
    required_columns = {"id", "type", "level", "item_name", "prompt"}
    missing_columns = required_columns - set(reader.fieldnames or [])

    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Missing required CSV columns: {missing}")

    prompt_rows = []

    for row in reader:
        prompt = row["prompt"].strip()

        if not prompt:
            continue

        prompt_rows.append({
            "id": row["id"].strip(),
            "type": row["type"].strip(),
            "level": row["level"].strip(),
            "item_name": row["item_name"].strip(),
            "prompt": prompt,
        })

print(f"Found {len(prompt_rows)} prompts")

# ==========================================================
# LOAD FLUX
# ==========================================================

print("=" * 60)
print("Loading FLUX.1-dev...")
print("=" * 60)

pipe = DiffusionPipeline.from_pretrained(
    "black-forest-labs/FLUX.1-dev",
    torch_dtype=torch.float16,
)

# pipe.enable_model_cpu_offload()
pipe.to(DEVICE)

print("Loading Game Assets LoRA...")

pipe.load_lora_weights(
    "gokaygokay/Flux-Game-Assets-LoRA-v2"
)

pipe.set_adapters(
    ["default_0"],
    adapter_weights=[LORA_WEIGHT],
)

# pipe.enable_vae_slicing()
# pipe.enable_vae_tiling()

print("FLUX Loaded.")

# ==========================================================
# GENERATE IMAGES
# ==========================================================

print("=" * 60)
print("Generating images...")
print("=" * 60)

generated_files = []

for i, row in enumerate(prompt_rows):

    seed = SEED + i

    generator = torch.Generator(
        device=DEVICE
    ).manual_seed(seed)

    prompt = f"{PROMPT_PREFIX}, {row['prompt']}, {PROMPT_SUFFIX}"

    print(f"\n[{i+1}/{len(prompt_rows)}]")
    print(f"Item   : {row['type']} L{row['level']} - {row['item_name']}")
    print(f"Prompt : {prompt}")
    print(f"Seed   : {seed}")

    image = pipe(
        prompt=prompt,
        guidance_scale=GUIDANCE_SCALE,
        num_inference_steps=INFERENCE_STEPS,
        max_sequence_length=MAX_SEQUENCE_LENGTH,
        generator=generator,
        height=HEIGHT,
        width=WIDTH,
    ).images[0]

    row_id = safe_filename_part(row["id"]).zfill(4)
    item_type = safe_filename_part(row["type"])
    level = safe_filename_part(row["level"]).zfill(2)
    item_name = safe_filename_part(row["item_name"])

    filename = f"{row_id}_{item_type}_L{level}_{item_name}.png"

    save_path = os.path.join(
        RAW_DIR,
        filename
    )

    image.save(save_path)
    generated_files.append(filename)

    print(f"Saved -> {save_path}")

print("\nAll images generated.")

# ==========================================================
# FREE FLUX MEMORY
# ==========================================================

print("=" * 60)
print("Freeing FLUX memory...")
print("=" * 60)

del pipe

gc.collect()

if torch.cuda.is_available():
    torch.cuda.empty_cache()
    torch.cuda.ipc_collect()

print("VRAM released.")

# ==========================================================
# LOAD BIREFNET
# ==========================================================

print("=" * 60)
print("Loading BiRefNet...")
print("=" * 60)

birefnet = AutoModelForImageSegmentation.from_pretrained(
    "ZhengPeng7/BiRefNet",
    trust_remote_code=True,
).to(DEVICE)

birefnet.eval()

transform = transforms.Compose([
    transforms.Resize((1024, 1024)),
    transforms.ToTensor(),
    transforms.Normalize(
        [0.5, 0.5, 0.5],
        [0.5, 0.5, 0.5],
    ),
])

# ==========================================================
# REMOVE BACKGROUND
# ==========================================================

def remove_bg(image: Image.Image):

    width, height = image.size

    input_tensor = transform(image).unsqueeze(0).to(DEVICE)

    with torch.no_grad():

        output = birefnet(input_tensor)

        if hasattr(output, "logits"):
            pred = output.logits
        else:
            pred = output[-1]

        pred = pred.sigmoid().cpu()[0][0]

    mask = transforms.ToPILImage()(pred)

    mask = mask.resize(
        (width, height),
        Image.Resampling.BILINEAR
    )

    rgba = image.convert("RGBA")

    rgba.putalpha(mask)

    return rgba

# ==========================================================
# REMOVE BACKGROUND FOR ALL IMAGES
# ==========================================================

print("=" * 60)
print("Removing background...")
print("=" * 60)

files = sorted(generated_files)

for i, file in enumerate(files):

    input_path = os.path.join(RAW_DIR, file)

    output_path = os.path.join(FINAL_DIR, file)

    img = Image.open(input_path).convert("RGB")

    result = remove_bg(img)

    result.save(output_path)

    print(f"[{i+1}/{len(files)}] Saved -> {output_path}")

print("=" * 60)
print("FINISHED")
print("=" * 60)
print(f"Raw images         : {RAW_DIR}")
print(f"Transparent images : {FINAL_DIR}")
