import os
import uuid

from django.conf import settings
from django.shortcuts import render
from django.core.files.storage import FileSystemStorage
from PIL import Image

from .forms import MediaUploadForm
from . import ml_engine as ml
from . import video_engine


def index(request):
    """Page d'accueil : formulaire d'upload."""
    form = MediaUploadForm()
    return render(request, "detector/index.html", {"form": form})


def analyze(request):
    if request.method != "POST":
        return render(request, "detector/index.html", {"form": MediaUploadForm()})

    form = MediaUploadForm(request.POST, request.FILES)
    if not form.is_valid():
        return render(request, "detector/index.html", {"form": form})

    uploaded_file = form.cleaned_data["media_file"]
    is_video = MediaUploadForm.is_video(uploaded_file.name)

    session_id = uuid.uuid4().hex[:10]
    upload_dir = os.path.join(settings.MEDIA_ROOT, "uploads")
    result_dir = os.path.join(settings.MEDIA_ROOT, "results")
    os.makedirs(upload_dir, exist_ok=True)
    os.makedirs(result_dir, exist_ok=True)

    fs = FileSystemStorage(location=upload_dir)
    ext = os.path.splitext(uploaded_file.name)[1]
    saved_name = f"{session_id}{ext}"
    fs.save(saved_name, uploaded_file)
    input_path = os.path.join(upload_dir, saved_name)

    if is_video:
        output_name = f"{session_id}_result.mp4"
        output_path = os.path.join(result_dir, output_name)
        summary = video_engine.process_video(input_path, output_path)

        context = {
            "is_video": True,
            "video_url": settings.MEDIA_URL + f"results/{output_name}",
            "summary": summary,
            "safety_labels_fr": ml.SAFETY_LABELS_FR,
            "road_labels_fr": ml.ROAD_LABELS_FR,
        }
        return render(request, "detector/result.html", context)

    else:
        pil_img = Image.open(input_path).convert("RGB")
        res = ml.analyze_image(pil_img)

        orig_name = f"{session_id}_orig.jpg"
        gradcam_safety_name = f"{session_id}_gradcam_safety.jpg"
        gradcam_road_name = f"{session_id}_gradcam_road.jpg"

        pil_img.resize((224, 224)).save(os.path.join(result_dir, orig_name))
        res["safety"]["gradcam_image"].save(os.path.join(result_dir, gradcam_safety_name))
        res["road"]["gradcam_image"].save(os.path.join(result_dir, gradcam_road_name))

        context = {
            "is_video": False,
            "orig_url": settings.MEDIA_URL + f"results/{orig_name}",
            "gradcam_safety_url": settings.MEDIA_URL + f"results/{gradcam_safety_name}",
            "gradcam_road_url": settings.MEDIA_URL + f"results/{gradcam_road_name}",
            "safety": res["safety"],
            "road": res["road"],
        }
        return render(request, "detector/result.html", context)
