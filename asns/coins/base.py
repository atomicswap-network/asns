# Copyright (c) 2020 The Atomic Swap Network Developers
# Licensed under the GNU General Public License, Version 3.

import json

from dataclasses import dataclass
from typing import List, Dict, Tuple

from ..util import resource_path


@dataclass
class CoinBaseData:
    name: str = None
    symbol: str = None
    insight: List[str] = None
    blockbook: List[str] = None
    electrumx: Dict = None
    p2pkh_prefix: bytes = None
    p2sh_prefix: bytes = None
    bech32_prefix: str = None

    @classmethod
    def from_json(cls, coin_name: str) -> 'CoinBaseData':
        low = coin_name.lower()
        if "Testnet" in coin_name:
            low, testnet = low.split()
            with open(resource_path("coins", low + "_" + testnet + ".json")) as f:
                coin_json = json.loads(f.read())
        else:
            with open(resource_path("coins", low + ".json")) as f:
                coin_json = json.loads(f.read())

        shaped_data = {}

        data_list: List[Tuple[str, type]] = [
            ("name", str),
            ("symbol", str),
            ("insight", list),
            ("blockbook", list),
            ("electrumx", dict),
            ("p2pkh_prefix", int),
            ("p2sh_prefix", int),
            ("bech32_prefix", str)
        ]

        for d in data_list:
            data = coin_json.get(d[0])
            shaped_data[d[0]] = None if not isinstance(data, d[1]) else data
            if shaped_data[d[0]] is not None and d[0].endswith("prefix") and d[1] == int:
                try:
                    shaped_data[d[0]] = bytes([data])
                except Exception:
                    pass

        return CoinBaseData(**shaped_data)

