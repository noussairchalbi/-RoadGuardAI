import os
import shutil
from huggingface_hub import hf_hub_download

REPO_ID = "noussairchalbi/roadguard-models"  # <-- a modifier si besoin
DEST_DIR = os.path.join(os.path.dirname(__file__), "detector", "ml_models")

FILES = ["best_model.pth", "best_model_vgg16.pth"]

os.makedirs(DEST_DIR, exist_ok=True)

for filename in FILES:
    print(f"Telechargement de {filename}...")
    path = hf_hub_download(repo_id=REPO_ID, filename=filename)
    dest = os.path.join(DEST_DIR, filename)
    if not os.path.exists(dest):
        shutil.copy(path, dest)
    print(f"  -> {dest}")

print("Termine.")
