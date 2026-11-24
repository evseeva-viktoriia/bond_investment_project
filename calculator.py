import polars as pl
from manager import get_securities, get_coupons, get_amortizations, get_prices
from typing import TypeVar, List
from pydantic import BaseModel
from datetime import date
import tqdm

M = TypeVar('M', bound=BaseModel)
TQOB = 'TQOB'
FIXED_BOND = 'SU26'
FLOATING_BONDS = 'SU29'

# Illiquid bonds
BAN_LIST = [
    'SU26231RMFS9',
    'SU26245RMFS9',
    'SU26248RMFS3',
    'SU26249RMFS1',
    'SU26250RMFS9',
    'SU26251RMFS7',
    'SU26254RMFS1',
    'SU29026RMFS0',
    'SU29027RMFS8',
    'SU29028RMFS6',
    'SU29029RMFS4',
    'SU26252RMFS5',
    'SU26253RMFS3',
    'SU26246RMFS7',
    'SU26247RMFS5',
]
YEAR = 252 # trade days
HORIZONS = [YEAR // 2, YEAR, YEAR * 2]

processing = lambda l, text: tqdm.tqdm(l, colour='GREEN', desc=text, ncols=100)


def to_df(data: List[M]) -> pl.DataFrame:
    return pl.DataFrame([d.model_dump() for d in data])


def prepare_ofz_list() -> pl.DataFrame:
    ofzs = to_df(get_securities(engine='stock', market='bonds', q='ОФЗ'))
    return ofzs.filter(
        pl.col('board_id')==TQOB,
        pl.col('sec_id').str.starts_with('SU')
    )


def prepare_eod_prices(sec_ids, start_date: date, end_date: date) -> pl.DataFrame:
    result = []
    for sec_id in processing(sec_ids, 'Loading EOD prices'):
        prices = to_df(get_prices(sec_id=sec_id, board_id=TQOB, start=start_date, till=end_date))
        if len(prices) > 0:
            result.append(prices)
    return pl.concat(result)


def prepare_coupons(sec_ids) -> pl.DataFrame:
    result = []
    for sec_id in processing(sec_ids, 'Loading coupons'):
        coupons = to_df(get_coupons(sec_id=sec_id))
        if len(coupons) > 0:
            result.append(coupons.with_columns(pl.lit(sec_id).alias('sec_id')))
    return pl.concat(result)


def prepare_amortizations(sec_ids) -> pl.DataFrame:
    result = []
    for sec_id in processing(sec_ids, 'Loading amortizations'):
        amortizations = to_df(get_amortizations(sec_id=sec_id))
        if len(amortizations) > 0:
            result.append(amortizations.with_columns(pl.lit(sec_id).alias('sec_id')))
    return pl.concat(result)


def calculate_horizon_yields(*, prices: pl.DataFrame, coupons: pl.DataFrame, amortizations: pl.DataFrame, horizons: list[int]) -> pl.DataFrame:
    return (
        prices.select('sec_id', 'date', 'close', 'acc_int', 'mat_date', 'face_value', 'duration')
        # add coupons if any
        .join(coupons.select('sec_id', 'date', 'coupon_rub'), on=['sec_id', 'date'], how='left').with_columns(pl.col('coupon_rub').fill_null(0))
        # add amortizations if any
        .join(amortizations.select('sec_id', 'amort_rub', 'date'), on=['sec_id', 'date'], how='left').with_columns(pl.col('amort_rub').fill_null(0))
        .with_columns(
            pl.when(pl.col('mat_date') == pl.col('date')).then(pl.lit(0)).otherwise(pl.col('amort_rub')).alias('amort_rub')
        )
        # calculate dirty price = clean price / 100 * notional  + accrued
        .with_columns((pl.col('close') / 100 * pl.col('face_value') + pl.col('acc_int')).alias('dirty_price'))
        # add coupon or amortization payments
        .with_columns((pl.col('coupon_rub') + pl.col('amort_rub')).alias('payment_rub'))
        # how many securities we can buy for payment (if any)
        .with_columns((pl.col('payment_rub') / pl.col('dirty_price')).alias('delta_per_one'))
        .select('sec_id', 'date', 'close', 'acc_int', 'mat_date', 'face_value', 'coupon_rub', 'amort_rub', 'dirty_price', 'payment_rub', 'delta_per_one', 'duration')
        .sort(['sec_id', 'date'], descending=[False, False])
        # calculate cumulated quantity
        .with_columns((pl.col('delta_per_one') + 1).cum_prod().over('sec_id').alias('qty'))

        # calculate quantity AFTER horizon
        .with_columns(
            pl.col('qty').shift(-h).over('sec_id').alias(f'q{h}_2')
            for h in horizons
        )
        .with_columns(
            (pl.col(f'q{h}_2') / pl.col('qty')).alias(f'q{h}')
            for h in horizons
        )
        .with_columns(
            (
                    pl.col('dirty_price').shift(-h).over('sec_id') *
                    pl.col('qty').shift(-h).over('sec_id') /
                    pl.col('qty')
            ).alias(f'pos{h}')
            for h in horizons
        )
        # add horizon yield
        .with_columns(
            (
                    # how much does your position cost after horizon
                    pl.col('dirty_price').shift(-h).over('sec_id') *
                    pl.col('qty').shift(-h).over('sec_id') /
                    # how myuch does your position cost now
                    (pl.col('qty') * pl.col('dirty_price'))
                    - 1
            ).alias(f'hy{h}')
            for h in horizons
        )
        .with_columns(
            pl.col('date').shift(-h).over('sec_id', order_by='date').alias(f'date{h}')
            for h in horizons
        )
        .sort('sec_id', 'date')
    )


def report(start_date: date, end_date: date):
    ofzs = prepare_ofz_list()
    ofzs = ofzs.filter(pl.col('sec_id').str.starts_with(FIXED_BOND) | pl.col('sec_id').str.starts_with(FLOATING_BONDS))
    sec_ids = ofzs['sec_id'].to_list()
    prices = prepare_eod_prices(sec_ids, start_date=start_date, end_date=end_date)
    prices = prices.rename({'legal_close_price': 'close', 'trade_date': 'date'})
    prices = prices.filter(~pl.col('sec_id').is_in(BAN_LIST))
    prices = prices.with_columns(pl.col('close').forward_fill().over('sec_id'))

    sec_ids = prices['sec_id'].unique().to_list()
    coupons = prepare_coupons(sec_ids)
    coupons = coupons.rename({'coupon_date': 'date', 'value_rub': 'coupon_rub'})
    amortizations = prepare_amortizations(sec_ids)
    amortizations = amortizations.rename({'amort_date': 'date', 'value_rub': 'amort_rub'})

    horizon_yields = calculate_horizon_yields(prices=prices, coupons=coupons, amortizations=amortizations, horizons=HORIZONS)
    horizon_yields.write_excel('./report/horizon_yields.xlsx', autofit=True, autofilter=True)


if __name__ == '__main__':
    report(
        start_date = date(2015, 1, 1),
        end_date = date(2026, 2, 20),
    )