"""
Traitement video : on echantillonne des frames a intervalle regulier,
on fait tourner les deux modeles + Grad-CAM sur chaque frame echantillonnee,
on incruste le texte de resultat sur la frame, et on reassemble une video
de sortie en plus d'un resume texte global.
"""
import os
import subprocess
import cv2
import numpy as np
from PIL import Image

from . import ml_engine as ml

# Analyser une frame sur N (pour rester rapide sur CPU)
FRAME_SAMPLE_INTERVAL = 15
MAX_SAMPLED_FRAMES = 40


def _put_wrapped_text(frame, lines, org=(10, 25), color=(255, 255, 255), bg=(0, 0, 0)):
    x, y = org
    for i, line in enumerate(lines):
        yy = y + i * 22
        (tw, th), _ = cv2.getTextSize(line, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 1)
        cv2.rectangle(frame, (x - 4, yy - th - 4), (x + tw + 4, yy + 4), bg, -1)
        cv2.putText(frame, line, (x, yy), cv2.FONT_HERSHEY_SIMPLEX, 0.55, color, 1, cv2.LINE_AA)
    return frame


def process_video(input_path, output_path):
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        raise ValueError("Impossible d'ouvrir la video")

    fps = cap.get(cv2.CAP_PROP_FPS) or 25
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

    tmp_output_path = output_path + ".tmp.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(tmp_output_path, fourcc, fps, (width, height))

    frame_idx = 0
    sampled_count = 0

    safety_counts = {c: 0 for c in ml.SAFETY_CLASSES}
    road_counts = {c: 0 for c in ml.ROAD_CLASSES}

    last_safety_label = None
    last_road_label = None
    last_safety_conf = 0.0
    last_road_conf = 0.0

    alerts = []  # frames avec unsafe ou obstacle/damage_road, avec timestamp

    while True:
        ok, frame = cap.read()
        if not ok:
            break

        analyze_this_frame = (
            frame_idx % FRAME_SAMPLE_INTERVAL == 0 and sampled_count < MAX_SAMPLED_FRAMES
        )

        if analyze_this_frame:
            pil_img = ml.bgr_to_pil(frame)
            res = ml.analyze_image(pil_img)

            last_safety_label = res["safety"]["label"]
            last_safety_conf = res["safety"]["confidence"]
            last_road_label = res["road"]["label"]
            last_road_conf = res["road"]["confidence"]

            safety_counts[last_safety_label] += 1
            road_counts[last_road_label] += 1
            sampled_count += 1

            timestamp_s = frame_idx / fps
            if last_safety_label == "unsafe" or last_road_label in ("damage_road", "obstacle"):
                alerts.append(
                    {
                        "time_s": round(timestamp_s, 1),
                        "safety": last_safety_label,
                        "road": last_road_label,
                    }
                )

        if last_safety_label is not None:
            lines = [
                f"Securite: {ml.SAFETY_LABELS_FR[last_safety_label]} ({last_safety_conf*100:.0f}%)",
                f"Route: {ml.ROAD_LABELS_FR[last_road_label]} ({last_road_conf*100:.0f}%)",
            ]
            color = (0, 0, 255) if last_safety_label == "unsafe" else (0, 200, 0)
            frame = _put_wrapped_text(frame, lines, color=(255, 255, 255), bg=color)

        writer.write(frame)
        frame_idx += 1

    cap.release()
    writer.release()

    # Reencodage en H.264 pour compatibilite navigateur (mp4v n'est pas lisible
    # dans la plupart des navigateurs web).
    try:
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", tmp_output_path,
                "-c:v", "libx264", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                output_path,
            ],
            check=True,
            capture_output=True,
        )
        os.remove(tmp_output_path)
    except (subprocess.CalledProcessError, FileNotFoundError):
        # Si ffmpeg indisponible, on garde la version brute
        os.replace(tmp_output_path, output_path)

    def pct(counts):
        total = sum(counts.values()) or 1
        return {k: round(100 * v / total, 1) for k, v in counts.items()}

    summary = {
        "total_frames": total_frames,
        "sampled_frames": sampled_count,
        "duration_s": round(total_frames / fps, 1) if fps else None,
        "safety_counts": safety_counts,
        "road_counts": road_counts,
        "safety_pct": pct(safety_counts),
        "road_pct": pct(road_counts),
        "alerts": alerts[:20],
        "nb_alerts": len(alerts),
    }
    return summary
