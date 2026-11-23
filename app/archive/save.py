from datetime import datetime, timezone
import json
import sqlite3
from time import perf_counter

from app.config import GAP_SECONDS, LATE_SECONDS, MERGE_MM, REVISION
from app.errors import TrackError
from app.manifest import canonical, digest
from app.pipeline import inspect
from app.anchors.register import survey_book
from app.chainage.meters import normalized, timeline


def retrieve(archive, run_id):
    with archive.transaction(write=False) as db:
        record = db.execute('SELECT payload FROM runs WHERE id=?', (run_id,)).fetchone()
    if record is None:
        raise TrackError('RUN_MISSING', 404)
    return json.loads(record[0])


def replay(archive, raw, meters=None):
    """复算并归档一趟巡检；同一输入、测绘与换表的组合只落一次。"""
    started = perf_counter()
    survey = survey_book()
    tickets = timeline(meters)
    changes = normalized(meters)
    evidence = inspect(raw, survey=survey, meters=tickets)
    parameters = {'gap_s': GAP_SECONDS, 'late_s': LATE_SECONDS, 'merge_mm': MERGE_MM}
    identity = {'input_sha256': digest(raw), 'survey_sha256': digest(canonical(survey)),
                'meters_sha256': digest(canonical(changes)), 'revision': REVISION,
                'parameters': parameters}
    run_id = digest(canonical(identity))
    summary = {key: evidence['coverage'][key]
               for key in ('planned_mm', 'mapped_mm', 'missing_mm', 'overlap_mm')}
    summary.update(spliced_mm=evidence['coverage']['spliced_mm'],
                   spliced_count=evidence['coverage']['spliced_count'],
                   resets=evidence['coverage']['resets'])
    manifest = dict(identity, run_id=run_id, created_at=datetime.now(timezone.utc).isoformat(),
                    elapsed_ms=round((perf_counter() - started) * 1000), summary=summary,
                    meter_count=len(changes))
    payload = canonical({'manifest': manifest, 'stages': evidence})
    for attempt in range(2):
        try:
            with archive.transaction() as db:
                inserted = db.execute('INSERT OR IGNORE INTO runs VALUES (?, ?)',
                                      (run_id, payload)).rowcount
                previous = db.execute('SELECT payload FROM runs WHERE id=?', (run_id,)).fetchone()[0]
            return dict(json.loads(previous)['manifest'], reused=not bool(inserted))
        except sqlite3.OperationalError:
            # 写锁冲突：事务已整体回滚，重试一次即可从空档继续，不留半份快照。
            if attempt:
                raise
    raise AssertionError('unreachable')


def recent(archive):
    with archive.transaction(write=False) as db:
        rows = db.execute('SELECT payload FROM runs ORDER BY rowid DESC LIMIT 30').fetchall()
    return {'runs': [json.loads(row[0])['manifest'] for row in rows]}
