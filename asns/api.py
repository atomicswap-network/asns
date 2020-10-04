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

import logging
import sys
import os
import secrets
import time
import binascii

from fastapi import FastAPI, Depends, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel
from uvicorn import Config, Server
from pycoin.encoding import b58
from typing import Dict, Union, List, Optional

from .db import SwapStatus, TokenStatus, TokenDB, TokenDBData, TxDB, TxDBData
from .util import sha256d


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
        logger = logging.getLogger("asns.error")
        logger.warn(
            "ASNS not supposed to use 'workers' and 'reload'."
        )
        sys.exit(1)
    else:
        config.setup_event_loop()
        await server.serve()


class API(FastAPI):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.db_base_path = None

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


api = asns_api = API()


class TokenItem(BaseModel):
    token: str


class RegisterSwapItem(TokenItem):
    wantCurrency: str
    wantAmount: int
    sendCurrency: str
    sendAmount: int
    receiveAddress: str


class InitiateSwapItem(TokenItem):
    selectedSwap: str
    rawTransaction: str
    receiveAddress: str


class ParticipateSwapItem(TokenItem):
    rawTransaction: str


@api.exception_handler(StarletteHTTPException)
async def http_exception_handler(_: Request, exc: StarletteHTTPException):
    return JSONResponse(
        content=jsonable_encoder({"status": "Failed", "error": str(exc.detail)})
    )


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
        content=jsonable_encoder({"status": "Failed", "error": result}),
    )


class DBCommons:
    def __init__(self) -> None:
        self.tx_db = TxDB(api.db_base_path)
        self.token_db = TokenDB(api.db_base_path)

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
            equal_status = token_data.token_status in token_status
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


@api.get("/")
async def server_info() -> JSONResponse:
    result = {
        "message": "This server is working."
    }

    return JSONResponse(content=jsonable_encoder(result))


@api.get("/get_token/")
async def get_token(commons: DBCommons = Depends()) -> JSONResponse:
    status_code = status.HTTP_200_OK
    raw_token = secrets.token_bytes(64)
    token = b58.b2a_base58(raw_token)
    hashed_token = sha256d(raw_token)
    created_at = int(time.time())
    result = {
        "status": "Success",
        "token": token
    }

    try:
        commons.token_db.put(hashed_token, TokenDBData(created_at))
    except Exception as e:
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        result = {
            "status": "Failed",
            "token": None,
            "error": str(e)
        }

    return JSONResponse(status_code=status_code, content=jsonable_encoder(result))


@api.post("/verify_token/")
async def verify_token(item: TokenItem, commons: DBCommons = Depends()) -> JSONResponse:
    token = item.token
    try:
        exist, create_at = commons.token_db.verify_token(token)
    except Exception:
        exist, create_at = False, None

    result = {
        "status": "Success",
        "exist": exist,
        "create_at": create_at
    }

    return JSONResponse(content=jsonable_encoder(result))


@api.post("/register_swap/")
async def register_swap(item: RegisterSwapItem, commons: DBCommons = Depends()) -> JSONResponse:
    token = item.token

    status_code = status.HTTP_200_OK
    msg = commons.token_status_msg(token, [TokenStatus.NOT_USED])

    if msg:
        status_code = status.HTTP_400_BAD_REQUEST
        result = {
            "status": "Failed",
            "error": msg
        }
    else:
        want_currency = item.wantCurrency
        want_amount = item.wantAmount
        send_currency = item.sendCurrency
        send_amount = item.sendAmount
        receive_address = item.receiveAddress

        # TODO: Receive Address Validation
        # TODO: Want/Send Currency Validation

        swap_data = TxDBData(
            i_currency=want_currency,
            i_receive_amount=send_amount,
            p_currency=send_currency,
            p_receive_amount=want_amount,
            p_addr=receive_address
        )

        raw_token = b58.a2b_base58(token)
        hashed_token = sha256d(raw_token)

        err = commons.change_token_status(hashed_token, TokenStatus.PARTICIPATOR)

        try:
            if err:
                raise Exception(err)
            commons.tx_db.put(hashed_token, swap_data)
            result = {
                "status": "Success"
            }
        except Exception as e:
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            result = {
                "status": "Failed",
                "error": str(e)
            }

    return JSONResponse(status_code=status_code, content=jsonable_encoder(result))


@api.get("/get_swap_list/")
async def get_swap_list(commons: DBCommons = Depends()) -> JSONResponse:
    status_code = status.HTTP_200_OK
    try:
        all_list = commons.tx_db.get_all()
        result = {
            "status": "Success",
            "data": {}
        }
    except Exception:
        all_list = {}
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        result = {
            "status": "Failed",
            "data": {}
        }
    for key in all_list.keys():
        value = all_list[key]
        if value.swap_status == SwapStatus.REGISTERED:
            result["data"][key.hex()] = {
                "initiatorCurrency": value.i_currency,
                "initiatorReceiveAmount": value.i_receive_amount,
                "participatorCurrency": value.p_currency,
                "participatorReceiveAmount": value.p_receive_amount,
                "participatorAddress": value.p_addr
            }

    return JSONResponse(status_code=status_code, content=jsonable_encoder(result))


