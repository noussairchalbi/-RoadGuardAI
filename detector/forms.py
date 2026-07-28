from django import forms

IMAGE_EXT = (".jpg", ".jpeg", ".png", ".bmp", ".webp")
VIDEO_EXT = (".mp4", ".avi", ".mov", ".mkv", ".webm")


class MediaUploadForm(forms.Form):
    media_file = forms.FileField(label="Image ou video")

    def clean_media_file(self):
        f = self.cleaned_data["media_file"]
        name = f.name.lower()
        if not (name.endswith(IMAGE_EXT) or name.endswith(VIDEO_EXT)):
            raise forms.ValidationError(
                "Format non supporte. Formats acceptes : "
                + ", ".join(IMAGE_EXT + VIDEO_EXT)
            )
        return f

    @staticmethod
    def is_video(filename):
        return filename.lower().endswith(VIDEO_EXT)
