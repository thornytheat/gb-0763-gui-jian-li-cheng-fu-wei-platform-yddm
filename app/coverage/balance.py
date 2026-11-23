from collections import defaultdict

from .intervals import clip, complement, union


def _range(span):
    a, b = span['left']['station_mm'], span['right']['station_mm']
    return (a, b) if a <= b else (b, a)


def _gap_cover(chain, lo, hi, gaps):
    """找出与缺口 [lo, hi) 相交的断档，保留原因、行号和换表依据。"""
    reasons, sources, tickets = [], [], []
    for gap in gaps:
        if gap['chain'] != chain:
            continue
        gstart, gend = sorted((gap['start_mm'], gap['end_mm']))
        if min(hi, gend) <= max(lo, gstart):
            continue
        if gap['reason'] not in reasons:
            reasons.append(gap['reason'])
        for line in gap['sources']:
            if line not in sources:
                sources.append(line)
        for ticket in gap.get('meters', ()):
            if ticket and ticket not in tickets:
                tickets.append(ticket)
    return reasons or ['NO_COVERAGE'], sources, tickets


def _reset_row(item):
    row = {'run': item['run'], 'left': item['left'], 'right': item['right'],
           'meters': item['meters'], 'meter_sources': item['meter_sources'],
           'decision': item['decision'], 'label': item['label'],
           'start_mm': min(item['from_mm'], item['to_mm']), 'end_mm': max(item['from_mm'], item['to_mm']),
           'distance_mm': item['distance_mm'],
           'lines': [item['left_line'], item['right_line'], *item['meter_sources']]}
    if item['reason']:
        row['resolved_by'] = item['reason']
    return row


def _reset_refs(chain, lo, hi, resets):
    rows = []
    for reset in resets or ():
        if reset['chain'] != chain:
            continue
        start, end = min(reset['from_mm'], reset['to_mm']), max(reset['from_mm'], reset['to_mm'])
        if end <= lo or start >= hi:
            continue
        rows.append(_reset_row(reset))
    return rows


def balance(plan, segments, gaps, resets=None):
    """覆盖按链取计划与有效区间的交；换表接续照常计入，换表留缺单列依据。"""
    covered = defaultdict(list)
    for span in segments:
        lo, hi = _range(span)
        if hi > lo:
            covered[span['left']['chain']].append((lo, hi))

    tracks, missing_parts, meter_gaps = [], [], []
    planned_mm = mapped_mm = overlap_mm = 0
    for item in plan:
        chain, start, end = item['chain'], item['start_mm'], item['end_mm']
        if end <= start:
            continue
        planned = end - start
        raw = clip(covered[chain], start, end)
        merged = union(raw)
        mapped = sum(hi - lo for lo, hi in merged)
        planned_mm += planned
        mapped_mm += mapped
        overlap_mm += sum(hi - lo for lo, hi in raw) - mapped
        tracks.append({'chain': chain, 'start_mm': start, 'end_mm': end, 'planned_mm': planned,
                       'mapped_mm': mapped, 'mapped_parts': merged,
                       'resets': _reset_refs(chain, start, end, resets)})
        for lo, hi in complement(merged, start, end):
            reasons, sources, tickets = _gap_cover(chain, lo, hi, gaps)
            missing_parts.append({'chain': chain, 'start_mm': lo, 'end_mm': hi,
                                  'reasons': reasons, 'sources': sources})
            if tickets:
                meter_gaps.append({'chain': chain, 'start_mm': lo, 'end_mm': hi, 'meters': tickets})

    plans = defaultdict(list)
    for item in plan:
        if item['end_mm'] > item['start_mm']:
            plans[item['chain']].append((item['start_mm'], item['end_mm']))
    spliced = [reset for reset in resets or () if reset['decision'] == 'SPLICED']
    spliced_mm = 0
    for reset in spliced:
        window = (min(reset['from_mm'], reset['to_mm']), max(reset['from_mm'], reset['to_mm']))
        spliced_mm += sum(hi - lo for lo, hi in clip(union(plans[reset['chain']]), *window))
    return {'planned_mm': planned_mm, 'mapped_mm': mapped_mm, 'missing_mm': planned_mm - mapped_mm,
            'overlap_mm': overlap_mm, 'missing_parts': missing_parts, 'meter_gaps': meter_gaps,
            'tracks': tracks, 'resets': [_reset_row(reset) for reset in resets or ()],
            'spliced_mm': spliced_mm, 'spliced_count': len(spliced)}
