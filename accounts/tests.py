from django.test import TestCase
from django.urls import reverse

from .models import User


class AccountTests(TestCase):
    def setUp(self):
        self.client_user = User.objects.create_user("c@test.com", "StrongPass!234", full_name="C", role="client")
        self.provider = User.objects.create_user("p@test.com", "StrongPass!234", full_name="P", role="provider")

    def test_register_hashes_password_and_rejects_mismatch(self):
        data = {"full_name": "New", "email": "new@test.com", "phone": "", "role": "client",
                "password1": "StrongPass!234", "password2": "StrongPass!234"}
        self.client.post(reverse("accounts:register"), data)
        u = User.objects.get(email="new@test.com")
        self.assertNotEqual(u.password, "StrongPass!234")
        data.update(email="x@test.com", password2="nope")
        self.client.post(reverse("accounts:register"), data)
        self.assertFalse(User.objects.filter(email="x@test.com").exists())

    def test_duplicate_email_rejected(self):
        data = {"full_name": "D", "email": "C@test.com", "role": "client",
                "password1": "StrongPass!234", "password2": "StrongPass!234"}
        self.client.post(reverse("accounts:register"), data)
        self.assertEqual(User.objects.filter(email__iexact="c@test.com").count(), 1)

    def test_login_and_wrong_role_dashboard_forbidden(self):
        self.client.post(reverse("accounts:login"), {"email": "c@test.com", "password": "StrongPass!234"})
        self.assertEqual(self.client.get(reverse("accounts:client_dashboard")).status_code, 200)
        self.assertEqual(self.client.get(reverse("accounts:provider_dashboard")).status_code, 403)
        self.assertEqual(self.client.get(reverse("accounts:admin_dashboard")).status_code, 403)

    def test_logged_out_redirected_to_login(self):
        r = self.client.get(reverse("accounts:profile"))
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse("accounts:login"), r.url)

    def test_lockout_after_five_failures(self):
        for _ in range(5):
            self.client.post(reverse("accounts:login"), {"email": "c@test.com", "password": "bad"})
        self.client_user.refresh_from_db()
        self.assertTrue(self.client_user.is_locked)

    def test_suspended_cannot_login(self):
        self.provider.status = "suspended"
        self.provider.save()
        self.client.post(reverse("accounts:login"), {"email": "p@test.com", "password": "StrongPass!234"})
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_logout_ends_session(self):
        self.client.login(username="c@test.com", password="StrongPass!234")
        self.client.post(reverse("accounts:logout"))
        self.assertNotIn("_auth_user_id", self.client.session)
