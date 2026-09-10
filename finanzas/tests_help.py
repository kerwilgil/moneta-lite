"""Help Center tests (in-app user guide)."""

from django.contrib.auth import get_user_model
from django.template.loader import get_template
from django.test import TestCase, override_settings
from django.urls import reverse

from finanzas import help as help_mod
from finanzas.product import edition_features


class HelpCenterTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user("helper", password="secret-pass-123")
        self.client.login(username="helper", password="secret-pass-123")

    def test_requires_login(self):
        self.client.logout()
        resp = self.client.get(reverse("help:help_index"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/accounts/login/", resp.headers["Location"])

    def test_index_loads_and_lists_articles(self):
        resp = self.client.get(reverse("help:help_index"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "helpSearch")
        # Every visible article link is on the index.
        for article in help_mod.visible_articles():
            self.assertContains(resp, reverse("help:help_article", args=[article.slug]))

    def test_every_visible_article_renders(self):
        for article in help_mod.visible_articles():
            with self.subTest(slug=article.slug):
                resp = self.client.get(reverse("help:help_article", args=[article.slug]))
                self.assertEqual(resp.status_code, 200)
                self.assertContains(resp, article.title)
                # Breadcrumb back to the index.
                self.assertContains(resp, reverse("help:help_index"))

    def test_every_article_has_a_body_template(self):
        for article in help_mod.ARTICLES:
            with self.subTest(slug=article.slug):
                get_template(f"finanzas/help/articles/{article.slug}.html")

    def test_unknown_slug_is_404(self):
        resp = self.client.get(reverse("help:help_article", args=["does-not-exist"]))
        self.assertEqual(resp.status_code, 404)

    def test_sidebar_has_help_link(self):
        resp = self.client.get(reverse("finanzas:dashboard"))
        self.assertContains(resp, reverse("help:help_index"))

    def test_contextual_help_button_on_key_screens(self):
        for route in [
            "finanzas:dashboard",
            "finanzas:transaction_list",
            "finanzas:credit_card_list",
            "finanzas:subscription_list",
            "finanzas:reports",
            "imports:import_queue",
            "integrations:mcp",
        ]:
            with self.subTest(route=route):
                resp = self.client.get(reverse(route))
                self.assertEqual(resp.status_code, 200)
                self.assertContains(resp, "help-inline")


@override_settings(APP_EDITION="lite", APP_FEATURES=edition_features("lite"))
class HelpCenterLiteGateTests(TestCase):
    """Lite must not advertise Pro-only modules in the Help Center."""

    PRO_ONLY_SLUGS = {"recurrentes", "ingreso-neto", "libro-contable"}

    def setUp(self):
        self.user = get_user_model().objects.create_user("lite", password="secret-pass-123")
        self.client.login(username="lite", password="secret-pass-123")

    def test_pro_only_articles_hidden_from_index(self):
        resp = self.client.get(reverse("help:help_index"))
        self.assertEqual(resp.status_code, 200)
        for slug in self.PRO_ONLY_SLUGS:
            self.assertNotContains(resp, reverse("help:help_article", args=[slug]))

    def test_pro_only_articles_return_404_on_lite(self):
        for slug in self.PRO_ONLY_SLUGS:
            with self.subTest(slug=slug):
                resp = self.client.get(reverse("help:help_article", args=[slug]))
                self.assertEqual(resp.status_code, 404)

    def test_lite_still_serves_core_articles(self):
        for slug in ["primeros-pasos", "dashboard", "movimientos", "tarjetas", "mcp", "importaciones"]:
            with self.subTest(slug=slug):
                resp = self.client.get(reverse("help:help_article", args=[slug]))
                self.assertEqual(resp.status_code, 200)
