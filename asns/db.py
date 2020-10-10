# Copyright (c) 2020 The Atomic Swap Network Developers
# Licensed under the GNU General Public License, Version 3.

import os

from dataclasses import dataclass, asdict
from enum import IntEnum
from typing import Dict, List, Tuple, Union, Optional

import plyvel
import pickle

from pycoin.encoding import b58
from .util import root_path, sha256d


class TokenStatus(IntEnum):
    NOT_USED = 0
    INITIATOR = 1
    PARTICIPATOR = 2


class SwapStatus(IntEnum):
    REGISTERED = 0
    INITIATED = 1
    PARTICIPATED = 2
    REDEEMED = 3
    COMPLETED = 4
    CANCELED = 5


@dataclass
class TxDBData:
    i_currency: str = None  # TODO: Make Currency Dataclass
    i_receive_amount: int = None
    i_addr: str = None
    i_token_hash: bytes = None
    i_raw_tx: str = None
    i_redeem_raw_tx: str = None
    p_currency: str = None  # TODO: Make Currency Dataclass
    p_receive_amount: int = None
    p_addr: str = None
    p_raw_tx: str = None
    p_redeem_raw_tx: str = None
    swap_status: SwapStatus = SwapStatus.REGISTERED

    @classmethod
    def from_dict(cls, dict_data: Dict) -> 'TxDBData':
        assert isinstance(dict_data, Dict), f"Data is not dict! ({type(dict_data)})"

        shaped_dict_data = {}

        data_list: List[Tuple[str, type]] = [
            ("i_currency", str),
            ("i_receive_amount", int),
            ("i_addr", str),
            ("i_token_hash", bytes),
            ("i_raw_tx", str),
            ("i_redeem_raw_tx", str),
            ("p_currency", str),
            ("p_receive_amount", int),
            ("p_addr", str),
            ("p_raw_tx", str),
            ("p_redeem_raw_tx", str),
            ("swap_status", int)
        ]

        for data in data_list:
            one_of_dict_data = dict_data.get(data[0])
            shaped_dict_data[data[0]] = None if not isinstance(one_of_dict_data, data[1]) else one_of_dict_data
            if one_of_dict_data is not None and data[0] == "swap_status":
                try:
                    shaped_dict_data[data[0]] = SwapStatus(one_of_dict_data)
                except ValueError:
                    pass

        return TxDBData(**shaped_dict_data)

    def asdict(self) -> Dict:
        result = asdict(self)
        result["swap_status"] = int(result["swap_status"])
        return result


@dataclass
class TokenDBData:
    date: int = None
    token_status: TokenStatus = TokenStatus.NOT_USED

    @classmethod
    def from_dict(cls, dict_data: Dict) -> 'TokenDBData':
        assert isinstance(dict_data, Dict), f"Data is not dict! ({type(dict_data)})"

        shaped_dict_data = {}

        data_list: List[Tuple[str, type]] = [
            ("date", int),
            ("token_status", int)
        ]

        for data in data_list:
            one_of_dict_data = dict_data.get(data[0])
            shaped_dict_data[data[0]] = None if not isinstance(one_of_dict_data, data[1]) else one_of_dict_data
            if one_of_dict_data is not None and data[0] == "token_status":
                try:
                    shaped_dict_data[data[0]] = TokenStatus(one_of_dict_data)
                except ValueError:
                    pass

        return TokenDBData(**shaped_dict_data)

    def asdict(self) -> Dict:
        return asdict(self)


class DBBase:
    def __init__(self, db_name: str, db_base_path: str = None) -> None:
        self.db_name = db_name
        self.db_base_path = db_base_path or root_path
        os.makedirs(self.db_base_path, exist_ok=True)
        self.db = plyvel.DB(os.path.join(self.db_base_path, self.db_name), create_if_missing=True)

    def put(self, key: str, value: Union[TxDBData, TokenDBData]) -> None:
        raise NotImplementedError

    def get(self, key: str) -> Optional[Union[TxDBData, TokenDBData]]:
        raise NotImplementedError


