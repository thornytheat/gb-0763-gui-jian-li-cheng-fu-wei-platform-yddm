import json

from flask import Blueprint, current_app, render_template, request

from app.archive.save import recent
from app.config import REVISION
from app.errors import TrackError
from app.inputs import published_meters, sample
from app.pipeline import inspect

pages = Blueprint('track_web', __name__)
SECTIONS = {'coverage': '轨段覆盖对账', 'capture': '轨检报文采信', 'anchors': '基点匹配',
            'chainage': '区间坐标复位', 'defects': '缺陷投影合并', 'runs': '批次留档复跑',
            'issue': '巡检证据签发'}
LABELS = {'dirty': '夜巡原始报文', 'clean': '标定对照报文', 'meter': '换表样例报文'}


@pages.get('/')
@pages.get('/work/<section>')
def screen(section='coverage'):
    if section not in SECTIONS:
        raise TrackError('NO_SAMPLE', 404)
    label = request.args.get('sample', 'dirty')
    raw, tickets = sample(label), published_meters(label)
    results = inspect(raw, section if section not in ('runs', 'issue') else 'coverage', meters=tickets)
    ledger = recent(current_app.track_archive)['runs'] if section in ('runs', 'issue') else []
    return render_template('base.html', section=section, nav=SECTIONS, label=label, labels=LABELS,
                           stages=results, ledger=ledger, rev=REVISION,
                           run_id=request.args.get('run', ''),
                           meters_text=json.dumps(tickets or [], ensure_ascii=False, indent=2)
                           if tickets else '')
