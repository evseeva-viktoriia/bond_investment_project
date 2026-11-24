from pydantic import BaseModel, Field
from datetime import date
from typing import Optional


class Coupon(BaseModel):
    coupon_date: date = Field(..., alias='coupondate')
    record_date: Optional[date] = Field(..., alias='recorddate')
    start_date: date = Field(..., alias='startdate')
    value_prc: Optional[float] = Field(..., alias='valueprc')
    value: Optional[float] = Field(..., alias='value')
    value_rub: Optional[float] = Field(..., alias='value_rub')


class Amortization(BaseModel):
    isin: str = Field(..., alias='isin')
    sec_id: str = Field(..., alias='secid')
    initial_face_value: float = Field(..., alias='initialfacevalue')
    face_unit: str = Field(..., alias='faceunit')
    amort_date: date = Field(..., alias='amortdate')
    value: float = Field(..., alias='value')
    value_rub: float = Field(..., alias='value_rub')
    data_source: str = Field(..., alias='data_source')


class Offer(BaseModel):
    offer_date: date = Field(..., alias='offerdate')
    offer_date_start: float = Field(..., alias='offerdatestart')
    offer_date_end: date = Field(..., alias='offerdateend')
    value_rub: float = Field(..., alias='value_rub')
    price: float = Field(..., alias='price')
    value: float = Field(..., alias='value')
    agent: str = Field(..., alias='agent')
    offertype: str = Field(..., alias='offertype')


class Bond:
    isin: str = Field(..., alias='ISIN')
    sec_id: str = Field(..., alias='SECID')
    face_value: float = Field(..., alias='FACEVALUE')
    face_unit: str = Field(..., alias='faceunit')
    coupons: list[Coupon] = Field([])
    amortizations: list[Amortization] = Field([])
    offers: list[Offer] = Field([])

    def __init__(self, coupons: list[Coupon], amortizations: list[Amortization], offers: list[Offer]):
        self.coupons = coupons
        self.amortizations = amortizations
        self.offers = offers
        last_amortizations = amortizations[-1]
        self.isin = last_amortizations.isin
        self.sec_id = last_amortizations.sec_id
        self.face_unit = last_amortizations.face_unit
        self.initial_face_value = last_amortizations.initial_face_value
        self.maturity_date = last_amortizations.amort_date


class Price(BaseModel):
    trade_date: date = Field(..., alias='TRADEDATE')
    legal_close_price: Optional[float] = Field(..., alias='LEGALCLOSEPRICE')
    mat_date: date = Field(..., alias='MATDATE')
    sec_id: str = Field(..., alias='SECID')
    face_value: float = Field(..., alias='FACEVALUE')
    duration: Optional[float] = Field(..., alias='DURATION')
    acc_int: float = Field(..., alias='ACCINT', description='Accrued coupon in currency')


class Security(BaseModel):
    sec_id: str = Field(..., alias='secid')
    board_id: str = Field(..., alias='primary_boardid')