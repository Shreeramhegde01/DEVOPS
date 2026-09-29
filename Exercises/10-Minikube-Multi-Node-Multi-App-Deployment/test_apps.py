import unittest

import product_catalog
import shopping_cart


class TestProductCatalog(unittest.TestCase):
    def test_products(self):
        response = product_catalog.app.test_client().get("/products")
        self.assertEqual(response.status_code, 200)
        self.assertEqual([p["name"] for p in response.get_json()], ["Laptop", "Phone", "Headphones"])


class TestShoppingCart(unittest.TestCase):
    def setUp(self):
        shopping_cart.cart.clear()
        self.client = shopping_cart.app.test_client()

    def test_cart_starts_empty(self):
        self.assertEqual(self.client.get("/cart").get_json(), [])

    def test_add_to_cart(self):
        item = {"id": 1, "name": "Laptop", "quantity": 1}
        response = self.client.post("/cart", json=item)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.get_json(), [item])
        self.assertEqual(self.client.get("/cart").get_json(), [item])

    def test_whoami(self):
        self.assertEqual(self.client.get("/whoami").get_json()["service"], "shopping-cart")


if __name__ == "__main__":
    unittest.main()
