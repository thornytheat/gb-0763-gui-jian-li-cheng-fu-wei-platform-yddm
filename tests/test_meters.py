import pytest

from app.chainage.interpolate import restore
from app.chainage.meters import normalized, offset_of, splice, timeline
from app.errors import TrackError
from app.inputs import published_meters, sample


def marks(odo_left, odo_right, *, seconds=120, chain_left='UP-A', chain_right='UP-A'):
    left = {'event_id': 'L', 'run': 'R7', 'kind': 'anchor', 'at': '2026-11-22T00:00:00+00:00',
            'odo_mm': odo_left, 'ref': 'A0', 'grade': 3, 'line': 2, 'chain': chain_left,
            'station_mm': 1000000}
    right = {'event_id': 'R', 'run': 'R7', 'kind': 'anchor',
             'at': f'2026-11-22T00:{seconds // 60:02d}:{seconds % 60:02d}+00:00',
             'odo_mm': odo_right, 'ref': 'A1', 'grade': 3, 'line': 3, 'chain': chain_right,
             'station_mm': 1100000}
    return left, right


def defect(event_id, at, odo, line):
    return {'event_id': event_id, 'run': 'R7', 'kind': 'defect', 'at': at, 'odo_mm': odo,
            'ref': '擦伤', 'grade': 2, 'line': line}


SWAP = {'ticket': 'MT-1', 'run': 'R7', 'at': '2026-11-22T00:01:00+00:00',
        'before_mm': 60000, 'after_mm': 0}


def test_reversal_without_ticket_leaves_gap():
    left, right = marks(50000, 0)
    points = [defect('d', '2026-11-22T00:00:30+00:00', 30000, 9)]
    out = restore(points, [left, right], [])
    assert out['projected'] == []
    assert out['unmapped'][0]['reason'] == 'ODO_REVERSAL'


def test_ticket_splices_both_legs():
    left, right = marks(0, 50000)
    points = [defect('before', '2026-11-22T00:00:30+00:00', 30000, 9),
              defect('after', '2026-11-22T00:01:30+00:00', 25000, 10)]
    out = restore(points, [left, right], [SWAP])
    assert [(p['event_id'], p['station_mm'], p['reset']) for p in out['projected']] == [
        ('before', 1027273, True), ('after', 1077273, True)]
    assert out['projected'][0]['meter_tickets'] == ['MT-1']
    assert out['resets'][0]['decision'] == 'SPLICED'
    assert out['resets'][0]['distance_mm'] == 110000


def test_ticket_required_even_if_endpoints_rise():
    """两只表的读数不能直接比大小：换表后即使右端更大，也要按记录重算。"""
    left, right = marks(100000, 50000)
    out = restore([], [left, right], [SWAP])
    assert out['segments'] == []
    assert out['gaps'][0]['reason'] == 'METER_UNVERIFIED'
    assert out['gaps'][0]['meter_sources'] == [1]


def test_ticket_outside_bracket_cannot_rescue():
    left, right = marks(50000, 0)
    late = dict(SWAP, at='2026-11-22T00:03:00+00:00')
    out = restore([], [left, right], [late])
    assert out['segments'] == [] and out['resets'] == []
    assert out['gaps'][0]['reason'] == 'ODO_REVERSAL'


def test_ticket_readout_mismatch_leaves_gap():
    left, right = marks(0, 50000)
    odd = dict(SWAP, after_mm=70000)
    out = restore([], [left, right], [odd])
    assert out['gaps'][0]['reason'] == 'METER_UNVERIFIED'
    assert out['resets'][0]['decision'] == 'UNVERIFIED'


def test_ticket_reading_below_left_anchor_leaves_gap():
    left, right = marks(0, 50000)
    out = restore([], [left, right], [dict(SWAP, before_mm=60000, after_mm=90000)])
    assert out['gaps'][0]['reason'] == 'METER_UNVERIFIED'


def test_break_and_signal_gap_still_win():
    left, right = marks(0, 50000, chain_right='UP-B')
    out = restore([], [left, right], [SWAP])
    assert out['gaps'][0]['reason'] == 'BREAK'
    assert out['resets'][0]['decision'] == 'NO_RESET'
    left, right = marks(0, 50000, seconds=150)
    out = restore([], [left, right], [SWAP])
    assert out['gaps'][0]['reason'] == 'SIGNAL_GAP'


def test_meter_reset_at_right_anchor():
    left, right = marks(0, 0)
    reset = dict(SWAP, at='2026-11-22T00:02:00+00:00', before_mm=80000, after_mm=0)
    out = restore([], [left, right], [reset])
    assert out['resets'][0]['decision'] == 'SPLICED'
    assert out['resets'][0]['distance_mm'] == 80000


