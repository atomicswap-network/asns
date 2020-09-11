# Copyright (c) 2020 The Swapping Support System Developers
#
# Permission is hereby granted, free of charge, to any person
# obtaining a copy of this software and associated documentation files
# (the "Software"), to deal in the Software without restriction,
# including without limitation the rights to use, copy, modify, merge,
# publish, distribute, sublicense, and/or sell copies of the Software,
# and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
#
# The above copyright notice and this permission notice shall be
# included in all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
# NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS
# BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN
# ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import os

from dataclasses import dataclass, asdict
from enum import IntEnum
from typing import Dict, List, Tuple, Union

import plyvel
import pickle
from .util import root_path


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
    i_token: str = None
    i_raw_tx: str = None
    i_redeem_raw_tx: str = None
    p_currency: str = None  # TODO: Make Currency Dataclass
    p_want_amount: int = None
    p_addr: str = None
    p_raw_tx: str = None
    p_redeem_raw_tx: str = None
    secret: str = None
    secret_hash: str = None
    swap_status: SwapStatus = SwapStatus.REGISTERED

    @classmethod
    def from_dict(cls, dict_data: Dict) -> 'TxDBData':
        assert isinstance(dict_data, Dict), f"Data is not dict! ({type(dict_data)})"

        shaped_dict_data = {}

        data_list: List[Tuple[str, type]] = [
            ("i_currency", str),
            ("i_receive_amount", int),
            ("i_addr", str),
            ("i_token", str),
            ("i_raw_tx", str),
            ("i_redeem_raw_tx", str),
            ("p_currency", str),
            ("p_want_amount", int),
            ("p_addr", str),
            ("p_raw_tx", str),
            ("p_redeem_raw_tx", str),
            ("secret", str),
            ("secret_hash", str),
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
    date: int

    @classmethod
    def from_dict(cls, dict_data: Dict) -> 'TokenDBData':
        assert isinstance(dict_data, Dict), f"Data is not dict! ({type(dict_data)})"

        shaped_dict_data = {}

        data_list: List[Tuple[str, type]] = [
            ("data", int)
        ]

        for data in data_list:
            one_of_dict_data = dict_data.get(data[0])
            shaped_dict_data[data[0]] = None if not isinstance(one_of_dict_data, data[1]) else one_of_dict_data

        return TokenDBData(**shaped_dict_data)

    def asdict(self) -> Dict:
        return asdict(self)


class DBBase:
    def __init__(self, db_name: str) -> None:
        os.makedirs(root_path, exist_ok=True)
        self.db = plyvel.DB(os.path.join(root_path, db_name), bool_create_if_missing=True)

    def put(self, key: str, value: Union[TxDBData, TokenDBData]) -> None:
        raise NotImplementedError

    def get(self, key: str) -> Union[TxDBData, TokenDBData]:
        raise NotImplementedError


class TxDB(DBBase):
    def __init__(self) -> None:
        super().__init__("tx_db")

    def put(self, key: str, value: TxDBData) -> None:
        assert isinstance(value, TxDBData), f"Data type is inappropriate!({type(value).__name__})"
        serialized_value = pickle.dumps(value.asdict())
        self.db.put(key, serialized_value)

    def get(self, key: str) -> TxDBData:
        value = self.db.get(key)
        deserialized_value = pickle.loads(value)
        return TxDBData.from_dict(deserialized_value)


class TokenDB(DBBase):
    def __init__(self) -> None:
        super().__init__("token_db")

    def put(self, key: str, value: TokenDBData) -> None:
        assert isinstance(value, TokenDBData), f"Data type is inappropriate!({type(value).__name__})"
        serialized_value = pickle.dumps(value.asdict())
        self.db.put(key, serialized_value)

    def get(self, key: str) -> TokenDBData:
        value = self.db.get(key)
        deserialized_value = pickle.loads(value)
        return TokenDBData.from_dict(deserialized_value)
