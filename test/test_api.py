import unittest
import tempfile
import shutil

from fastapi.testclient import TestClient
from pycoin.encoding import b58

from s4 import s4_api


class TestAPI(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.s4_path = tempfile.mkdtemp()
        s4_api.db_base_path = self.s4_path
        self.client = TestClient(s4_api)

    def tearDown(self):
        super().tearDown()
        shutil.rmtree(self.s4_path)

    def test_index(self):
        response = self.client.get("/")
        right_result = {
            "message": "This server is working."
        }
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), right_result)

    def test_get_token_and_verify_token(self):
        response = self.client.get("/get_token/")
        response_json = response.json()
        token = response_json.get("token")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response_json, dict))
        self.assertTrue(isinstance(token, str))
        encodable = False
        try:
            encodable = bool(b58.a2b_base58(token))
        except Exception:
            pass
        self.assertTrue(encodable)

        true_response = self.client.get(f"/verify_token/?token={token}")
        true_response_json = true_response.json()
        true_exist = true_response_json.get("exist")
        self.assertEqual(true_response.status_code, 200)
        self.assertTrue(isinstance(true_response_json, dict))
        self.assertTrue(isinstance(true_exist, bool))
        self.assertTrue(true_exist)

        false_token = "4esCzx3bbk2UNWLsxinLwGFfUv1zq5N5tUrirCMQWWBWkoxe5yrRYnkqWeqqViDodxSMT252Gif37c7UJp5RLPLy"
        false_response = self.client.get(f"/verify_token/?token={false_token}")
        false_response_json = false_response.json()
        false_exist = false_response_json.get("exist")
        self.assertEqual(false_response.status_code, 200)
        self.assertTrue(isinstance(false_response_json, dict))
        self.assertTrue(isinstance(false_exist, bool))
        self.assertFalse(false_exist)
