from io import BytesIO
import tempfile
from pathlib import Path

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from PIL import Image
from rest_framework.test import APITestCase

from .models import User


class ProfileSettingsTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="profile@example.com",
            username="profile",
            password="test-password",
        )
        self.client.force_authenticate(self.user)

    def test_user_can_update_theme_and_language(self):
        response = self.client.patch(
            "/api/v1/auth/me/",
            {"theme": "dark", "language": "en", "first_name": "Awa"},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["theme"], "dark")
        self.assertEqual(response.data["language"], "en")
        self.assertEqual(response.data["first_name"], "Awa")

    def test_user_can_upload_a_persistent_profile_photo(self):
        image = BytesIO()
        Image.new("RGB", (1, 1), color="white").save(image, format="PNG")
        with tempfile.TemporaryDirectory() as media_dir:
            with override_settings(MEDIA_ROOT=Path(media_dir)):
                response = self.client.patch(
                    "/api/v1/auth/me/",
                    {"profile_photo": SimpleUploadedFile("avatar.png", image.getvalue(), content_type="image/png")},
                    format="multipart",
                )

                self.assertEqual(response.status_code, 200, response.data)
                self.assertTrue(response.data["profile_photo_url"].startswith("/media/profile_photos/"))
