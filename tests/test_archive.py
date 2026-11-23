from concurrent.futures import ThreadPoolExecutor
import sqlite3

import pytest

from app.archive.save import replay, recent
from app.inputs import sample
from app.main import create_app
from app.manifest import digest


def test_replay(client):
    first = client.post('/api/runs', json={'sample':'dirty'})
    second = client.post('/api/runs', json={'sample':'dirty'})
    assert (first.status_code,second.status_code)==(201,200)
    assert second.json == dict(first.json, reused=True)


def test_restart(client, archive_app):
    result = client.post('/api/runs', json={'sample':'dirty'}).json
    path = '/api/runs/' + result['run_id']
    reopened = create_app(archive_app.track_archive.file).test_client()
    assert reopened.get(path).json == client.get(path).json


def test_input_fingerprint(client):
    result = client.post('/api/runs', json={'sample':'clean'}).json
    assert result['input_sha256'] == digest(sample('clean'))
    assert result['summary']['mapped_mm'] == 600000


def test_parse_failure_writes_nothing(client):
    assert client.post('/api/runs', json={'csv':'wrong'}).json['error'] == 'BAD_HEADER'
    assert client.get('/api/runs').json == {'runs':[]}


def test_many_workers_one_commit(archive_app):
    archive = archive_app.track_archive
    with ThreadPoolExecutor(6) as pool:
        results = list(pool.map(lambda _:replay(archive, sample('dirty')), range(8)))
    assert sum(not result['reused'] for result in results)==1
    assert len(recent(archive)['runs']) == 1


def test_failed_write_rolls_back(archive_app):
    archive = archive_app.track_archive
    with archive.transaction() as db:
        db.execute("CREATE TRIGGER fail_run BEFORE INSERT ON runs BEGIN SELECT RAISE(ABORT, 'fault'); END")
    with pytest.raises(sqlite3.IntegrityError):
        replay(archive, sample('dirty'))
    assert recent(archive) == {'runs':[]}


def test_meter_tickets_saved_with_run(client):
    saved = client.post('/api/runs', json={'sample': 'meter'}).json
    assert saved['meter_count'] == 1
    assert [item['label'] for item in saved['summary']['resets']] == ['换表接续']


def test_different_meters_make_different_run(client):
    first = client.post('/api/runs', json={'sample': 'meter'}).json
    second = client.post('/api/runs', json={'sample': 'meter', 'meters': []}).json
    assert first['run_id'] != second['run_id']
    assert second['summary']['spliced_count'] == 0
    assert second['summary']['spliced_mm'] == 0 < first['summary']['spliced_mm']
    assert second['summary']['resets'] == []
    assert first['meter_count'] == 1 and second['meter_count'] == 0


def test_invalid_meter_body_rejected(client):
    response = client.post('/api/runs', json={'sample': 'meter', 'meters': [{'run': 'R7'}]})
    assert (response.status_code, response.json['error']) == (422, 'BAD_METER')
    assert client.get('/api/runs').json == {'runs': []}


def test_retry_after_failed_write(client, archive_app):
    archive = archive_app.track_archive
    with archive.transaction() as db:
        db.execute("CREATE TRIGGER fail_run BEFORE INSERT ON runs BEGIN SELECT RAISE(ABORT, 'fault'); END")
    with pytest.raises(sqlite3.IntegrityError):
        replay(archive, sample('meter'))
    assert recent(archive) == {'runs': []}
    with archive.transaction() as db:
        db.execute('DROP TRIGGER fail_run')
    result = client.post('/api/runs', json={'sample': 'meter'}).json
    assert client.post('/api/runs', json={'sample': 'meter'}).json == dict(result, reused=True)
    assert len(recent(archive)['runs']) == 1
