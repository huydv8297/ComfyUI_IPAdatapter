from diffusers import DiffusionPipeline
from transformers import AutoModelForImageSegmentation
from torchvision import transforms
from PIL import Image
from huggingface_hub import login

import os
import gc
import torch

# ==========================================================
# CONFIG
# ==========================================================

HF_TOKEN = "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"

PROMPT_FILE = "prompts.txt"

OUTPUT_DIR = "output"
RAW_DIR = os.path.join(OUTPUT_DIR, "raw")
FINAL_DIR = os.path.join(OUTPUT_DIR, "transparent")

DEVICE = "cuda"

WIDTH = 1024
HEIGHT = 1024

GUIDANCE_SCALE = 3.5
INFERENCE_STEPS = 28
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

with open(PROMPT_FILE, "r", encoding="utf-8") as f:
    prompts = [
        x.strip()
        for x in f.readlines()
        if x.strip()
    ]

print(f"Found {len(prompts)} prompts")

# ==========================================================
# LOAD FLUX
# ==========================================================

print("=" * 60)
print("Loading FLUX.1-dev...")
print("=" * 60)

pipe = DiffusionPipeline.from_pretrained(
    "black-forest-labs/FLUX.1-dev",
    torch_dtype=torch.bfloat16,
    device_map="cuda",
)

print("Loading Game Assets LoRA...")

pipe.load_lora_weights(
    "gokaygokay/Flux-Game-Assets-LoRA-v2"
)

pipe.set_adapters(
    ["default_0"],
    adapter_weights=[LORA_WEIGHT],
)

pipe.enable_vae_slicing()
pipe.enable_vae_tiling()

print("FLUX Loaded.")

# ==========================================================
# GENERATE IMAGES
# ==========================================================

print("=" * 60)
print("Generating images...")
print("=" * 60)

for i, p in enumerate(prompts):

    seed = SEED + i

    generator = torch.Generator(
        device=DEVICE
    ).manual_seed(seed)

    prompt = f"{PROMPT_PREFIX}, {p}, {PROMPT_SUFFIX}"

    print(f"\n[{i+1}/{len(prompts)}]")
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

    safe_name = (
        p.replace("/", "_")
         .replace("\\", "_")
         .replace(":", "_")
         .replace("*", "_")
         .replace("?", "_")
         .replace("\"", "")
         .replace("<", "_")
         .replace(">", "_")
         .replace("|", "_")
         .replace(" ", "_")
    )

    filename = f"{i:04d}_{safe_name}.png"

    save_path = os.path.join(
        RAW_DIR,
        filename
    )

    image.save(save_path)

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

files = sorted([
    f for f in os.listdir(RAW_DIR)
    if f.lower().endswith(".png")
])

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
