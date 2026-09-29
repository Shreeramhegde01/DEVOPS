import unittest
from unittest import mock

from app import app


class TestNetworkingApp(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_about(self):
        data = self.client.get('/about').get_json()
        self.assertEqual(data["name"], "Simple REST API")
        self.assertEqual(data["version"], "1.0")

    def test_status_reports_unreachable_dependencies(self):
        # Outside Docker the names "mysql" / "redis" do not resolve
        with mock.patch("socket.gethostbyname", side_effect=OSError("no such host")):
            response = self.client.get('/status')
        self.assertEqual(response.status_code, 503)
        self.assertFalse(response.get_json()["dependencies"]["mysql"]["reachable"])

    def test_status_ok_when_dependencies_reachable(self):
        with mock.patch("socket.gethostbyname", return_value="172.18.0.2"), \
             mock.patch("socket.create_connection"):
            response = self.client.get('/status')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["dependencies"]["redis"]["reachable"])


if __name__ == '__main__':
    unittest.main()
