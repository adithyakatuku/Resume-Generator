"""The application tracker: <profile>/applications.xlsx.

Sheets:
  Summary          read-only. Funnel, per-company and per-week counts are live
                   formulas, so they follow your edits as soon as you make them.
                   The "waiting for a reply" list refreshes on each scan / --refresh.
  Applications     the one sheet you edit. One row per job.
  Applied by Date  read-only. Your applications grouped by the day you applied,
                   rebuilt from Applications on each scan / --refresh.
  _state           hidden. The statuses seen at the last save, used to stamp
                   "Last Update" when you change a status.

You own Match, Status, Resume, Applied On, Last Update and Notes on the
Applications sheet; every other column is refreshed from the job boards. The
workbook is regenerated on every save, so extra columns or formatting added
by hand do not survive. Put free text in Notes.

On each save:
  * a status you changed since the last save gets Last Update = today (unless
    you also edited Last Update yourself)
  * a row at Applied or beyond with no Applied On gets Applied On = today
  * Closed rows are removed (they reappear as New if the job becomes eligible again)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from datetime import date, datetime, timedelta

from openpyxl import Workbook, load_workbook
from openpyxl.formatting.rule import FormulaRule
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

import candidate  # noqa: E402  (engine/candidate.py: the active profile folder)


def xlsx_path():
    return candidate.path('applications.xlsx')

# (header, width)
COLUMNS = [
    ('Key', 20), ('Company', 18), ('Role', 46), ('Location', 26), ('Exp Asked', 10),
    ('Posted', 11), ('Age (days)', 10), ('First Seen', 11), ('Last Seen', 11), ('Match', 8), ('Gaps', 30),
    ('Status', 12), ('Resume', 24), ('Applied On', 11), ('Last Update', 11), ('Notes', 40), ('URL', 50),
]
HEADS = [h for h, _ in COLUMNS]
COL = {h: get_column_letter(i + 1) for i, h in enumerate(HEADS)}
DATE_FIELDS = ['Posted', 'First Seen', 'Last Seen', 'Applied On', 'Last Update']
# kept across scans: yours to edit, plus Match/Gaps which match.py fills once per job
USER_FIELDS = ['Match', 'Gaps', 'Status', 'Resume', 'Applied On', 'Last Update', 'Notes']

STATUSES = ['New', 'Shortlisted', 'Tailored', 'Applied', 'Responded', 'Interview', 'Offer',
            'Rejected', 'Skipped', 'Closed']
OPEN = ['New', 'Shortlisted', 'Tailored']                        # found, not applied yet
APPLIED = ['Applied', 'Responded', 'Interview', 'Offer', 'Rejected']
REPLIED = ['Responded', 'Interview', 'Offer', 'Rejected']        # any reply, rejections included
POSITIVE = ['Responded', 'Interview', 'Offer']
INTERVIEWED = ['Interview', 'Offer']
WAIT_DAYS = 21
MAX_ROW = 5000

STATUS_ORDER = {s: i for i, s in enumerate(['Offer', 'Interview', 'Responded', 'Applied', 'Tailored',
                                             'Shortlisted', 'New', 'Rejected', 'Skipped', 'Closed'])}
STATUS_COLORS = {'New': 'DDEBF7', 'Shortlisted': 'FFF2CC', 'Tailored': 'FCE4D6', 'Applied': 'E2EFDA',
                 'Responded': 'D9E1F2', 'Interview': 'C6EFCE', 'Offer': 'A9D08E',
                 'Rejected': 'EDEDED', 'Skipped': 'EDEDED', 'Closed': 'EDEDED'}

HEAD_FONT, HEAD_FILL = Font(bold=True, color='FFFFFF'), PatternFill('solid', fgColor='305496')
TITLE_FONT, SECTION_FONT = Font(bold=True, size=16), Font(bold=True, size=12, color='305496')
NOTE_FONT, LINK_FONT = Font(italic=True, color='7F7F7F'), Font(color='0563C1', underline='single')
GROUP_FILL = PatternFill('solid', fgColor='D9E1F2')
DATE_FMT = 'yyyy-mm-dd'


def to_date(v):
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, str) and v.strip():
        try:
            return datetime.strptime(v.strip()[:10], '%Y-%m-%d').date()
        except ValueError:
            return ''
    return ''


def _rng(field):
    return f"Applications!${COL[field]}$2:${COL[field]}${MAX_ROW}"


def _in(statuses):
    return '{' + ','.join(f'"{s}"' for s in statuses) + '}'


# ---------------------------------------------------------------- load / merge
def load():
    """Return {key: row-dict}. Each row carries _prev_status/_prev_update from
    the last save so status changes can be dated."""
    if not os.path.exists(xlsx_path()):
        return {}
    wb = load_workbook(xlsx_path())
    ws = wb['Applications'] if 'Applications' in wb.sheetnames else wb.active
    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return {}
    head = [str(h) if h is not None else '' for h in rows[0]]
    out = {}
    for r in rows[1:]:
        rec = {h: ('' if v is None else v) for h, v in zip(head, r)}
        if not rec.get('Key'):
            continue
        for f in DATE_FIELDS:
            rec[f] = to_date(rec.get(f))
        out[rec['Key']] = rec
    if '_state' in wb.sheetnames:
        for key, status, upd in wb['_state'].iter_rows(min_row=2, values_only=True):
            if key in out:
                out[key]['_prev_status'] = status or ''
                out[key]['_prev_update'] = to_date(upd)
    return out


def merge(existing, found, scanned_companies, today):
    """Fold this scan's eligible jobs into the tracker rows.

    found: {key: row-dict with scanner columns}. Jobs from a scanned company
    that are no longer found flip New -> Closed; anything you already acted on
    is left alone.
    """
    today = to_date(today)
    rows = dict(existing)
    new_keys = []
    for k, rec in found.items():
        rec = dict(rec, Posted=to_date(rec.get('Posted')))
        if k in rows:
            keep = {f: rows[k].get(f, '') for f in USER_FIELDS + ['_prev_status', '_prev_update']}
            first = rows[k].get('First Seen') or today
            rows[k] = dict(rec, **keep, **{'First Seen': first, 'Last Seen': today})
            if rows[k].get('Status') == 'Closed':  # relisted
                rows[k]['Status'] = 'New'
        else:
            rows[k] = dict(rec, **{'First Seen': today, 'Last Seen': today, 'Status': 'New'})
            new_keys.append(k)
    closed = []
    for k, rec in rows.items():
        if rec.get('Company') in scanned_companies and k not in found and rec.get('Status') == 'New':
            rec['Status'] = 'Closed'
            closed.append(k)
    return rows, new_keys, closed


def reconcile(rows, today):
    """Date status changes made by hand since the last save."""
    for r in rows.values():
        st = r.get('Status') or ''
        prev = r.get('_prev_status')
        if prev is not None and st != prev and r.get('Last Update') == r.get('_prev_update'):
            # a freshly marked application dates from its Applied On (you may backdate it)
            r['Last Update'] = (r.get('Applied On') or today) if st == 'Applied' else today
        if st in APPLIED and not r.get('Applied On'):
            r['Applied On'] = today
        if st in APPLIED and not r.get('Last Update'):
            r['Last Update'] = r['Applied On']


# ---------------------------------------------------------------- sheets
def _header(ws, row, labels, widths=None):
    for i, h in enumerate(labels, start=1):
        c = ws.cell(row=row, column=i, value=h)
        c.font, c.fill = HEAD_FONT, HEAD_FILL
        if widths:
            ws.column_dimensions[get_column_letter(i)].width = widths[i - 1]


def _applications(ws, rows):
    _header(ws, 1, HEADS, [w for _, w in COLUMNS])
    ordered = sorted(rows, key=lambda r: r.get('Posted') or date.min, reverse=True)
    ordered.sort(key=lambda r: STATUS_ORDER.get(r.get('Status'), 99))
    p = COL['Posted']
    for i, r in enumerate(ordered, start=2):
        for j, h in enumerate(HEADS, start=1):
            c = ws.cell(row=i, column=j)
            if h == 'Age (days)':
                c.value, c.number_format = f'=IF({p}{i}="","",TODAY()-{p}{i})', '0'
            else:
                c.value = r.get(h, '')
                if h in DATE_FIELDS:
                    c.number_format = DATE_FMT
            if h == 'URL' and c.value:
                c.hyperlink, c.font = c.value, LINK_FONT
            if h in ('Role', 'Notes', 'Gaps'):
                c.alignment = Alignment(wrap_text=True, vertical='top')
    last = get_column_letter(len(HEADS))
    ws.freeze_panes = 'C2'
    ws.auto_filter.ref = f'A1:{last}{max(ws.max_row, 2)}'
    s = COL['Status']
    dv = DataValidation(type='list', formula1='"' + ','.join(STATUSES) + '"', allow_blank=True)
    dv.add(f'{s}2:{s}{MAX_ROW}')
    ws.add_data_validation(dv)
    for st, color in STATUS_COLORS.items():
        ws.conditional_formatting.add(f'A2:{last}{MAX_ROW}', FormulaRule(
            formula=[f'${s}2="{st}"'], fill=PatternFill('solid', fgColor=color)))


def _summary(ws, rows, today):
    S, C, AO = _rng('Status'), _rng('Company'), _rng('Applied On')
    FS, LU = _rng('First Seen'), _rng('Last Update')
    for col, w in zip('ABCDEFGHI', (34, 11, 11, 11, 11, 11, 11, 11, 11)):
        ws.column_dimensions[col].width = w
    ws['A1'], ws['A1'].font = 'Job Search Summary', TITLE_FONT
    ws['A2'] = (f'Last rebuilt {today:%d %b %Y}. Counts are live formulas over the Applications sheet; '
                f'the waiting list below refreshes when you run scan.py (or scan.py --refresh).')
    ws['A2'].font = NOTE_FONT

    # funnel
    ws['A4'], ws['A4'].font = 'Funnel', SECTION_FONT
    _header(ws, 5, ['Stage', 'Jobs', '% of applied'])
    funnel = [
        ('Jobs found (all tracked)', f'=COUNTA(Applications!$A$2:$A${MAX_ROW})', False),
        ('Not applied yet (New / Shortlisted / Tailored)', f'=SUMPRODUCT(COUNTIF({S},{_in(OPEN)}))', False),
        ('Applied', f'=SUMPRODUCT(COUNTIF({S},{_in(APPLIED)}))', 'base'),
        ('Got any reply (incl. rejections)', f'=SUMPRODUCT(COUNTIF({S},{_in(REPLIED)}))', True),
        ('Positive reply (Responded / Interview / Offer)', f'=SUMPRODUCT(COUNTIF({S},{_in(POSITIVE)}))', True),
        ('Reached interview', f'=SUMPRODUCT(COUNTIF({S},{_in(INTERVIEWED)}))', True),
        ('Offers', f'=COUNTIF({S},"Offer")', True),
        ('Rejected', f'=COUNTIF({S},"Rejected")', True),
        ('Awaiting reply', f'=COUNTIF({S},"Applied")', True),
        (f'  of which waiting > {WAIT_DAYS} days', f'=COUNTIFS({S},"Applied",{AO},"<"&TODAY()-{WAIT_DAYS})', True),
    ]
    base = None
    for i, (label, formula, rate) in enumerate(funnel, start=6):
        ws.cell(row=i, column=1, value=label)
        ws.cell(row=i, column=2, value=formula)
        if rate == 'base':
            base = f'$B${i}'
        elif rate:
            c = ws.cell(row=i, column=3, value=f'=IF({base}=0,"",B{i}/{base})')
            c.number_format = '0%'
    r = 6 + len(funnel) + 1

    # by company
    ws.cell(row=r, column=1, value='By company').font = SECTION_FONT
    _header(ws, r + 1, ['Company', 'Found', 'Not applied', 'Applied', 'Replies', 'Interviews', 'Offers',
                        'Rejected', 'Reply rate'])
    companies = sorted({x.get('Company') for x in rows if x.get('Company')})
    for i, name in enumerate(companies, start=r + 2):
        a = f'$A{i}'
        ws.cell(row=i, column=1, value=name)
        ws.cell(row=i, column=2, value=f'=COUNTIF({C},{a})')
        for col, group in ((3, OPEN), (4, APPLIED), (5, REPLIED), (6, INTERVIEWED), (7, ['Offer']), (8, ['Rejected'])):
            ws.cell(row=i, column=col, value=f'=SUMPRODUCT(COUNTIFS({C},{a},{S},{_in(group)}))')
        ws.cell(row=i, column=9, value=f'=IF(D{i}=0,"",E{i}/D{i})').number_format = '0%'
    r = r + 2 + len(companies) + 1

    # by week (Monday-start), live
    ws.cell(row=r, column=1, value='By week (last 8 weeks)').font = SECTION_FONT
    _header(ws, r + 1, ['Week of (Mon)', 'Jobs found', 'Applied', 'Replies logged'])
    for k in range(8):
        i = r + 2 + k
        ws.cell(row=i, column=1, value=f'=TODAY()-WEEKDAY(TODAY(),3)-{7 * k}').number_format = 'ddd dd mmm yyyy'
        rng = lambda R: f'{R},">="&$A{i},{R},"<"&$A{i}+7'  # noqa: E731
        ws.cell(row=i, column=2, value=f'=COUNTIFS({rng(FS)})')
        ws.cell(row=i, column=3, value=f'=COUNTIFS({rng(AO)})')
        ws.cell(row=i, column=4, value=f'=SUMPRODUCT(COUNTIFS({rng(LU)},{S},{_in(REPLIED)}))')
    r = r + 2 + 8 + 1

    # waiting list (snapshot)
    ws.cell(row=r, column=1, value=f'Waiting more than {WAIT_DAYS} days for a reply').font = SECTION_FONT
    ws.cell(row=r + 1, column=1, value='Snapshot as of the last rebuild. Follow up, or mark Rejected if you have given up.').font = NOTE_FONT
    _header(ws, r + 2, ['Role', 'Company', 'Applied On', 'Days', 'URL'])
    cutoff = today - timedelta(days=WAIT_DAYS)
    waiting = sorted((x for x in rows if x.get('Status') == 'Applied' and x.get('Applied On')
                      and x['Applied On'] < cutoff), key=lambda x: x['Applied On'])
    if not waiting:
        ws.cell(row=r + 3, column=1, value='Nothing yet.').font = NOTE_FONT
    for i, x in enumerate(waiting, start=r + 3):
        ws.cell(row=i, column=1, value=x.get('Role'))
        ws.cell(row=i, column=2, value=x.get('Company'))
        ws.cell(row=i, column=3, value=x['Applied On']).number_format = DATE_FMT
        ws.cell(row=i, column=4, value=(today - x['Applied On']).days)
        c = ws.cell(row=i, column=5, value=x.get('URL'))
        if c.value:
            c.hyperlink, c.font = c.value, LINK_FONT
    ws.protection.sheet = True


def _by_date(ws, rows):
    labels = ['Company', 'Role', 'Status', 'Last Update', 'Exp Asked', 'Match', 'URL']
    ws['A1'] = 'Read-only view rebuilt from Applications on each scan. Change statuses on the Applications sheet.'
    ws['A1'].font = NOTE_FONT
    _header(ws, 2, labels, [20, 50, 12, 12, 10, 8, 50])
    ws.freeze_panes = 'A3'
    applied = [x for x in rows if x.get('Applied On')]
    days = sorted({x['Applied On'] for x in applied}, reverse=True)
    r = 3
    if not days:
        ws.cell(row=r, column=1, value='No applications yet.').font = NOTE_FONT
    for d in days:
        group = sorted((x for x in applied if x['Applied On'] == d), key=lambda x: (x.get('Company'), x.get('Role')))
        n = len(group)
        ws.cell(row=r, column=1, value=f'{d:%a %d %b %Y}  ·  {n} application{"s" if n != 1 else ""}').font = Font(bold=True)
        for col in range(1, len(labels) + 1):
            ws.cell(row=r, column=col).fill = GROUP_FILL
        r += 1
        for x in group:
            for col, h in enumerate(labels, start=1):
                c = ws.cell(row=r, column=col, value=x.get(h, ''))
                if h == 'Last Update':
                    c.number_format = DATE_FMT
                if h == 'URL' and c.value:
                    c.hyperlink, c.font = c.value, LINK_FONT
                if h == 'Status' and x.get('Status') in STATUS_COLORS:
                    c.fill = PatternFill('solid', fgColor=STATUS_COLORS[x['Status']])
            r += 1
        r += 1
    ws.protection.sheet = True


def save(rows):
    today = date.today()
    reconcile(rows, today)
    # Closed = the posting is gone or no longer passes the rules: drop it to keep the sheet
    # to jobs that matter. A job that becomes eligible again comes back as New on the next scan.
    # Skipped rows stay: they are how a live posting is kept from being suggested again.
    for k in [k for k, r in rows.items() if r.get('Status') == 'Closed']:
        del rows[k]
    data = list(rows.values())
    wb = Workbook()
    summary = wb.active
    summary.title = 'Summary'
    _applications(wb.create_sheet('Applications'), data)
    _by_date(wb.create_sheet('Applied by Date'), data)
    _summary(summary, data, today)
    st = wb.create_sheet('_state')
    st.append(['Key', 'Status', 'Last Update'])
    for x in data:
        st.append([x.get('Key'), x.get('Status', ''), x.get('Last Update') or None])
    st.sheet_state = 'hidden'
    try:
        wb.save(xlsx_path())
    except PermissionError:
        raise SystemExit(f'Could not write {xlsx_path()}: close it in Excel and re-run.')
