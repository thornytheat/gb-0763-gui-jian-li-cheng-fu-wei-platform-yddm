from collections import defaultdict
from datetime import datetime
from itertools import pairwise

from app.config import GAP_SECONDS
from app.reasons import evidence
from .meters import splice


def _between(tickets, left, right):
    """换表记录落在两侧基点之间：左开右闭，与断链处左闭右开的分配一致。"""
    return [item for item in tickets if left['at'] < item['at'] <= right['at']]


def delimit(anchors, meters=None):
    """按车次切分基点区间，并对读数下降处用换表记录裁定接续或留缺。"""
    trains = defaultdict(list)
    for mark in anchors:
        trains[mark['run']].append(mark)
    tickets = meters or {}
    spans = defaultdict(list)
    gaps, resets = [], []
    for run, marks in trains.items():
        for left, right in pairwise(marks):
            elapsed = (datetime.fromisoformat(right['at']) - datetime.fromisoformat(left['at'])).total_seconds()
            why = None
            reset = None
            decision = 'CONTINUOUS'
            changes = _between(tickets.get(run, ()), left, right)
            if left['chain'] != right['chain']:
                why, decision = 'BREAK', 'NO_RESET'
            elif elapsed <= 0 or elapsed > GAP_SECONDS:
                why, decision = 'SIGNAL_GAP', 'NO_RESET'
            elif changes:
                # 换表前后是两只表，端点读数不能直接比较，必须按换表记录重算距离。
                reset = splice(left, right, changes)
                if reset is not None:
                    decision = 'SPLICED'
                else:
                    why, decision = 'METER_UNVERIFIED', 'UNVERIFIED'
            elif right['odo_mm'] > left['odo_mm']:
                decision = 'CONTINUOUS'
            else:
                why, decision = 'ODO_REVERSAL', 'REVERSAL'
            meter_rows = [{key: item[key] for key in ('at', 'before_mm', 'after_mm', 'ticket')}
                          for item in changes]
            meter_sources = [item['order'] + 1 for item in changes]
            span = {'left': left, 'right': right, 'reason': why, 'seconds': int(elapsed),
                    'reset': reset, 'decision': decision, 'meters': meter_rows,
                    'meter_sources': meter_sources}
            spans[run].append(span)
            if why:
                gaps.append(dict(evidence(why, left, right), chain=left['chain'],
                                 next_chain=right['chain'], start_mm=left['station_mm'],
                                 end_mm=right['station_mm'],
                                 meters=[item['ticket'] for item in changes],
                                 meter_sources=meter_sources))
            if changes:
                labels = {'SPLICED': '换表接续', 'UNVERIFIED': '读数下降留缺',
                          'REVERSAL': '读数下降留缺', 'NO_RESET': '换表落在断档内'}
                resets.append({'run': run, 'left': left['ref'], 'right': right['ref'],
                               'left_line': left['line'], 'right_line': right['line'],
                               'chain': left['chain'],
                               'from_mm': left['station_mm'], 'to_mm': right['station_mm'],
                               'meters': meter_rows, 'meter_sources': meter_sources,
                               'decision': decision, 'reason': why,
                               'label': labels[decision],
                               'distance_mm': reset['distance_mm'] if reset else None})
    return spans, gaps, resets
