from django.test import override_settings
from rest_framework.test import APITestCase


PASSWORD = "MotDePasse123!"


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class AuthAndShopTests(APITestCase):
    def register(self, email, username):
        return self.client.post(
            "/api/v1/auth/register/",
            {"email": email, "username": username, "password": PASSWORD},
            format="json",
        )

    def login(self, email):
        response = self.client.post(
            "/api/v1/auth/token/",
            {"email": email, "password": PASSWORD},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        return response.data["access"]

    def use_token(self, access, shop_id=None):
        headers = {"HTTP_AUTHORIZATION": f"Bearer {access}"}
        if shop_id:
            headers["HTTP_X_SHOP_ID"] = str(shop_id)
        self.client.credentials(**headers)

    def create_owner_with_shop(self, email="patron@a.ci", username="patron"):
        response = self.register(email, username)
        self.assertEqual(response.status_code, 201, response.data)
        access = self.login(email)
        self.use_token(access)
        response = self.client.post(
            "/api/v1/shops/", {"name": "Quincaillerie A"}, format="json"
        )
        self.assertEqual(response.status_code, 201, response.data)
        return access, response.data["id"]

    def test_registration_and_login_use_email_and_hide_password(self):
        response = self.register("awa@a.ci", "awa")

        self.assertEqual(response.status_code, 201, response.data)
        self.assertNotIn("password", response.data)
        self.assertTrue(self.login("awa@a.ci"))

    def test_duplicate_email_is_rejected(self):
        first = self.register("awa@a.ci", "awa")
        duplicate = self.register("awa@a.ci", "awa2")

        self.assertEqual(first.status_code, 201, first.data)
        self.assertEqual(duplicate.status_code, 400)

    def test_shop_creation_gives_creator_owner_membership(self):
        _, shop_id = self.create_owner_with_shop()

        response = self.client.get("/api/v1/auth/me/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["memberships"], [{
            "shop_id": shop_id,
            "shop_name": "Quincaillerie A",
            "role": "owner",
        }])

    def test_owner_can_update_currency_and_default_stock_threshold(self):
        access, shop_id = self.create_owner_with_shop()
        self.use_token(access)

        response = self.client.patch(
            f"/api/v1/shops/{shop_id}/",
            {"currency": "EUR", "default_min_stock": "4.500"},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.data["currency"], "EUR")
        self.assertEqual(response.data["default_min_stock"], "4.500")

    def test_auth_me_rejects_anonymous_requests(self):
        self.client.credentials()

        response = self.client.get("/api/v1/auth/me/")

        self.assertIn(response.status_code, (401, 403))

    def test_owner_can_add_seller_who_can_login_but_cannot_list_team(self):
        access, shop_id = self.create_owner_with_shop()
        self.use_token(access, shop_id)
        response = self.client.post(
            "/api/v1/members/",
            {
                "email": "vendeur@a.ci",
                "username": "vendeur",
                "password": PASSWORD,
                "role": "seller",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)

        seller_access = self.login("vendeur@a.ci")
        self.use_token(seller_access, shop_id)
        profile = self.client.get("/api/v1/auth/me/")
        team = self.client.get("/api/v1/members/")

        self.assertEqual(profile.status_code, 200)
        self.assertEqual(profile.data["memberships"][0]["role"], "seller")
        self.assertEqual(team.status_code, 403)

    def test_second_owner_cannot_be_added(self):
        access, shop_id = self.create_owner_with_shop()
        self.use_token(access, shop_id)

        response = self.client.post(
            "/api/v1/members/",
            {
                "email": "second-owner@a.ci",
                "username": "second-owner",
                "password": PASSWORD,
                "role": "owner",
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)

    def test_owner_cannot_modify_own_membership(self):
        access, shop_id = self.create_owner_with_shop()
        self.use_token(access, shop_id)
        response = self.client.get("/api/v1/members/")
        self.assertEqual(response.status_code, 200, response.data)
        owner_membership = next(
            member for member in response.data["results"]
            if member["email"] == "patron@a.ci"
        )

        response = self.client.patch(
            f"/api/v1/members/{owner_membership['id']}/",
            {"role": "seller"},
            format="json",
        )

        self.assertEqual(response.status_code, 403)

    def test_non_member_cannot_list_or_modify_another_users_shop(self):
        _, shop_id = self.create_owner_with_shop()
        response = self.register("autre@b.ci", "autre")
        self.assertEqual(response.status_code, 201, response.data)
        self.use_token(self.login("autre@b.ci"))

        shops = self.client.get("/api/v1/shops/")
        update = self.client.patch(
            f"/api/v1/shops/{shop_id}/", {"name": "Piraté"}, format="json"
        )

        self.assertEqual(shops.status_code, 200)
        self.assertEqual(shops.data["count"], 0)
        self.assertEqual(update.status_code, 404)
