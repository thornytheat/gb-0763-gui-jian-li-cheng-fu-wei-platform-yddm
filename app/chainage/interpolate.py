from bisect import bisect_right
from decimal import Decimal, ROUND_HALF_UP

from app.reasons import evidence
from .meters import offset_of, timeline
from .segments import delimit


def _station(a, b, measure, total):
    delta = Decimal(measure * (b['station_mm'] - a['station_mm']))
    return int((a['station_mm'] + delta / total).quantize(Decimal('1'), rounding=ROUND_HALF_UP))


def restore(events, anchors, meters=None):
    tickets = meters if isinstance(meters, dict) else timeline(meters)
    spans, gaps, resets = delimit(anchors, tickets)
    boundaries = {run: [span['left']['at'] for span in items] for run, items in spans.items()}
    progress, projected, missing = {}, [], []
    for event in events:
        if event['kind'] != 'defect':
            continue
        run, odo = event['run'], event['odo_mm']
        index = bisect_right(boundaries.get(run, ()), event['at']) - 1
        span = spans[run][index] if index >= 0 else None
        why, sources = 'NO_BRACKET', [event]
        if span and event['at'] < span['right']['at']:
            a, b = span['left'], span['right']
            sources.extend((a, b))
            why = span['reason']
            if not why and span['reset'] is not None:
                offset = offset_of(span['reset'], event)
                if offset is None:
                    why = 'METER_UNVERIFIED'
                elif offset < progress.get((run, index), 0):
                    why = 'ODO_REVERSAL'
                else:
                    progress[run, index] = offset
                    projected.append(dict(
                        event, station_mm=_station(a, b, offset, span['reset']['distance_mm']),
                        chain=a['chain'], marks=[a['ref'], b['ref']], anchor_lines=[a['line'], b['line']],
                        reset=True, meter_sources=span['meter_sources'],
                        meter_tickets=[item['ticket'] for item in span['reset']['changes']]))
                    continue
            if not why:
                if not a['odo_mm'] <= odo < b['odo_mm']:
                    why = 'OUTSIDE_ODO'
                elif odo < progress.get((run, index), odo):
                    why = 'ODO_REVERSAL'
                else:
                    progress[run, index] = odo
                    projected.append(dict(
                        event, station_mm=_station(a, b, odo - a['odo_mm'], b['odo_mm'] - a['odo_mm']),
                        chain=a['chain'], marks=[a['ref'], b['ref']], anchor_lines=[a['line'], b['line']],
                        reset=False, meter_sources=[], meter_tickets=[]))
                    continue
        missing.append(dict(evidence(why, *sources), event_id=event['event_id'],
                            reset=bool(span and span['meters']),
                            meter_sources=span['meter_sources'] if span else [],
                            meter_tickets=[item['ticket'] for item in span['meters']] if span else [],
                            raw=event))
    usable = [span for group in spans.values() for span in group if not span['reason']]
    return {'projected_count': len(projected), 'unmapped_count': len(missing), 'projected': projected,
            'unmapped': missing, 'segments': usable, 'gaps': gaps, 'resets': resets}
