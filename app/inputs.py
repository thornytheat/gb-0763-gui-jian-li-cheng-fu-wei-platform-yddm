import json

from flask import request

from app.config import SAMPLES
from app.errors import TrackError

SAMPLE_NAMES = ('dirty', 'clean', 'meter')
SOURCES = ('sample', 'csv')


def sample(name):
    if name not in SAMPLE_NAMES:
        raise TrackError('NO_SAMPLE', 404)
    return (SAMPLES / f'{name}.csv').read_bytes()


def published_meters(name):
    """样例随附的换表记录；只有换表样例带记录。"""
    document = json.loads((SAMPLES / 'meters.json').read_text(encoding='utf-8'))
    return document.get(name)


def _body():
    body = request.get_json(silent=True)
    if not isinstance(body, dict) or set(body) - {*SOURCES, 'meters'}:
        raise TrackError('BAD_BODY')
    return body


def _choice():
    if request.method == 'GET':
        name = request.args.get('sample', 'dirty')
        return sample(name), published_meters(name)
    body = _body()
    if len([key for key in SOURCES if key in body]) != 1:
        raise TrackError('BAD_BODY')
    if 'csv' in body:
        try:
            raw = body['csv'].encode('utf-8')
        except (AttributeError, UnicodeEncodeError) as exc:
            raise TrackError('BAD_CSV') from exc
        return raw, body.get('meters')
    if isinstance(body.get('sample'), str):
        name = body['sample']
        return sample(name), published_meters(name) if 'meters' not in body else body['meters']
    raise TrackError('BAD_BODY')


def resolved():
    """一次解析取回报文与换表记录，避免同一请求体被读两遍。"""
    return _choice()
