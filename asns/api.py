# Copyright (c) 2020 The Atomic Swap Network Developers
# Licensed under the GNU General Public License, Version 3.

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
from pycoin.vm.ScriptTools import ScriptTools
from typing import Dict, Union, List

from .db import SwapStatus, TokenStatus, TokenDBData, TxDBData, DBCommons
from .tx import BitcoinTx
from .util import sha256d, ErrorMessages, ResponseStatus


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


async def db_commons():
    return DBCommons(api.db_base_path)


class TokenItem(BaseModel):
    token: str


class TokenAndSelectedSwapItem(TokenItem):
    selectedSwap: str


class TokenAndTxItem(TokenItem):
    rawTransaction: str


class TokenAndTxAndContractItem(TokenAndTxItem):
    contract: str


class RegisterSwapItem(TokenItem):
    wantCurrency: str
    wantAmount: int
    sendCurrency: str
    sendAmount: int
    receiveAddress: str


class InitiateSwapItem(TokenAndTxAndContractItem, TokenAndSelectedSwapItem):
    receiveAddress: str


class RedeemSwapItem(TokenAndTxItem, TokenAndSelectedSwapItem):
    pass


@api.exception_handler(StarletteHTTPException)
async def http_exception_handler(_: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=jsonable_encoder({"status": ResponseStatus.FAILED, "error": str(exc.detail)})
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
        content=jsonable_encoder({"status": ResponseStatus.FAILED, "error": result}),
    )


@api.get("/")
async def server_info() -> JSONResponse:
    result = {
        "message": "This server is working."
    }

    return JSONResponse(content=jsonable_encoder(result))


@api.get("/get_token/")
async def get_token(commons: DBCommons = Depends(db_commons)) -> JSONResponse:
    status_code = status.HTTP_200_OK
    raw_token = secrets.token_bytes(64)
    token = b58.b2a_base58(raw_token)
    hashed_token = sha256d(raw_token)
    created_at = int(time.time())
    result = {
        "status": ResponseStatus.SUCCESS,
        "token": token
    }

    try:
        commons.token_db.put(hashed_token, TokenDBData(created_at))
    except Exception as e:
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        result = {
            "status": ResponseStatus.FAILED,
            "token": None,
            "error": str(e)
        }

    return JSONResponse(status_code=status_code, content=jsonable_encoder(result))


@api.post("/verify_token/")
async def verify_token(item: TokenItem, commons: DBCommons = Depends(db_commons)) -> JSONResponse:
    token = item.token
    try:
        exist, create_at = commons.token_db.verify_token(token)
    except Exception:
        exist, create_at = False, None

    result = {
        "status": ResponseStatus.SUCCESS,
        "exist": exist,
        "create_at": create_at
    }

    return JSONResponse(content=jsonable_encoder(result))


