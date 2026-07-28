"""
Moteur ML : chargement des deux modeles (securite du transport + etat de la route)
et implementation de Grad-CAM pour les deux architectures.
"""
import os
import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torchvision import models, transforms
from PIL import Image

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
WEIGHTS_DIR = os.path.join(BASE_DIR, "ml_models")

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------
SAFETY_CLASSES = ["safe", "unsafe"]
ROAD_CLASSES = ["clean_road", "damage_road", "obstacle"]

SAFETY_LABELS_FR = {"safe": "Transport sûr", "unsafe": "Transport dangereux"}
ROAD_LABELS_FR = {
    "clean_road": "Route en bon état",
    "damage_road": "Route endommagée (nid-de-poule)",
    "obstacle": "Obstacle sur la route",
}

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD = [0.229, 0.224, 0.225]


# ---------------------------------------------------------------------------
# Architectures (doivent correspondre exactement aux state_dict fournis)
# ---------------------------------------------------------------------------
def build_safety_model():
    """ResNet50 + tete de classification personnalisee -> 2 classes (safe/unsafe)."""
    model = models.resnet50(weights=None)
    model.fc = nn.Sequential(
        nn.Dropout(0.5),
        nn.Linear(2048, 256),
        nn.ReLU(),
        nn.Dropout(0.3),
        nn.Linear(256, len(SAFETY_CLASSES)),
    )
    return model


def build_road_model():
    """VGG16 + tete de classification personnalisee -> 3 classes (route)."""
    model = models.vgg16(weights=None)
    model.classifier = nn.Sequential(
        nn.Linear(25088, 512),
        nn.ReLU(True),
        nn.Dropout(0.5),
        nn.Linear(512, 128),
        nn.ReLU(True),
        nn.Dropout(0.5),
        nn.Linear(128, len(ROAD_CLASSES)),
    )
    return model


def _load(model, filename):
    path = os.path.join(WEIGHTS_DIR, filename)
    state_dict = torch.load(path, map_location=DEVICE, weights_only=True)
    model.load_state_dict(state_dict)
    model.to(DEVICE)
    model.eval()
    return model


_safety_model = None
_road_model = None


def get_safety_model():
    global _safety_model
    if _safety_model is None:
        _safety_model = _load(build_safety_model(), "best_model.pth")
    return _safety_model


def get_road_model():
    global _road_model
    if _road_model is None:
        _road_model = _load(build_road_model(), "best_model_vgg16.pth")
    return _road_model


# ---------------------------------------------------------------------------
# Pre-traitement
# ---------------------------------------------------------------------------
preprocess = transforms.Compose(
    [
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=IMAGENET_MEAN, std=IMAGENET_STD),
    ]
)


def pil_to_tensor(pil_img):
    return preprocess(pil_img.convert("RGB")).unsqueeze(0).to(DEVICE)


def bgr_to_pil(bgr_frame):
    rgb = cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


# ---------------------------------------------------------------------------
# Grad-CAM (implementation generique via hooks forward/backward)
# ---------------------------------------------------------------------------
class GradCAM:
    """
    Implementation basee sur retain_grad() plutot qu'un backward hook,
    car un backward hook sur une couche suivie d'une operation in-place
    (ex: ReLU(inplace=True) de VGG) casse le graphe d'autograd.
    """

    def __init__(self, model, target_layer):
        self.model = model
        self.target_layer = target_layer
        self.activations = None
        self._fwd_handle = target_layer.register_forward_hook(self._save_activation)

    def _save_activation(self, module, inp, out):
        out.retain_grad()
        self.activations = out

    def remove(self):
        self._fwd_handle.remove()

    def generate(self, input_tensor, class_idx=None):
        self.model.zero_grad()
        output = self.model(input_tensor)
        probs = F.softmax(output, dim=1)
        if class_idx is None:
            class_idx = int(torch.argmax(probs, dim=1).item())
        score = output[0, class_idx]
        score.backward()

        gradients = self.activations.grad[0]         # (C, H, W)
        activations = self.activations.detach()[0]   # (C, H, W)
        weights = gradients.mean(dim=(1, 2))  # (C,)

        cam = torch.zeros(activations.shape[1:], dtype=torch.float32, device=activations.device)
        for i, w in enumerate(weights):
            cam += w * activations[i]

        cam = F.relu(cam)
        cam = cam - cam.min()
        if cam.max() > 0:
            cam = cam / cam.max()
        cam = cam.cpu().numpy()

        return cam, class_idx, probs.detach().cpu().numpy()[0]


def get_target_layer(model, model_type):
    if model_type == "safety":
        return model.layer4[-1]
    elif model_type == "road":
        return model.features[28]
    raise ValueError(model_type)


def overlay_heatmap(pil_img, cam, alpha=0.45):
    """Superpose la carte Grad-CAM (0..1, HxW) sur l'image PIL d'origine."""
    img = np.array(pil_img.convert("RGB").resize((224, 224)))
    cam_resized = cv2.resize(cam, (224, 224))
    heatmap = cv2.applyColorMap(np.uint8(255 * cam_resized), cv2.COLORMAP_JET)
    heatmap = cv2.cvtColor(heatmap, cv2.COLOR_BGR2RGB)
    overlay = np.uint8(img * (1 - alpha) + heatmap * alpha)
    return Image.fromarray(overlay)


# ---------------------------------------------------------------------------
# API haut-niveau : analyser une image PIL avec les deux modeles
# ---------------------------------------------------------------------------
def analyze_image(pil_img):
    """
    Retourne un dict avec les predictions des deux modeles + images Grad-CAM
    encodees en PIL (a sauvegarder par l'appelant).
    """
    tensor = pil_to_tensor(pil_img)

    result = {}

    # --- Modele 1 : securite du transport (ResNet50) ---
    safety_model = get_safety_model()
    cam1 = GradCAM(safety_model, get_target_layer(safety_model, "safety"))
    heatmap1, cls_idx1, probs1 = cam1.generate(tensor)
    cam1.remove()
    gradcam_img1 = overlay_heatmap(pil_img, heatmap1)

    result["safety"] = {
        "label": SAFETY_CLASSES[cls_idx1],
        "label_fr": SAFETY_LABELS_FR[SAFETY_CLASSES[cls_idx1]],
        "confidence": float(probs1[cls_idx1]),
        "probs": {SAFETY_CLASSES[i]: float(p) for i, p in enumerate(probs1)},
        "gradcam_image": gradcam_img1,
    }

    # --- Modele 2 : etat de la route (VGG16) ---
    road_model = get_road_model()
    cam2 = GradCAM(road_model, get_target_layer(road_model, "road"))
    heatmap2, cls_idx2, probs2 = cam2.generate(tensor)
    cam2.remove()
    gradcam_img2 = overlay_heatmap(pil_img, heatmap2)

    result["road"] = {
        "label": ROAD_CLASSES[cls_idx2],
        "label_fr": ROAD_LABELS_FR[ROAD_CLASSES[cls_idx2]],
        "confidence": float(probs2[cls_idx2]),
        "probs": {ROAD_CLASSES[i]: float(p) for i, p in enumerate(probs2)},
        "gradcam_image": gradcam_img2,
    }

    return result
