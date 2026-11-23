from app.defects.cluster import consolidate


def test_real_members(dirty):
    assert dirty['defects']['clusters'][1]['members'] == ['p1','p2','rp']


def test_member_sources(dirty):
    assert dirty['defects']['clusters'][1]['sources'] == [8,9,22]


def test_no_transitive_spread(dirty):
    p = dirty['chainage']['projected'][0]
    points = [dict(p, station_mm=n, event_id=str(n)) for n in (0,5000,5001)]
    assert [r['members'] for r in consolidate(points)['clusters']] == [['0','5000'],['5001']]


def test_other_branch_not_merged(dirty):
    p = dirty['chainage']['projected'][0]
    assert consolidate([p, dict(p, chain='ANOTHER')])['clusters_count'] == 2


def test_other_defect_type_not_merged(dirty):
    p = dirty['chainage']['projected'][0]
    assert consolidate([p, dict(p, ref='崩边')])['merged'] == 0


def test_empty_cluster():
    assert consolidate([]) == {'observations':0,'clusters_count':0,'clusters':[],'merged':0}


def test_reset_members_keep_meter_evidence(meter):
    clusters = [row for row in meter['defects']['clusters']
                if row['chain'] == 'UP-A' and row['kind'] == '擦伤']
    assert [row['members'] for row in clusters] == [['pre'], ['post']]
    assert [row['resets'] for row in clusters] == [['pre'], ['post']]
    assert {tuple(row['meter_tickets']) for row in clusters} == {('MT-4502',)}
    assert {tuple(row['meter_sources']) for row in clusters} == {(1,)}


def test_plain_cluster_has_no_meter_evidence(dirty):
    cluster = next(row for row in dirty['defects']['clusters'] if row['members'] == ['p4'])
    assert (cluster['resets'], cluster['meter_tickets'], cluster['meter_sources']) == ([], [], [])