@api.post("/register_swap/")
async def register_swap(item: RegisterSwapItem, commons: DBCommons = Depends(db_commons)) -> JSONResponse:
    token = item.token

    status_code = status.HTTP_200_OK
    msg = commons.token_status_msg(token, [TokenStatus.NOT_USED])

    if msg:
        result = {
            "status": ResponseStatus.FAILED,
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

        result = commons.update_swap(hashed_token, swap_data, err)

    if result.get("error") is not None:
        status_code = status.HTTP_400_BAD_REQUEST

    return JSONResponse(status_code=status_code, content=jsonable_encoder(result))


@api.get("/get_swap_list/")
async def get_swap_list(commons: DBCommons = Depends(db_commons)) -> JSONResponse:
    status_code = status.HTTP_200_OK
    try:
        all_list = commons.tx_db.get_all()
        result = {
            "status": ResponseStatus.SUCCESS,
            "data": {}
        }
    except Exception:
        all_list = {}
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        result = {
            "status": ResponseStatus.FAILED,
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
async def initiate_swap(item: InitiateSwapItem, commons: DBCommons = Depends(db_commons)) -> JSONResponse:
    token = item.token
    status_code = status.HTTP_200_OK

    selected_swap_key = binascii.a2b_hex(item.selectedSwap)
    result, _, selected_swap_data = commons.verify_token_and_get_swap_data(
        token,
        [TokenStatus.NOT_USED],
        SwapStatus.REGISTERED,
        selected_swap_key=selected_swap_key
    )

    if result is None:
        contract = item.contract
        initiate_raw_tx = item.rawTransaction
        receive_address = item.receiveAddress

        raw_token = b58.a2b_base58(token)
        hashed_token = sha256d(raw_token)

        selected_swap_data.swap_status = SwapStatus.INITIATED
        selected_swap_data.i_contract = contract
        selected_swap_data.i_raw_tx = initiate_raw_tx  # TODO: Raw Transaction Validation
        selected_swap_data.i_addr = receive_address  # TODO: Receive Address Validation
        selected_swap_data.i_token_hash = hashed_token

        err = commons.change_token_status(hashed_token, TokenStatus.INITIATOR)

        result = commons.update_swap(selected_swap_key, selected_swap_data, err)

    if result.get("error") is not None:
        status_code = status.HTTP_400_BAD_REQUEST

    return JSONResponse(status_code=status_code, content=jsonable_encoder(result))


@api.post("/get_initiator_info/")
async def get_initiator_info(item: TokenItem, commons: DBCommons = Depends(db_commons)) -> JSONResponse:
    token = item.token

    status_code = status.HTTP_200_OK
    msg = commons.token_status_msg(token, [TokenStatus.PARTICIPATOR])
    if msg == ErrorMessages.TOKEN_USED:
        msg = None

    if msg:
        result = {
            "status": ResponseStatus.FAILED,
            "error": msg
        }
    else:
        raw_token = b58.a2b_base58(token)
        hashed_token = sha256d(raw_token)

        if SwapStatus.REGISTERED < (swap_data := commons.tx_db.get(hashed_token)).swap_status < SwapStatus.COMPLETED:
            initiator_address = swap_data.i_addr
            initiate_contract = swap_data.i_contract
            initiate_tx = swap_data.i_raw_tx
            token_hash = swap_data.i_token_hash
            result = {
                "status": ResponseStatus.SUCCESS,
                "initiatorAddress": initiator_address,
                "initiateContract": initiate_contract,
                "initiateRawTransaction": initiate_tx,
                "tokenHash": token_hash.hex()
            }
        else:
            result = {
                "status": ResponseStatus.FAILED,
                "initiatorAddress": None,
                "tokenHash": None,
                "initiateContract": None,
                "initiateRawTransaction": None,
                "error": ErrorMessages.SWAP_STATUS_INVALID
            }

    if result.get("error") is not None:
        status_code = status.HTTP_400_BAD_REQUEST

    return JSONResponse(status_code=status_code, content=jsonable_encoder(result))


@api.post("/participate_swap/")
async def participate_swap(item: TokenAndTxAndContractItem, commons: DBCommons = Depends(db_commons)) -> JSONResponse:
    token = item.token
    status_code = status.HTTP_200_OK

    result, hashed_token, swap_data = commons.verify_token_and_get_swap_data(
        token,
        [TokenStatus.PARTICIPATOR],
        SwapStatus.INITIATED,
        [ErrorMessages.TOKEN_USED]
    )

    if result is None:
        contract = item.contract
        participate_raw_tx = item.rawTransaction

        swap_data.swap_status = SwapStatus.PARTICIPATED
        swap_data.p_contract = contract
        swap_data.p_raw_tx = participate_raw_tx  # TODO: Raw Transaction Validation

        result = commons.update_swap(hashed_token, swap_data)

    if result.get("error") is not None:
        status_code = status.HTTP_400_BAD_REQUEST

    return JSONResponse(status_code=status_code, content=jsonable_encoder(result))


@api.get("/get_participator_info/")
async def get_participator_info(
        item: TokenAndSelectedSwapItem,
        commons: DBCommons = Depends(db_commons)
) -> JSONResponse:
    token = item.token
    status_code = status.HTTP_200_OK

    selected_swap_key = binascii.a2b_hex(item.selectedSwap)
    result, _, selected_swap_data = commons.verify_token_and_get_swap_data(
        token,
        [TokenStatus.INITIATOR],
        SwapStatus.PARTICIPATED,
        selected_swap_key
    )

    if result is None:
        if SwapStatus.PARTICIPATED < selected_swap_data.swap_status < SwapStatus.COMPLETED:
            participate_contract = selected_swap_data.p_contract
            participate_tx = selected_swap_data.p_raw_tx
            result = {
                "status": "Success",
                "participateContract": participate_contract,
                "participateRawTransaction": participate_tx
            }
        else:
            result = {
                "status": "Failed",
                "participateContract": None,
                "participateRawTransaction": None,
                "error": ErrorMessages.SWAP_STATUS_INVALID
            }

    if result.get("error") is not None:
        status_code = status.HTTP_400_BAD_REQUEST

    return JSONResponse(status_code=status_code, content=jsonable_encoder(result))


@api.post("/redeem_swap/")
async def redeem_swap(item: RedeemSwapItem, commons: DBCommons = Depends(db_commons)) -> JSONResponse:
    token = item.token
    status_code = status.HTTP_200_OK

    selected_swap_key = binascii.a2b_hex(item.selectedSwap)
    result, _, selected_swap_data = commons.verify_token_and_get_swap_data(
        token,
        [TokenStatus.INITIATOR],
        SwapStatus.PARTICIPATED,
        [ErrorMessages.TOKEN_USED],
        selected_swap_key
    )

    if result is None:
        redeem_raw_tx = item.rawTransaction

        selected_swap_data.swap_status = SwapStatus.REDEEMED
        selected_swap_data.i_redeem_raw_tx = redeem_raw_tx  # TODO: Raw Transaction Validation

        result = commons.update_swap(selected_swap_key, selected_swap_data)

    if result.get("error") is not None:
        status_code = status.HTTP_400_BAD_REQUEST

    return JSONResponse(status_code=status_code, content=jsonable_encoder(result))


@api.post("/get_redeem_token/")
async def get_redeem_token(item: TokenItem, commons: DBCommons = Depends(db_commons)) -> JSONResponse:
    token = item.token
    status_code = status.HTTP_200_OK

    result, hashed_token, swap_data = commons.verify_token_and_get_swap_data(
        token,
        [TokenStatus.PARTICIPATOR],
        SwapStatus.REDEEMED,
        [ErrorMessages.TOKEN_USED]
    )

    if result is None:
        redeem_raw_tx: BitcoinTx = BitcoinTx.from_hex(swap_data.i_redeem_raw_tx)
        txs_in: List[BitcoinTx.TxIn] = redeem_raw_tx.txs_in
        token = None
        for tx_in in txs_in:
            parsed_script: List[str] = ScriptTools.opcode_list(tx_in.script)
            for data in parsed_script:
                if data[0] == "[" and data[-1] == "]":
                    pushed_data = binascii.a2b_hex(data[1:-1])
                    hashed_data = sha256d(pushed_data)
                    if swap_data.i_token_hash == hashed_data:
                        token = pushed_data
                        break
                else:
                    continue
        if token is None:
            result = {
                "status": ResponseStatus.FAILED,
                "token": None,
                "error": ErrorMessages.FATAL_ERROR
            }
        else:
            result = {
                "status": ResponseStatus.SUCCESS,
                "token": token.hex()
            }

    if result.get("error") is not None:
        status_code = status.HTTP_400_BAD_REQUEST

    return JSONResponse(status_code=status_code, content=jsonable_encoder(result))


@api.post("/complete_swap/")
async def complete_swap(item: TokenAndTxItem, commons: DBCommons = Depends(db_commons)) -> JSONResponse:
    token = item.token
    status_code = status.HTTP_200_OK

    result, hashed_token, swap_data = commons.verify_token_and_get_swap_data(
        token,
        [TokenStatus.PARTICIPATOR],
        SwapStatus.REDEEMED,
        [ErrorMessages.TOKEN_USED]
    )

    if result is None:
        redeem_raw_tx = item.rawTransaction

        swap_data.swap_status = SwapStatus.COMPLETED
        swap_data.p_redeem_raw_tx = redeem_raw_tx  # TODO: Raw Transaction Validation

        result = commons.update_swap(hashed_token, swap_data)

    if result.get("error") is not None:
        status_code = status.HTTP_400_BAD_REQUEST

    return JSONResponse(status_code=status_code, content=jsonable_encoder(result))

