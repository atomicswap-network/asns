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

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from uvicorn import Config, Server
from pycoin.encoding import b58
from typing import Dict, Optional, Union, Any, List

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


class API(FastAPI):
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


class RegisterSwapItem(BaseModel):
    token: str
    wantCurrency: str
    wantAmount: Union[int, float]
    sendCurrency: str
    sendAmount: Union[int, float]
    receiveAddress: str


@api.exception_handler(RequestValidationError)
async def validation_exception_handler(_: Request, exc: RequestValidationError):
    err_msg: List[str] = []
    target_requests: List[List[str]] = []
    for err in exc.errors():
        msg = err["msg"]
        if msg not in err_msg:
            err_msg.append(msg)
        msg_index = err_msg.index(msg)
        target = err["loc"][1]
        try:
            target_requests[msg_index].append(target)
        except IndexError:
            target_requests.append([target])

    result: List[Dict[str, Union[str, List[str]]]] = []
    for i in range(len(err_msg)):
        err = {
            "message": err_msg[i],
            "target": target_requests[i]
        }
        result.append(err)
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=jsonable_encoder({"code": "Failed", "error": result}),
    )


@api.get("/")
def server_info() -> Dict[str, str]:
    return {
        "message": "This server is working."
    }


@api.get("/get_token/")
def get_token() -> Union[Dict[str, Union[str, Any]], Dict[str, Optional[str]]]:
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

    return result


@api.get("/verify_token/{token}")
def verify_token(token: str) -> Dict[str, Union[str, bool]]:
    try:
        exist = token_db.verify_token(token)
    except Exception:
        exist = False

    return {
        "code": "Success",
        "exist": exist
    }


@api.post("/register_swap/")
async def register_token(item: RegisterSwapItem) -> Dict[str, str]:
    token: str = item.token

    exist = False
    used = False

    try:
        exist = token_db.verify_token(token)
    except Exception:
        pass

    if exist:
        raw_token = b58.a2b_base58(token)
        hashed_token = sha256d(raw_token)
        try:
            used = bool(tx_db.get(hashed_token))
        except Exception:
            pass

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
        want_currency = item.wantCurrency
        want_amount = item.wantAmount
        send_currency = item.sendCurrency
        send_amount = item.sendAmount
        receive_address = item.receiveAddress

        try:
            if str(want_amount).count(".") or str(send_amount).count("."):
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

    return result


@api.get("/get_swap_list/")
def get_swap_list() -> Dict[str, Dict[str, Union[str, int]]]:
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

    return result
