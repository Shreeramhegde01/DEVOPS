import unittest

from app import app


class TestFlaskApp(unittest.TestCase):
    def test_home(self):
        response = app.test_client().get('/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data.decode(), "Hello from Flask on Kubernetes!")


if __name__ == '__main__':
    unittest.main()
