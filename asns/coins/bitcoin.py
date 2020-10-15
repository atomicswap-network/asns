from .base import CoinBaseData


class Bitcoin(CoinBaseData):
    symbol = "BTC"
    insight = ["https://api.bitcore.io/api/BTC/mainnet/"]
    blockbook = ["https://btc1.trezor.io/api/", "https://btc2.trezor.io/api/", "https://btc3.trezor.io/api/"]
    electrumx = {"electrum.blockstream.info": {"s": 50002, "t": 50001}, "b.1209k.com": {"s": 50002, "t": 50001}}
    p2pkh_prefix = b"\x00"
    p2sh_prefix = b"\x05"
    bech32_prefix = "bc"
