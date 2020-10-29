# Copyright (c) 2011-2020 The Electrum Developers
# Copyright (c) 2020 The Atomic Swap Network Developers
# Licensed under the GNU General Public License, Version 3.

import platform
import os
import hashlib

from typing import Union

os_name = platform.system()
pkg_dir = os.path.split(os.path.realpath(__file__))[0]


def resource_path(*parts):
    return os.path.join(pkg_dir, *parts)


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


def hash160(x: Union[bytes, str]) -> bytes:
    x = to_bytes(x, "utf8")
    h160 = hashlib.new("ripemd160")
    h160.update(sha256(x))
    out = h160.digest()
    return bytes(out)
