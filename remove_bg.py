# -*- coding: utf-8 -*-
from transformers import AutoModelForImageSegmentation
from torchvision import transforms
from PIL import Image
import os
import gc
import torch

# ==========================================================
# CONFIG
# ==========================================================
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"

OUTPUT_DIR = "output"
RAW_DIR = os.path.join(OUTPUT_DIR, "raw")
FINAL_DIR = os.path.join(OUTPUT_DIR, "transparent")

# Target size for Unity assets (e.g., 512 or 256). 
# Set TARGET_SIZE = None if you want to keep original 1024x1024 resolution.
TARGET_SIZE = (512, 512) 

# Create output directories if they do not exist
os.makedirs(FINAL_DIR, exist_ok=True)

# ==========================================================
# LOAD BIREFNET
# ==========================================================
print("=" * 60)
print(f"Loading BiRefNet on device: {DEVICE}...")
print("=" * 60)

birefnet = AutoModelForImageSegmentation.from_pretrained(
    "ZhengPeng7/BiRefNet",
    trust_remote_code=True,
).to(DEVICE)

birefnet.eval()

# Input transformation for BiRefNet
transform = transforms.Compose([
    transforms.Resize((1024, 1024)),
    transforms.ToTensor(),
    transforms.Normalize(
        [0.485, 0.456, 0.406], # BiRefNet default normalization
        [0.229, 0.224, 0.225],
    ),
])

# ==========================================================
# REMOVE BACKGROUND FUNCTION
# ==========================================================
def remove_bg(image: Image.Image):
    width, height = image.size

    img_rgb = image.convert("RGB")
    
    # Get model's running data type (safely handles FP32/FP16 compatibility)
    model_dtype = next(birefnet.parameters()).dtype
    input_tensor = transform(img_rgb).unsqueeze(0).to(device=DEVICE, dtype=model_dtype)

    with torch.no_grad():
        output = birefnet(input_tensor)
        
        if hasattr(output, "logits"):
            pred = output.logits
        else:
            pred = output[-1]

        pred = pred.sigmoid().cpu()[0][0]

    # Convert predicted mask to PIL Image
    mask = transforms.ToPILImage()(pred)

    # Resize mask to match original image size
    mask = mask.resize(
        (width, height),
        Image.Resampling.BILINEAR
    )

    # Convert source image to RGBA and apply the mask to Alpha channel
    rgba = image.convert("RGBA")
    rgba.putalpha(mask)

    return rgba

# ==========================================================
# SCAN RAW FOLDER & PROCESS
# ==========================================================
valid_extensions = (".png", ".jpg", ".jpeg", ".PNG", ".JPG", ".JPEG")
if not os.path.exists(RAW_DIR):
    print(f"Error: Folder '{RAW_DIR}' not found. Please make sure it exists.")
    exit()

files = sorted([f for f in os.listdir(RAW_DIR) if f.endswith(valid_extensions)])

print("=" * 60)
print(f"Found {len(files)} raw images in '{RAW_DIR}'")
print("Starting background removal...")
print("=" * 60)

if len(files) == 0:
    print("No images found to process.")
    exit()

for i, file in enumerate(files):
    input_path = os.path.join(RAW_DIR, file)
    
    # Force output format to PNG to preserve alpha channel
    base_name = os.path.splitext(file)[0]
    output_path = os.path.join(FINAL_DIR, f"{base_name}.png")

    try:
        # 1. Load raw image
        img = Image.open(input_path)

        # 2. Run background removal
        result = remove_bg(img)

        # 3. Optimize: Scale to target size for Unity
        if TARGET_SIZE is not None:
            result = result.resize(TARGET_SIZE, Image.Resampling.LANCZOS)

        # 4. Save final image
        result.save(output_path, "PNG")

        print(f"[{i+1}/{len(files)}] Processed: {file} -> Saved to {output_path}")

    except Exception as e:
        print(f"[{i+1}/{len(files)}] Error processing {file}: {str(e)}")

# Clear VRAM after processing
del birefnet
gc.collect()
if torch.cuda.is_available():
    torch.cuda.empty_cache()

print("=" * 60)
print("FINISHED!")
print(f"Transparent images saved in : {FINAL_DIR}")
print("=" * 60)
