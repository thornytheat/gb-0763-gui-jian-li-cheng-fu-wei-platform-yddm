from app.coverage.balance import balance
from app.coverage.intervals import union


def test_conservation(dirty):
    result = dirty['coverage']
    assert result['planned_mm'] == result['mapped_mm'] + result['missing_mm'] == 600000


def test_duplicate_coverage(dirty):
    assert (dirty['coverage']['mapped_mm'], dirty['coverage']['overlap_mm']) == (400000,100000)


def test_gap_explained(dirty):
    assert dirty['coverage']['missing_parts'] == [dict(chain='UP-B', start_mm=2100000, end_mm=2300000,
                                                      reasons=['SIGNAL_GAP'], sources=[5,6])]


def test_unplanned_chain_does_not_credit(dirty):
    result = balance([dict(chain='NONE',start_mm=1000000,end_mm=1100000)], dirty['chainage']['segments'], [])
    assert (result['mapped_mm'], result['missing_mm']) == (0, 100000)


def test_touching_and_contained():
    assert union([(0,7),(7,10),(1,2),(19,19)]) == [[0,10]]


def test_clean_api(client):
    result = client.get('/api/coverage?sample=clean').json
    assert (result['mapped_mm'], result['missing_parts']) == (600000,[])


def test_spliced_segment_counts_towards_plan(meter):
    data = meter['coverage']
    assert (data['planned_mm'], data['mapped_mm'], data['missing_mm']) == (600000, 200000, 400000)
    assert (data['spliced_mm'], data['spliced_count']) == (100000, 1)


def test_spliced_track_carries_meter_line(meter):
    row = next(item for item in meter['coverage']['tracks'] if item['chain'] == 'UP-A')
    assert [(reset['decision'], reset['meter_sources']) for reset in row['resets']] == [('SPLICED', [1])]


def test_unverified_reset_surfaces_in_gap(meter_client):
    body = meter_client.post('/api/coverage', json={
        'sample': 'meter',
        'meters': [{'ticket': 'MT-X', 'run': 'R7', 'at': '2026-11-22T00:01:00Z',
                    'before_mm': 1000, 'after_mm': 90000}],
    }).json
    gap = next(item for item in body['missing_parts'] if item['chain'] == 'UP-A')
    assert gap['reasons'] == ['METER_UNVERIFIED']
    assert body['meter_gaps'][0]['meters'] == ['MT-X']
    assert body['spliced_count'] == 0


def test_reset_inside_gap_keeps_gap_reason(dirty):
    data = dirty['coverage']
    assert data['missing_parts'] == [dict(chain='UP-B', start_mm=2100000, end_mm=2300000,
                                          reasons=['SIGNAL_GAP'], sources=[5, 6])]
    assert data['meter_gaps'] == [{'chain': 'UP-B', 'start_mm': 2100000, 'end_mm': 2300000,
                                   'meters': ['MT-4471']}]
    reset = next(item for item in data['resets'] if item['run'] == 'R7')
    assert (reset['decision'], reset['resolved_by']) == ('NO_RESET', 'SIGNAL_GAP')


def test_meter_evidence_reaches_archive(client):
    saved = client.post('/api/runs', json={'sample': 'meter'}).json
    assert saved['meters_sha256']
    served = client.get('/api/runs/' + saved['run_id']).json
    assert served['stages']['coverage']['spliced_mm'] == 100000
    assert served['manifest']['summary']['spliced_count'] == 1
    assert served['stages']['chainage']['resets'][0]['meter_sources'] == [1]
