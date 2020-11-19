import unittest
import tempfile
import shutil
import secrets

from fastapi.testclient import TestClient
from fastapi.encoders import jsonable_encoder
from pycoin.encoding import b58

from asns import asns_api
from asns.util import sha256d, ErrorMessages, ResponseStatus

from enum import Enum

from typing import Dict, Tuple, Optional


class TestAPI(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.asns_path = tempfile.mkdtemp()
        asns_api.db_base_path = self.asns_path
        self.client = TestClient(asns_api)

    def tearDown(self):
        super().tearDown()
        shutil.rmtree(self.asns_path)

    def assertEqualEnumContent(self, first: str, second: Enum) -> None:
        self.assertEqual(first, second.value)

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

    def optional_result_method_by_post(self, end_point: str, req_data: Dict, status_code, result: ResponseStatus) -> Optional[str]:
        response = self.client.post(f"/{end_point}/", json=jsonable_encoder(req_data))
        response_json = response.json()
        status = response_json.get("status")
        self.assertEqual(response.status_code, status_code)
        self.assertTrue(isinstance(response_json, Dict))
        self.assertEqualEnumContent(status, result)
        if result == ResponseStatus.FAILED:
            return response_json.get("error")

    def register_swap(self, req_data: Dict, status_code: int = 200, result: ResponseStatus = ResponseStatus.SUCCESS) -> Optional[str]:
        return self.optional_result_method_by_post("register_swap", req_data, status_code, result)

    def get_swap_list(self) -> Dict:
        response = self.client.get("/get_swap_list/")
        response_json = response.json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response_json, Dict))
        return response_json

    def initiate_swap(self, req_data: Dict, status_code: int = 200, result: ResponseStatus = ResponseStatus.SUCCESS) -> Optional[str]:
        return self.optional_result_method_by_post("initiate_swap", req_data, status_code, result)

    def get_initiator_info(self, token: str, status_code: int = 200) -> Dict:
        response = self.client.post("/get_initiator_info/", json={"token": token})
        response_json = response.json()
        self.assertEqual(response.status_code, status_code)
        self.assertTrue(isinstance(response_json, Dict))
        return response_json

    @staticmethod
    def make_register_requests(
            token: str,
            want_currency: str = "BTC",
            want_amount: int = 10000,
            send_currency: str = "LTC",
            send_amount: int = 100000000,
            receive_address: str = "12dRugNcdxK39288NjcDV4GX7rMsKCGn6B"
    ) -> Dict:
        return {
            "token": token,
            "wantCurrency": want_currency,
            "wantAmount": want_amount,
            "sendCurrency": send_currency,
            "sendAmount": send_amount,
            "receiveAddress": receive_address
        }

    @staticmethod
    def make_initiate_requests(
            token: str,
            selected_swap: str,
            contract: str,
            raw_tx: str,
            receive_address: str = "LV5nrreyVZJVvptA9PZSD4ViegKh7Qa8MA"
    ) -> Dict:
        return {
            "token": token,
            "selectedSwap": selected_swap,
            "contract": contract,
            "rawTransaction": raw_tx,
            "receiveAddress": receive_address
        }

    def test_index(self):
        response = self.client.get("/")
        right_result = {
            "message": "This server is working."
        }
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), right_result)

    def test_get_token_and_verify_token(self):
        token, _ = self.get_token()
        self.verify_token(token)

        for _ in range(10):
            wrong_token = b58.b2a_base58(secrets.token_bytes(64))
            self.verify_token(wrong_token, False)

    def test_register_swap_and_get_swap_list(self):
        token, raw_token = self.get_token()

        register_right_requests = self.make_register_requests(token)

        self.register_swap(register_right_requests)

        wrong_token = b58.b2a_base58(secrets.token_bytes(64))
        register_wrong_requests = self.make_register_requests(wrong_token)

        err = self.register_swap(register_wrong_requests, 400, ResponseStatus.FAILED)
        self.assertEqualEnumContent(err, ErrorMessages.TOKEN_INVALID)

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

        err = self.register_swap(register_right_requests, 400, ResponseStatus.FAILED)
        self.assertEqualEnumContent(err, ErrorMessages.TOKEN_STATUS_INVALID)

    def test_register_swap_and_initiate_swap_and_get_initiator_info(self):
        p_token, p_raw_token = self.get_token()  # participator's token
        i_token, i_raw_token = self.get_token()  # initiator's token

        register_right_requests = self.make_register_requests(p_token)

        self.register_swap(register_right_requests)

        selected_swap = sha256d(p_raw_token).hex()
        contract = (
            "6382012088a820f1636905818c86f7720a410df614656c413c68921c4b57cd1a3134c3c0db960b8876a91456b6159687a5f5d9504e"
            "7e6f60f2a98ad4b5babc67043fbcb35fb17576a914be402c8c3ba4908db6a8b9a3a347a18620fb717f6888ac"
        )
        raw_tx = (
            "02000000000101298fed9754d420a2c97ebb0b9dae0786b3d4df3c5aa4eac7ef8ff5f8d81aa2b80100000017160014ce93b1186648"
            "d2039c794a09631f5a76c6c079e3feffffff0200e1f5050000000017a9144cf32d0858a4cc39b8291416e522960acefc924f87bd3f"
            "1a110000000017a914f0ca045d824af519d5131a751aad0cefe82f59728702473044022059fb209313db688a1ba6dd105fb66612da"
            "e25035b3b53b26319a1b067b4b1c1f02207aa21db14667986109537b25f58c51e782cfa517cb6b81e47c01f2aec54ef7c0012103da"
            "e03d26d68540d94ea4b067a525b929653cdaa863ad21247e5afe719b48510700000000"
        )
        initiate_right_requests = self.make_initiate_requests(i_token, selected_swap, contract, raw_tx)

        self.initiate_swap(initiate_right_requests)

        i_info = self.get_initiator_info(p_token)

        right_response = {
            "status": ResponseStatus.SUCCESS.value,
            "initiatorAddress": initiate_right_requests["receiveAddress"],
            "initiateContract": contract,
            "initiateRawTransaction": raw_tx,
            "tokenHash": sha256d(i_raw_token).hex()
        }

        self.assertEqual(i_info, right_response)