class TxDB(DBBase):
    def __init__(self, db_base_path: str = None) -> None:
        super().__init__("tx_db", db_base_path)

    def put(self, key: bytes, value: TxDBData) -> None:
        assert isinstance(value, TxDBData), f"Data type is inappropriate!({type(value).__name__})"
        serialized_value = pickle.dumps(value.asdict())
        self.db.put(key, serialized_value)

    def get(self, key: bytes) -> Optional[TxDBData]:
        value = self.db.get(key)
        if value is None:
            return None
        deserialized_value = pickle.loads(value)
        return TxDBData.from_dict(deserialized_value)

    def get_all(self) -> Dict[bytes, TxDBData]:
        values = {}
        for key, value in self.db:
            deserialized_value = pickle.loads(value)
            values[key] = TxDBData.from_dict(deserialized_value)
        return values


class TokenDB(DBBase):
    def __init__(self, db_base_path: str = None) -> None:
        super().__init__("token_db", db_base_path)

    def put(self, key: bytes, value: TokenDBData) -> None:
        assert isinstance(value, TokenDBData), f"Data type is inappropriate!({type(value).__name__})"
        serialized_value = pickle.dumps(value.asdict())
        self.db.put(key, serialized_value)

    def get(self, key: bytes) -> Optional[TokenDBData]:
        value = self.db.get(key)
        if value is None:
            return None
        deserialized_value = pickle.loads(value)
        return TokenDBData.from_dict(deserialized_value)

    def verify_token(self, token: str) -> Tuple[bool, Optional[int]]:
        raw_token = b58.a2b_base58(token)
        hashed_token = sha256d(raw_token)
        if data := self.get(hashed_token):
            return True, data.date
        else:
            return False, None


class DBCommons:
    def __init__(self, db_base_path: str) -> None:
        self.tx_db = TxDB(db_base_path)
        self.token_db = TokenDB(db_base_path)

    def token_status_msg(self, token: str, token_status: List[TokenStatus]) -> Optional[str]:
        is_exist = False
        is_used = False
        equal_status = False
        msg = None

        token_data = None

        raw_token = b58.a2b_base58(token)
        hashed_token = sha256d(raw_token)
        try:
            token_data = self.token_db.get(hashed_token)
        except Exception:
            pass

        if token_data is not None:
            is_exist = True

        if is_exist:
            equal_status = token_data.token_status not in token_status
            try:
                is_used = bool(self.tx_db.get(hashed_token))
            except Exception:
                pass
        else:
            msg = "Token is not registered or is invalid."

        if equal_status:
            msg = "Inappropriate token status."
        elif is_used:
            msg = "Token is already used."

        return msg

    def change_token_status(self, hashed_token: bytes, token_status: TokenStatus) -> Optional[str]:
        err = None

        try:
            token_data = self.token_db.get(hashed_token)
            token_data.token_status = token_status
            self.token_db.put(hashed_token, token_data)
        except Exception as e:
            err = str(e)

        return err

    def update_swap(self, hashed_token: bytes, swap_data: TxDBData, err: str = None) -> Dict:
        try:
            if err:
                raise Exception(f"Failed to update token status: {err}")
            self.tx_db.put(hashed_token, swap_data)
            result = {
                "status": "Success"
            }
        except Exception as e:
            if err is None:
                e = f"Failed to update swap data: {str(e)}"
            result = {
                "status": "Failed",
                "error": str(e)
            }
        return result

    def verify_token_and_get_swap_data(
            self,
            token: str,
            token_statuses: List[TokenStatus],
            swap_status: SwapStatus,
            selected_swap_key: bytes = None
    ) -> Tuple[Optional[Dict], bytes, Optional[TxDBData]]:
        msg = self.token_status_msg(token, token_statuses)
        selected_swap_data = None

        if selected_swap_key is None:
            raw_token = b58.a2b_base58(token)
            selected_swap_key = sha256d(raw_token)

        if msg is None:
            try:
                selected_swap_data = self.tx_db.get(selected_swap_key)
            except Exception:
                pass

        if selected_swap_data is None:
            msg = "Selected swap is not registered or is invalid."

        if selected_swap_data.swap_status != swap_status:
            msg = "Selected swap is already in progress or completed."

        result = {
            "status": "Failed",
            "error": msg
        } if msg is not None else None

        return result, selected_swap_key, selected_swap_data

