from io import BytesIO
from uuid import uuid4

from PIL import Image, ImageOps, UnidentifiedImageError
from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand

from accounts.models import User


class Command(BaseCommand):
    help = "Reduce existing profile photo dimensions and file size."

    def handle(self, **options):
        saved_bytes = 0
        updated = 0
        for user in User.objects.exclude(photo="").iterator():
            photo = user.photo
            try:
                original_size = photo.size
                with photo.open("rb") as stream, Image.open(stream) as image:
                    image.load()
                    portrait = ImageOps.exif_transpose(image).convert("RGB")
                    portrait.thumbnail((480, 600))
                    output = BytesIO()
                    portrait.save(output, "JPEG", quality=80, optimize=True)
                content = output.getvalue()
                if len(content) >= original_size:
                    continue
                # Retain the original file for recovery. The database uses the smaller copy.
                user.photo.save(f"{uuid4().hex}.jpg", ContentFile(content), save=False)
                user.save(update_fields=["photo"])
                saved_bytes += original_size - len(content)
                updated += 1
            except (OSError, ValueError, UnidentifiedImageError):
                self.stderr.write(f"Skipped unreadable photo for user {user.pk}.")
        self.stdout.write(f"Optimized {updated} photos; {saved_bytes} fewer bytes served.")