def test_reset_zone_still_rejects_reversal():
    left, right = marks(0, 50000)
    points = [defect('late', '2026-11-22T00:01:30+00:00', 30000, 9),
              defect('back', '2026-11-22T00:01:40+00:00', 10000, 10)]
    out = restore(points, [left, right], [SWAP])
    assert [p['event_id'] for p in out['projected']] == ['late']
    assert next(p['reason'] for p in out['unmapped'] if p['event_id'] == 'back') == 'ODO_REVERSAL'


def test_odometer_outside_active_meter_rejected():
    left, right = marks(0, 50000)
    points = [defect('high', '2026-11-22T00:01:30+00:00', 90000, 9)]
    out = restore(points, [left, right], [SWAP])
    assert out['unmapped'][0]['reason'] == 'METER_UNVERIFIED'


def test_timeline_rejects_bad_tickets():
    for bad in ({'run': 'R7'}, dict(SWAP, at='no-zone'), dict(SWAP, before_mm='x'),
                dict(SWAP, after_mm=-1), dict(SWAP, run='')):
        with pytest.raises(TrackError) as error:
            timeline([bad])
        assert error.value.code == 'BAD_METER'
    with pytest.raises(TrackError):
        timeline({'run': 'R7'})


def test_timeline_normalizes_offsets_and_orders():
    grouped = timeline([dict(SWAP, at='2026-11-22T08:01:00+08:00'),
                        dict(SWAP, at='2026-11-22T00:00:30+00:00', ticket='MT-0')])
    assert [item['ticket'] for item in grouped['R7']] == ['MT-0', 'MT-1']
    assert grouped['R7'][1]['at'] == '2026-11-22T00:01:00+00:00'


def test_normalized_is_order_independent():
    early = dict(SWAP, ticket='MT-0', at='2026-11-22T00:00:30+00:00')
    assert normalized([SWAP, early]) == normalized([early, SWAP])


def test_offset_is_half_open():
    reset = splice(*marks(0, 50000), [timeline([SWAP])['R7'][0]])
    assert offset_of(reset, {'at': '2026-11-22T00:01:00+00:00', 'odo_mm': 0}) == 60000
    assert offset_of(reset, {'at': '2026-11-22T00:02:00+00:00', 'odo_mm': 50000}) is None


def test_meter_sample_publishes_splice():
    result = __import__('app.pipeline', fromlist=['inspect']).inspect(
        sample('meter'), meters=published_meters('meter'))
    assert [(p['event_id'], p['reset']) for p in result['chainage']['projected']] == [
        ('pre', True), ('post', True)]
    assert result['coverage']['spliced_mm'] == 100000


def test_swap_inside_signal_gap_keeps_gap():
    left, right = marks(480000, 0, seconds=300)
    out = restore([], [left, right], [dict(SWAP, before_mm=480000)])
    assert out['gaps'][0]['reason'] == 'SIGNAL_GAP'
    assert out['resets'][0]['label'] == '换表落在断档内'
    assert out['resets'][0]['decision'] == 'NO_RESET'


def test_two_swaps_in_one_span():
    left, right = marks(0, 20000, seconds=110)
    swaps = [dict(SWAP, ticket='MT-1', at='2026-11-22T00:00:40+00:00'),
             dict(SWAP, ticket='MT-2', at='2026-11-22T00:01:20+00:00',
                  before_mm=40000, after_mm=0)]
    out = restore([], [left, right], swaps)
    assert out['resets'][0]['distance_mm'] == 120000
    assert out['resets'][0]['meter_sources'] == [1, 2]


def test_duplicate_swap_instant_rejected():
    with pytest.raises(TrackError):
        timeline([SWAP, dict(SWAP, ticket='MT-2')])


def test_gap_and_break_keep_meter_as_evidence():
    left, right = marks(0, 50000, seconds=200)
    out = restore([], [left, right], [SWAP])
    assert out['gaps'][0]['reason'] == 'SIGNAL_GAP'
    assert out['gaps'][0]['meters'] == ['MT-1'] and out['gaps'][0]['meter_sources'] == [1]
    assert out['resets'][0]['decision'] == 'NO_RESET'
    assert out['resets'][0]['reason'] == 'SIGNAL_GAP'


def test_no_ticket_no_reset_row():
    left, right = marks(50000, 0)
    out = restore([], [left, right], [])
    assert out['resets'] == [] and out['gaps'][0]['meter_sources'] == []