@api.post("/initiate_swap/")
async def initiate_swap(item: InitiateSwapItem, commons: DBCommons = Depends()) -> JSONResponse:
    token = item.token
    status_code = status.HTTP_200_OK

    msg = commons.token_status_msg(token, [TokenStatus.NOT_USED])
    selected_swap_key = None
    selected_swap_data = None

    if msg is None:
        try:
            selected_swap_key = binascii.a2b_hex(item.selectedSwap)
            selected_swap_data = commons.tx_db.get(selected_swap_key)
        except Exception:
            pass

    if selected_swap_data is None:
        msg = "Selected swap is not registered or is invalid."

    if selected_swap_data.swap_status != SwapStatus.REGISTERED:
        msg = "Selected swap is already in progress or completed."

    if msg:
        status_code = status.HTTP_400_BAD_REQUEST
        result = {
            "status": "Failed",
            "error": msg
        }
    else:
        initiate_raw_tx = item.rawTransaction
        receive_address = item.receiveAddress

        raw_token = b58.a2b_base58(token)
        hashed_token = sha256d(raw_token)

        selected_swap_data.swap_status = SwapStatus.INITIATED
        selected_swap_data.i_raw_tx = initiate_raw_tx  # TODO: Raw Transaction Validation
        selected_swap_data.i_addr = receive_address  # TODO: Receive Address Validation
        selected_swap_data.i_token_hash = hashed_token

        err = commons.change_token_status(hashed_token, TokenStatus.INITIATOR)

        try:
            if err:
                raise Exception(err)
            commons.tx_db.put(selected_swap_key, selected_swap_data)
            result = {
                "status": "Success"
            }
        except Exception as e:
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            result = {
                "status": "Failed",
                "error": str(e)
            }

    return JSONResponse(status_code=status_code, content=jsonable_encoder(result))


@api.post("/get_initiator_info/")
async def get_initiator_info(item: TokenItem, commons: DBCommons = Depends()) -> JSONResponse:
    token = item.token

    status_code = status.HTTP_200_OK
    msg = commons.token_status_msg(token, [TokenStatus.INITIATOR, TokenStatus.PARTICIPATOR])

    if msg:
        status_code = status.HTTP_400_BAD_REQUEST
        result = {
            "status": "Failed",
            "error": msg
        }
    else:
        raw_token = b58.a2b_base58(token)
        hashed_token = sha256d(raw_token)

        if SwapStatus.REGISTERED < (swap_data := commons.tx_db.get(hashed_token)).swap_status < SwapStatus.COMPLETED:
            initiator_address = swap_data.i_addr
            token_hash = swap_data.i_token_hash
            result = {
                "status": "Success",
                "initiatorAddress": initiator_address,
                "tokenHash": token_hash
            }
        else:
            status_code = status.HTTP_400_BAD_REQUEST
            result = {
                "status": "Failed",
                "initiatorAddress": None,
                "tokenHash": None,
                "error": "Swap has not initiated or has already completed."
            }

    return JSONResponse(status_code=status_code, content=jsonable_encoder(result))


@api.post("/participate_swap/")
async def participate_swap(item: ParticipateSwapItem, commons: DBCommons = Depends()) -> JSONResponse:
    token = item.token

    status_code = status.HTTP_200_OK
    msg = commons.token_status_msg(token, [TokenStatus.PARTICIPATOR])

    raw_token = b58.a2b_base58(token)
    hashed_token = sha256d(raw_token)

    swap_data = None

    if msg is None:
        try:
            swap_key = binascii.a2b_hex(hashed_token)
            swap_data = commons.tx_db.get(swap_key)
        except Exception:
            pass

    if swap_data is None:
        msg = "Token Hash doesn't have swap transaction."

    if swap_data.swap_status != SwapStatus.INITIATED:
        msg = "Selected swap is already in progress or completed."

    if msg:
        status_code = status.HTTP_400_BAD_REQUEST
        result = {
            "status": "Failed",
            "error": msg
        }
    else:
        participate_raw_tx = item.rawTransaction

        swap_data.swap_status = SwapStatus.PARTICIPATED
        swap_data.p_raw_tx = participate_raw_tx  # TODO: Raw Transaction Validation

        try:
            commons.tx_db.put(hashed_token, swap_data)
            result = {
                "status": "Success"
            }
        except Exception as e:
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
            result = {
                "status": "Failed",
                "error": str(e)
            }

    return JSONResponse(status_code=status_code, content=jsonable_encoder(result))

