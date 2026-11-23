"""换表记录与两侧基点的对账。

巡检车换表后测距归零，读数下降与倒车外观相同。只有落在两侧基点之间、
并且两端读数都能由换表单的「换前/换后」读数接上的记录，才允许把这一段
续接起来；接不上就整段留缺，不能只按读数差硬算。
"""
from datetime import datetime, timezone

from app.errors import TrackError

FIELDS = ('at', 'before_mm', 'after_mm')


def _instant(value):
    if not isinstance(value, str):
        raise TrackError('BAD_METER')
    try:
        at = datetime.fromisoformat(value)
    except ValueError as exc:
        raise TrackError('BAD_METER') from exc
    if at.utcoffset() is None:
        raise TrackError('BAD_METER')
    return at.astimezone(timezone.utc).isoformat()


def _count(value):
    if isinstance(value, bool):
        raise TrackError('BAD_METER')
    try:
        number = int(value)
    except (TypeError, ValueError) as exc:
        raise TrackError('BAD_METER') from exc
    if not 0 <= number <= 10**12:
        raise TrackError('BAD_METER')
    return number


def timeline(records):
    """按车次归拢换表记录，时间统一到 UTC；同一时标只允许一条。"""
    if records is None:
        return {}
    if not isinstance(records, list):
        raise TrackError('BAD_METER')
    grouped = {}
    for order, record in enumerate(records):
        if not isinstance(record, dict):
            raise TrackError('BAD_METER')
        try:
            run = record['run']
            at = _instant(record['at'])
            before = _count(record['before_mm'])
            after = _count(record['after_mm'])
        except KeyError as exc:
            raise TrackError('BAD_METER') from exc
        if not isinstance(run, str) or not run.strip():
            raise TrackError('BAD_METER')
        ticket = record.get('ticket', '')
        if ticket is None:
            ticket = ''
        if not isinstance(ticket, str):
            raise TrackError('BAD_METER')
        grouped.setdefault(run, []).append({'at': at, 'before_mm': before, 'after_mm': after,
                                            'ticket': ticket, 'order': order})
    for run, items in grouped.items():
        items.sort(key=lambda item: (item['at'], item['order']))
        if len({item['at'] for item in items}) != len(items):
            raise TrackError('BAD_METER')
    return grouped


def normalized(records):
    """换表记录的规范形态：去掉文件顺序，只留可复算字段，供归档键使用。"""
    grouped = timeline(records)
    return [{'run': run, **{key: item[key] for key in ('at', 'before_mm', 'after_mm', 'ticket')}}
            for run in sorted(grouped) for item in grouped[run]]


def splice(left, right, changes):
    """用区间内的换表记录把左右基点接成一条连续测距；接不上就返回 None。

    读数在每个区段内必须不降；换表点右开，右端基点取换表后的表。
    """
    if not changes:
        return None
    legs, offset = [], 0
    start_at, start_odo = left['at'], left['odo_mm']
    for change in changes:
        if change['at'] < start_at or change['at'] > right['at'] or change['before_mm'] < start_odo:
            return None
        legs.append({'start_at': start_at, 'end_at': change['at'], 'start_odo': start_odo,
                     'end_odo': change['before_mm'], 'offset_mm': offset})
        offset += change['before_mm'] - start_odo
        start_at, start_odo = change['at'], change['after_mm']
        if change['at'] == right['at']:
            if right['odo_mm'] != change['after_mm']:
                return None
            if offset <= 0:
                return None
            return {'distance_mm': offset, 'legs': legs,
                    'changes': [{key: item[key] for key in ('at', 'before_mm', 'after_mm', 'ticket')}
                                for item in changes]}
    if right['odo_mm'] < start_odo:
        return None
    legs.append({'start_at': start_at, 'end_at': right['at'], 'start_odo': start_odo,
                 'end_odo': right['odo_mm'], 'offset_mm': offset})
    offset += right['odo_mm'] - start_odo
    if offset <= 0:
        return None
    return {'distance_mm': offset, 'legs': legs,
            'changes': [{key: item[key] for key in ('at', 'before_mm', 'after_mm', 'ticket')}
                        for item in changes]}


def offset_of(reset, event):
    """换表区段内的有效测距：按报文时标选用换表前或换表后的表，左闭右开。"""
    for leg in reset['legs']:
        if leg['start_at'] <= event['at'] < leg['end_at']:
            if not leg['start_odo'] <= event['odo_mm'] <= leg['end_odo']:
                return None
            value = leg['offset_mm'] + event['odo_mm'] - leg['start_odo']
            return value if 0 <= value < reset['distance_mm'] else None
    return None
