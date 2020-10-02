# Copyright (c) 2011-2020 The Electrum Developers
# Copyright (c) 2020 The Atomic Swap Network Developers
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

import platform
import os
import hashlib

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

