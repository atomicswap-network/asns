# Copyright (c) 2020 The Atomic Swap Network Developers
# Licensed under the GNU General Public License, Version 3.

from dataclasses import dataclass
from typing import List, Dict


@dataclass
class CoinBaseData:
    symbol: str = None
    insight: List[str] = None
    blockbook: List[str] = None
    electrumx: Dict = None
    p2pkh_prefix: bytes = None
    p2sh_prefix: bytes = None
    bech32_prefix: str = None
