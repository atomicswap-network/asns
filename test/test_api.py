import unittest
import tempfile
import shutil

from fastapi.testclient import TestClient
from fastapi.encoders import jsonable_encoder
from pycoin.encoding import b58

from asns import asns_api
from asns.util import sha256d

from typing import Tuple


class TestAPI(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.asns_path = tempfile.mkdtemp()
        asns_api.db_base_path = self.asns_path
        self.client = TestClient(asns_api)

    def tearDown(self):
        super().tearDown()
        shutil.rmtree(self.asns_path)

    def test_index(self):
        response = self.client.get("/")
        right_result = {
            "message": "This server is working."
        }
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), right_result)

    def get_token(self) -> Tuple[str, bytes]:
        response = self.client.get("/get_token/")
        response_json = response.json()
        token = response_json.get("token")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response_json, dict))
        self.assertTrue(isinstance(token, str))
        encodable = False
        raw_token = b""
        try:
            raw_token = b58.a2b_base58(token)
            encodable = bool(raw_token)
        except Exception:
            pass
        self.assertTrue(encodable)
        return token, raw_token

    def verify_token(self, token: str, result: bool) -> None:
        response = self.client.post("/verify_token/", json={"token": token})
        response_json = response.json()
        exist = response_json.get("exist")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response_json, dict))
        self.assertTrue(isinstance(exist, bool))
        self.assertEqual(exist, result)

    def test_get_token_and_verify_token(self):
        token, _ = self.get_token()
        self.verify_token(token, True)

        false_token = "4esCzx3bbk2UNWLsxinLwGFfUv1zq5N5tUrirCMQWWBWkoxe5yrRYnkqWeqqViDodxSMT252Gif37c7UJp5RLPLy"
        self.verify_token(false_token, False)

    def test_register_swap_and_get_swap_list(self):
        token, raw_token = self.get_token()

        register_right_requests = {
            "token": token,
            "wantCurrency": "BTC",
            "wantAmount": 10000,
            "sendCurrency": "LTC",
            "sendAmount": 100000000,
            "receiveAddress": "12dRugNcdxK39288NjcDV4GX7rMsKCGn6B"
        }

        register_response = self.client.post("/register_swap/", json=jsonable_encoder(register_right_requests))
        register_response_json = register_response.json()
        status = register_response_json.get("status")
        self.assertEqual(register_response.status_code, 200)
        self.assertTrue(isinstance(register_response_json, dict))
        self.assertEqual(status, "Success")

        right_list_response = {
            "initiatorCurrency": register_right_requests["wantCurrency"],
            "initiatorReceiveAmount": register_right_requests["sendAmount"],
            "participatorCurrency": register_right_requests["sendCurrency"],
            "participatorReceiveAmount": register_right_requests["wantAmount"],
            "participatorAddress": register_right_requests["receiveAddress"]
        }
        hashed_token_hex = sha256d(raw_token).hex()

        list_response = self.client.get("/get_swap_list/")
        list_response_json = list_response.json()
        self.assertEqual(list_response.status_code, 200)
        self.assertTrue(isinstance(list_response_json, dict))
        data = list_response_json.get("data")
        self.assertTrue(isinstance(data, dict))
        exported_by_key = data.get(hashed_token_hex)
        self.assertTrue(isinstance(exported_by_key, dict))
        self.assertEqual(exported_by_key, right_list_response)

