import unittest
import tempfile
import shutil

from fastapi.testclient import TestClient
from fastapi.encoders import jsonable_encoder
from pycoin.encoding import b58

from asns import asns_api
from asns.util import sha256d

from typing import Dict, Tuple


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
        self.assertTrue(isinstance(response_json, Dict))
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

    def verify_token(self, token: str, result: bool = True) -> None:
        response = self.client.post("/verify_token/", json={"token": token})
        response_json = response.json()
        exist = response_json.get("exist")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response_json, Dict))
        self.assertTrue(isinstance(exist, bool))
        self.assertEqual(exist, result)

    def register_swap(self, req_data: Dict, status_code: int = 200, result: str = "Success") -> None:
        response = self.client.post("/register_swap/", json=jsonable_encoder(req_data))
        response_json = response.json()
        status = response_json.get("status")
        self.assertEqual(response.status_code, status_code)
        self.assertTrue(isinstance(response_json, Dict))
        self.assertEqual(status, result)

    def get_swap_list(self) -> Dict:
        response = self.client.get("/get_swap_list/")
        response_json = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response_json, Dict))
        return response_json

    def test_get_token_and_verify_token(self):
        token, _ = self.get_token()
        self.verify_token(token)

        wrong_token = "4esCzx3bbk2UNWLsxinLwGFfUv1zq5N5tUrirCMQWWBWkoxe5yrRYnkqWeqqViDodxSMT252Gif37c7UJp5RLPLy"
        self.verify_token(wrong_token, False)

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

        self.register_swap(register_right_requests)

        right_list_response = {
            "initiatorCurrency": register_right_requests["wantCurrency"],
            "initiatorReceiveAmount": register_right_requests["sendAmount"],
            "participatorCurrency": register_right_requests["sendCurrency"],
            "participatorReceiveAmount": register_right_requests["wantAmount"],
            "participatorAddress": register_right_requests["receiveAddress"]
        }
        hashed_token_hex = sha256d(raw_token).hex()

        list_response_json = self.get_swap_list()
        data = list_response_json.get("data")
        self.assertTrue(isinstance(data, Dict))
        exported_by_key = data.get(hashed_token_hex)
        self.assertTrue(isinstance(exported_by_key, Dict))
        self.assertEqual(exported_by_key, right_list_response)

