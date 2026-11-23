from collections import defaultdict

from app.config import MERGE_MM


def consolidate(projected):
    """缺陷按链、类别、位置归并；带换表接续的点保留换表依据并在群内单列。"""
    channels = defaultdict(list)
    for point in projected:
        channels[point['chain'], point['ref']].append(point)
    clusters = []
    for (chain, kind), points in sorted(channels.items()):
        for event in sorted(points, key=lambda point: (point['station_mm'], point['event_id'])):
            station = event['station_mm']
            if not clusters or (clusters[-1]['chain'], clusters[-1]['kind']) != (chain, kind) or (
                station - clusters[-1]['start_mm'] > MERGE_MM
            ):
                clusters.append({'chain': chain, 'kind': kind, 'start_mm': station, 'end_mm': station,
                                 'members': [], 'sources': [], 'resets': [], 'meter_sources': [],
                                 'meter_tickets': []})
            cluster = clusters[-1]
            cluster['end_mm'] = station
            cluster['members'].append(event['event_id'])
            cluster['sources'].append(event['line'])
            if event.get('reset'):
                cluster['resets'].append(event['event_id'])
                for line in event['meter_sources']:
                    if line not in cluster['meter_sources']:
                        cluster['meter_sources'].append(line)
                for ticket in event['meter_tickets']:
                    if ticket not in cluster['meter_tickets']:
                        cluster['meter_tickets'].append(ticket)
    return {'observations': len(projected), 'clusters_count': len(clusters), 'clusters': clusters,
            'merged': len(projected) - len(clusters)}
