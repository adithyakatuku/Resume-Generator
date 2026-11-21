"""Read and update the application tracker from the command line (or through the MCP server).

    .venv/bin/python engine/track.py list [--status Applied,Interview]   # rows, newest first
    .venv/bin/python engine/track.py show amazon:10580008                # one job + its description
    .venv/bin/python engine/track.py set amazon:10580008 Interview --note "Recruiter call 2 Dec"

`set` goes through tracker.save, so Last Update / Applied On are stamped and the Summary and
Applied by Date sheets are rebuilt. Statuses: New, Shortlisted, Tailored, Applied, Responded,
Interview, Offer, Rejected, Skipped.
"""
import argparse
import json
import os
import re
import sys
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import candidate  # noqa: E402
import tracker  # noqa: E402


def fmt(v):
    return v.isoformat() if isinstance(v, date) else ('' if v is None else str(v))


def cmd_list(rows, statuses):
    keep = [r for r in rows.values() if not statuses or r.get('Status') in statuses]
    keep.sort(key=lambda r: (fmt(r.get('Last Update')) or fmt(r.get('Posted'))), reverse=True)
    if not keep:
        print('No rows' + (f' with status {", ".join(statuses)}' if statuses else '') + '.')
        return
    print(f'{len(keep)} job(s):')
    for r in keep:
        print(f"{r['Key']:<28} {r.get('Status', ''):<11} {fmt(r.get('Match')):>3}  asks {fmt(r.get('Exp Asked')) or '?':<5}"
              f" posted {fmt(r.get('Posted')) or '?':<10}  {r.get('Company', '')}: {r.get('Role', '')}")


def cmd_show(rows, key):
    r = rows.get(key)
    if not r:
        raise SystemExit(f'{key} is not in the tracker.')
    for col, _ in tracker.COLUMNS:
        if col != 'Age (days)' and fmt(r.get(col)):
            print(f'{col}: {fmt(r.get(col))}')
    cid, jid = key.split(':', 1)
    p = candidate.path('data', 'jobs', cid, re.sub(r'[^\w.-]', '_', jid) + '.json')
    if os.path.exists(p):
        with open(p, encoding='utf-8') as f:
            print('\nDESCRIPTION\n' + json.load(f).get('description', ''))
    else:
        print('\n(no cached description: run a scan)')


def cmd_set(rows, key, status, note):
    r = rows.get(key)
    if not r:
        raise SystemExit(f'{key} is not in the tracker.')
    if status not in tracker.STATUSES:
        raise SystemExit(f'Unknown status "{status}". Use one of: {", ".join(tracker.STATUSES)}')
    old = r.get('Status')
    r['Status'] = status
    if note:
        r['Notes'] = (fmt(r.get('Notes')) + ('; ' if fmt(r.get('Notes')) else '') + note).strip()
    tracker.save(rows)
    r = tracker.load()[key]
    print(f'{key}: {old} -> {status} (Last Update {fmt(r.get("Last Update"))}'
          + (f', Applied On {fmt(r.get("Applied On"))}' if fmt(r.get('Applied On')) else '') + ')')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('list')
    p.add_argument('--status', default='', help='comma-separated statuses to show')
    p = sub.add_parser('show')
    p.add_argument('key')
    p = sub.add_parser('set')
    p.add_argument('key')
    p.add_argument('status')
    p.add_argument('--note', default='')
    a = ap.parse_args()
    rows = tracker.load()
    if a.cmd == 'list':
        cmd_list(rows, [s.strip() for s in a.status.split(',') if s.strip()])
    elif a.cmd == 'show':
        cmd_show(rows, a.key)
    else:
        cmd_set(rows, a.key, a.status, a.note)


if __name__ == '__main__':
    main()
