# RoadGuard AI — Django

Application Django qui utilise deux modèles PyTorch entraînés pour analyser
des images ou des vidéos de route :

1. **Sécurité du transport** (`best_model.pth`, ResNet50) → `safe` / `unsafe`
2. **État de la route** (`best_model_vgg16.pth`, VGG16) → `clean_road` /
   `damage_road` / `obstacle`

Chaque prédiction est accompagnée d'une visualisation **Grad-CAM** montrant
les zones de l'image qui ont influencé la décision du modèle.

## Installation

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

> **ffmpeg requis** pour l'analyse vidéo (ré-encodage H.264 compatible
> navigateur). Sur Ubuntu/Debian : `sudo apt install ffmpeg`.
> Sans ffmpeg, l'app fonctionne quand même mais la vidéo de sortie peut
> ne pas se lire dans tous les navigateurs.

## Lancement

```bash
python manage.py migrate
python manage.py runserver
```

Puis ouvrir http://127.0.0.1:8000/

## Structure

```
roadsafety/
├── manage.py
├── requirements.txt
├── roadsafety/            # config Django (settings, urls)
└── detector/
    ├── ml_engine.py        # chargement des 2 modèles + Grad-CAM
    ├── video_engine.py      # échantillonnage & annotation vidéo
    ├── forms.py             # validation upload (image/vidéo)
    ├── views.py              # index + analyze
    ├── urls.py
    ├── templates/detector/  # index.html, result.html, base.html
    ├── static/css/style.css
    ├── templatetags/         # filtres `get_item`, `pct`
    └── ml_models/
        ├── best_model.pth
        └── best_model_vgg16.pth
```

## Fonctionnement

- **Image** : les deux modèles tournent sur l'image entière (224×224),
  chacun génère sa propre carte Grad-CAM superposée en overlay coloré.
- **Vidéo** : une frame sur 15 est échantillonnée (jusqu'à 40 frames max
  pour rester rapide sur CPU), chaque frame échantillonnée est analysée
  par les deux modèles, le résultat texte est incrusté sur la vidéo de
  sortie, et un résumé global (répartition des classes, liste des
  moments à risque) est affiché à côté du lecteur vidéo.

## Configuration

- Les noms de classes / labels français sont dans
  `detector/ml_engine.py` (`SAFETY_LABELS_FR`, `ROAD_LABELS_FR`).
- L'intervalle d'échantillonnage vidéo (`FRAME_SAMPLE_INTERVAL`) et le
  nombre max de frames analysées (`MAX_SAMPLED_FRAMES`) sont réglables
  dans `detector/video_engine.py` — à augmenter/diminuer selon la
  puissance CPU/GPU disponible.
- Taille max d'upload : 200 Mo (`settings.py`,
  `DATA_UPLOAD_MAX_MEMORY_SIZE`).

## Notes de production

Le serveur `runserver` est fourni pour le développement uniquement.
Pour un déploiement réel : utiliser Gunicorn/Uvicorn + Nginx, servir les
`ml_models/*.pth` hors du repo git (ou via Git LFS, ~200 Mo au total),
et idéalement faire tourner l'inférence sur GPU pour les vidéos plus
longues.
