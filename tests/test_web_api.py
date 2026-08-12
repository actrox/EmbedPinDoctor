import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from app.web_app import EmbedPinDoctorHandler


class TestWebAPI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), EmbedPinDoctorHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def get_json(self, path):
        with urlopen(f"{self.base_url}{path}", timeout=3) as response:
            return json.loads(response.read())

    def post_json(self, path, payload):
        request = Request(
            f"{self.base_url}{path}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urlopen(request, timeout=3) as response:
            return json.loads(response.read())

    def test_catalog_and_version_endpoints(self):
        self.assertTrue(self.get_json("/api/version")["version"])
        self.assertGreater(len(self.get_json("/api/chips")["chips"]), 0)
        self.assertGreater(len(self.get_json("/api/modules")["modules"]), 0)

    def test_allocate_endpoint(self):
        result = self.post_json(
            "/api/allocate",
            {
                "chip_id": "stm32f103c8t6",
                "module_ids": ["oled_i2c", "button"],
                "include_alternatives": True,
            },
        )
        self.assertEqual(result["chip"]["id"], "stm32f103c8t6")
        self.assertGreater(len(result["allocation"]), 0)
        self.assertIn("risks", result)

    def test_static_path_traversal_is_rejected(self):
        with self.assertRaises(HTTPError) as context:
            urlopen(f"{self.base_url}/..%2FVERSION", timeout=3)
        self.assertIn(context.exception.code, {400, 404})


if __name__ == "__main__":
    unittest.main()
