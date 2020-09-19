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

import logging
import sys
import os
import secrets
import time

from responder import API as ResponderAPI
from responder.models import Request, Response
from uvicorn import Config, Server
from pycoin.encoding import b58
from typing import Dict

from .db import SwapStatus, TokenDB, TokenDBData, TxDB, TxDBData
from .util import sha256d

tx_db = TxDB()
token_db = TokenDB()


async def api_spawn(app, **kwargs) -> None:
    config = Config(app, **kwargs)
    server = Server(config=config)

    if (config.reload or config.workers > 1) and not isinstance(app, str):
        logger = logging.getLogger("uvicorn.error")
        logger.warn(
            "You must pass the application as an import string to enable 'reload' or 'workers'."
        )
        sys.exit(1)

    if config.should_reload or config.workers > 1:
        logger = logging.getLogger("s4.error")
        logger.warn(
            "S4 not supposed to use 'workers' and 'reload'."
        )
        sys.exit(1)
    else:
        config.setup_event_loop()
        await server.serve()


class API(ResponderAPI):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    async def serve(self, *, address=None, port=None, debug=False, **options):
        if "PORT" in os.environ:
            port = int(os.environ["PORT"])

        if address is None:
            address = "0.0.0.0"
        if port is None:
            port = 8000

        await api_spawn(self, host=address, port=port, debug=debug, **options)

    async def run(self, **kwargs):
        if "debug" not in kwargs:
            kwargs.update({"debug": self.debug})
        await self.serve(**kwargs)


api = s4_api = API()


@api.route("/")
def server_info(_: Request, resp: Response) -> None:
    resp.media = {
        "message": "This server is working."
    }


@api.route("/get_token/")
def get_token(_: Request, resp: Response) -> None:
    raw_token = secrets.token_bytes(64)
    token = b58.b2a_base58(raw_token)
    hashed_token = sha256d(raw_token)
    created_at = int(time.time())
    result = {
        "code": "Success",
        "token": token
    }

    try:
        token_db.put(hashed_token, TokenDBData(created_at))
    except Exception as e:
        result = {
            "code": "Failed",
            "token": None,
            "error": str(e)
        }

    resp.media = result


@api.route("/verify_token/{token}")
def verify_token(_: Request, resp: Response, token: str) -> None:
    try:
        exist = token_db.verify_token(token)
    except Exception:
        exist = False

    result = {
        "code": "Success",
        "exist": exist
    }

    resp.media = result


@api.route("/register_swap/")
async def register_token(req: Request, resp: Response) -> None:
    request: Dict = await req.media()
    token: str = request.get("token")
    try:
        exist = token_db.verify_token(token)
    except Exception:
        exist = False

    raw_token = b58.a2b_base58(token)
    hashed_token = sha256d(raw_token)
    try:
        used = bool(tx_db.get(hashed_token))
    except Exception:
        used = False

    if not exist:
        result = {
            "code": "Failed",
            "error": "Token is not registered or is invalid."
        }
    elif used:
        result = {
            "code": "Failed",
            "error": "Token is already used."
        }
    else:
        want_currency: str = request.get("wantCurrency")
        want_amount: int = request.get("wantAmount")
        send_currency: str = request.get("sendCurrency")
        send_amount: int = request.get("sendAmount")
        receive_address: str = request.get("receiveAddress")
        try:
            if want_amount.count(".") or send_amount.count("."):
                raise  # amount type isn't int...
            want_amount = int(want_amount)
            send_amount = int(send_amount)
        except Exception:
            pass

        # TODO: Receive Address Validation
        if not (
                isinstance(want_currency, str) and
                isinstance(want_amount, int) and
                isinstance(send_currency, str) and
                isinstance(send_amount, int) and
                isinstance(receive_address, str)
        ):
            result = {
                "code": "Failed",
                "error": "Request data is invalid."
            }
        else:
            data = TxDBData(
                i_currency=want_currency,
                i_receive_amount=send_amount,
                p_currency=send_currency,
                p_receive_amount=want_amount,
                p_addr=receive_address
            )
            try:
                tx_db.put(hashed_token, data)
                result = {
                    "code": "Success"
                }
            except Exception as e:
                result = {
                    "code": "Failed",
                    "error": str(e)
                }

    resp.media = result


@api.route("/get_swap_list/")
def get_swap_list(_: Request, res: Response) -> None:
    all_list = tx_db.get_all()
    result = {}
    for key in all_list.keys():
        value = all_list[key]
        if value.swap_status == SwapStatus.REGISTERED:
            result[key.hex()] = {
                "initiator_currency": value.i_currency,
                "initiator_receive_amount": value.i_receive_amount,
                "participator_currency": value.p_currency,
                "participator_receive_amount": value.p_receive_amount,
                "participator_address": value.p_addr
            }

    res.media = result
