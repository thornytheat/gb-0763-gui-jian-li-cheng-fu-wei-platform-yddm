def test_evidence_screens(client):
    for path, marker in [('/', '掉线缺口'),('/work/chainage','双基点复位'),('/work/anchors','基点取舍'),
                         ('/work/capture','隔离报文'),('/work/defects','归并检点'),('/work/runs','归档报文')]:
        assert marker in client.get(path).get_data(as_text=True)


def test_meter_screens_show_reset_basis(client):
    for path, marker in [('/work/coverage', '换表接续'), ('/work/chainage', '换表对账'),
                         ('/work/defects', '换表依据'), ('/work/runs', '换表记录 JSON')]:
        page = client.get(path + '?sample=meter').get_data(as_text=True)
        assert marker in page


def test_runs_page_lists_reset_evidence(client):
    assert '等待首次归档' in client.get('/work/runs?sample=meter').get_data(as_text=True)
    saved = client.post('/api/runs', json={'sample': 'meter'}).json
    page = client.get('/work/runs?sample=meter').get_data(as_text=True)
    assert saved['run_id'][:16] in page
    assert 'MT-4502' in page and '换表接续' in page
    assert 'A0 → A1' in page


def test_gap_sample_lists_meter_basis(client):
    page = client.get('/work/coverage?sample=dirty').get_data(as_text=True)
    assert 'MT-4471' in page and 'SIGNAL_GAP' in page
