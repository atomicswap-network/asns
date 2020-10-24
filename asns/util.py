# Copyright (c) 2011-2020 The Electrum Developers
# Copyright (c) 2020 The Atomic Swap Network Developers
# Licensed under the GNU General Public License, Version 3.

import platform
import os
import hashlib

from enum import Enum
from typing import Union

os_name = platform.system()


def get_path() -> str:
    if os_name == "Windows":
        path = os.path.expanduser("~/AppData/Roaming/")
    elif os_name == "Darwin":
        path = os.path.expanduser("~/Library/Application Support/")
    elif os_name == "Linux":
        path = os.path.expanduser("~/")
    else:
        raise Exception(
            "Please set database save path by '--base_path' option. (ex. ./run_asns --base_path=/home/user/asns/)"
        )
    return path


root_path = os.path.join(get_path(), f'{"." if os_name == "Linux" else ""}asns')


def to_bytes(something, encoding="utf8") -> bytes:
    """
    cast string to bytes() like object, but for python2 support it's bytearray copy
    """
    if isinstance(something, bytes):
        return something
    if isinstance(something, str):
        return something.encode(encoding)
    elif isinstance(something, bytearray):
        return bytes(something)
    else:
        raise TypeError("Not a string or bytes like object")


def sha256(x: Union[bytes, str]) -> bytes:
    x = to_bytes(x, "utf8")
    return bytes(hashlib.sha256(x).digest())


def sha256d(x: Union[bytes, str]) -> bytes:
    x = to_bytes(x, "utf8")
    return bytes(sha256(sha256(x)))


class ErrorMessages(Enum):
    TOKEN_INVALID = "Token is not registered or is invalid."
    TOKEN_STATUS_INVALID = "Inappropriate token status."
    TOKEN_USED = "Token is already used."
    UPDATE_TOKEN = "Failed to update token status: "
    UPDATE_SWAP = "Failed to update swap data: "
    SWAP_INVALID = "Selected swap is not registered or is invalid."
    SWAP_PROGRESS = "Selected swap is already in progress or completed."


class ResponseStatus(Enum):
    SUCCESS = "Success"
    FAILED = "Failed"
