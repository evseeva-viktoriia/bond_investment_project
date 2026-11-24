from datetime import date, datetime
from httpx import Client
from typing import Callable, Union, Optional
import ssl

BASE_URL = 'https://iss.moex.com/iss'
CERTIFICATE = './certificate/Russian_Trusted_CA_2024.pem'
Results = list[dict[str, date | str | int | float | bool]]
DATE_FORMAT = '%Y-%m-%d'

class Paging:
    def __init__(self, page: int, page_size: Optional[int], total: Optional[int]):
        self.page = page
        self.page_size = page_size
        self.total = total

    def move_next_page(self):
        self.page += 1


def get_paged(*, fn: Callable[..., tuple[Results, Paging]], **kwargs) -> Results:
    """Common method to get paged data"""
    results: Results = []
    paging = Paging(page=0, page_size=None, total=None)
    while True:
        res, paging = fn(**kwargs, paging=paging)
        if len(res) == 0:
            break
        results.extend(res)
        paging.move_next_page()
    return results


def get_json(*, url: str, params: dict) -> dict:
    """Common method to request by GET methods returning json"""
    ctx = ssl.create_default_context(cafile=CERTIFICATE)
    ctx.verify_flags |= ssl.VERIFY_X509_PARTIAL_CHAIN
    with Client(verify=ctx, timeout=60.) as client:
        return client.get(url, params=params).json()


def resolve_type(*, tp: str, value: Union[str, int, bool, float]) -> Union[None, str, int, bool, float, date, datetime]:
    if value is None:
        return None
    if tp == 'date':
        return datetime.strptime(value, '%Y-%m-%d').date()
    return value


def load_paged_block_page(*, url: str, params: dict[str, ...], paging: Paging, block: str, limit: int) -> tuple[Results, Paging]:
    """Common method to get block of data with pagination"""
    block_cursor = block + '.cursor'
    params = params | {
        'iss.only': ','.join([block, block_cursor]),
        'limit': limit,
        'start': paging.page * limit,
    }
    res = get_json(
        url=url,
        params=params
    )
    type_metadata = {field: tp_params['type'] for field, tp_params in res[block]['metadata'].items()}
    if block_cursor not in res:
        page, page_size, total = paging.page, limit, paging.page * limit + 1 # fix
    else:
        page, page_size, total = res[block_cursor]['data'][0]

    return (
        [
            {col: resolve_type(tp=type_metadata[col], value=val) for col, val in zip(res[block]['columns'], row)}
            for row in res[block]['data']
        ],
        Paging(page, page_size, total)
    )


def load_bondization_block(*, sec_id: str, paging: Paging, block: str) -> tuple[Results, Paging]:
    return load_paged_block_page(
        url=f'{BASE_URL}/statistics/engines/stock/markets/bonds/bondization/{sec_id}.json',
        params={},
        paging=paging,
        block=block,
        limit=10,
    )


def load_coupons(*, sec_id: str, paging: Paging) -> tuple[Results, Paging]:
    return load_bondization_block(sec_id=sec_id, paging=paging, block='coupons')


def load_amortizations(*, sec_id: str, paging: Paging) -> tuple[Results, Paging]:
    return load_bondization_block(sec_id=sec_id, paging=paging, block='amortizations')


def load_offers(*, sec_id: str, paging: Paging) -> tuple[Results, Paging]:
    return load_bondization_block(sec_id=sec_id, paging=paging, block='offers')


def load_bonds(*, paging: Paging) -> tuple[Results, Paging]:
    return load_paged_block_page(
        url=f'{BASE_URL}/'
            f'engines/stock/'
            f'markets/bonds/'
            f'securities.json',
        params={
            'primary_board': 1,
        },
        paging=paging,
        block='securities',
        limit=100,
    )


def load_prices(*, engine: str, market: str, board_id:str, sec_id: str, start: date, till: date, paging: Paging) -> tuple[Results, Paging]:
    session = 1
    return load_paged_block_page(
        url=f'{BASE_URL}/history/'
            f'engines/{engine}/'
            f'markets/{market}/'
            f'sessions/{session}/'
            f'boards/{board_id}/'
            f'securities/{sec_id}.json',
        params={
            'engine': 'stock',
            'market': 'bonds',
            'till': till.strftime(DATE_FORMAT),
            'from': start.strftime(DATE_FORMAT),
        },
        paging=paging,
        block='history',
        limit=100,
    )


def load_securities(*, engine: str, market: str, q: str, paging: Paging) -> tuple[Results, Paging]:
    """Load list of securities traded on engine, market."""
    return load_paged_block_page(
        url = f'{BASE_URL}/'
              f'securities.json',
        params={
            'engine': engine,
            'market': market,
            'q': q,
        },
        paging = paging,
        block='securities',
        limit=100,
    )