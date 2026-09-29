import socket
import unittest

from app import app


class TestFlashSaleApp(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_homepage(self):
        data = self.client.get("/").get_json()
        self.assertEqual(data["message"], "Welcome to Big Sale!")
        self.assertEqual(data["pod"], socket.gethostname())

    def test_buy_uses_query_user(self):
        data = self.client.get("/buy?user=123").get_json()
        self.assertEqual(data["status"], "success")
        self.assertEqual(data["user"], "123")
        self.assertIn(data["item"], ["Smartphone", "Shoes", "Headphones", "Laptop"])
        self.assertIn("served_by_pod", data)

    def test_health(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "healthy")


if __name__ == "__main__":
    unittest.main()
