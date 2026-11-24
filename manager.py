from iss_moex import load_coupons, load_amortizations, load_offers, load_bonds, load_prices, get_paged, load_securities
from models import Coupon, Amortization, Offer, Bond, Price, Security
from datetime import date


def get_coupons(*, sec_id: str) -> list[Coupon]:
    return [Coupon(**row) for row in get_paged(fn=load_coupons, sec_id=sec_id)]


def get_amortizations(*, sec_id: str) -> list[Amortization]:
    return [Amortization(**row) for row in get_paged(fn=load_amortizations, sec_id=sec_id)]


def get_offers(*, sec_id: str) -> list[Offer]:
    return [Offer(**row) for row in get_paged(fn=load_offers, sec_id=sec_id)]


def get_prices(*, sec_id: str, board_id: str, start: date, till: date) -> list[Price]:
    results = get_paged(
            fn=load_prices,
            engine='stock',
            market='bonds',
            sec_id=sec_id,
            board_id=board_id,
            start=start,
            till=till
        )
    return [
        Price(**row) for row in results
    ]


def get_securities(*,  engine: str, market: str, q: str) -> list[Security]:
    return [
        Security(**row) for row in get_paged(
            fn=load_securities,
            engine=engine,
            market=market,
            q=q,
        )
    ]
