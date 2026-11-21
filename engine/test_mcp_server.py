"""Smoke test for the MCP server: starts it like an AI app would and calls its tools.

    .venv/bin/python engine/test_mcp_server.py            # uses the fictional example profile only

Read-only except for a throwaway profile it creates and deletes.
"""
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
TMP = 'zz-mcp-test'


class Client:
    def __init__(self):
        self.p = subprocess.Popen([sys.executable, os.path.join(HERE, 'mcp_server.py')], stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, text=True, cwd=REPO)
        self.n = 0

    def call(self, method, params=None):
        self.n += 1
        self.p.stdin.write(json.dumps({'jsonrpc': '2.0', 'id': self.n, 'method': method, 'params': params or {}}) + '\n')
        self.p.stdin.flush()
        while True:
            msg = json.loads(self.p.stdout.readline())
            if msg.get('id') == self.n:
                return msg
            assert msg.get('method') == 'notifications/progress', msg

    def notify(self, method):
        self.p.stdin.write(json.dumps({'jsonrpc': '2.0', 'method': method}) + '\n')
        self.p.stdin.flush()

    def tool(self, tool_name, **args):
        r = self.call('tools/call', {'name': tool_name, 'arguments': args, '_meta': {'progressToken': tool_name}})['result']
        return r, '\n'.join(c['text'] for c in r['content'] if c['type'] == 'text')


def main():
    c = Client()
    fails = []

    def check(label, ok, detail=''):
        print(('PASS ' if ok else 'FAIL ') + label + ('' if ok else f'\n     {detail[:400]}'))
        if not ok:
            fails.append(label)

    r = c.call('initialize', {'protocolVersion': '2025-06-18', 'capabilities': {}, 'clientInfo': {'name': 'test', 'version': '0'}})
    check('initialize', r['result']['serverInfo']['name'] == 'resume-generator' and 'Never invent' in r['result']['instructions'], r)
    c.notify('notifications/initialized')
    check('ping', c.call('ping').get('result') == {})
    tools = {t['name'] for t in c.call('tools/list')['result']['tools']}
    check(f'tools/list ({len(tools)} tools)', {'guide', 'doctor', 'tailor', 'tracker_set', 'save_jobs'} <= tools, tools)
    check('unknown method -> error', c.call('nope')['error']['code'] == -32601)

    r, t = c.tool('guide', name='agents')
    check('guide agents', 'Ground rules' in t or 'ground rules' in t.lower(), t)
    r, t = c.tool('guide', name='nope')
    check('guide unknown lists choices', r['isError'] and 'build-bank' in t, t)
    r, t = c.tool('list_profiles')
    check('list_profiles', 'example' in t, t)
    r, t = c.tool('doctor', profile='example')
    check('doctor runs', 'Checking your setup' in t, t)
    r, t = c.tool('read_file', profile='example', path='')
    check('read_file lists profile', 'bank.json' in t, t)
    r, t = c.tool('read_file', profile='example', path='../../AGENTS.md')
    check('read_file refuses ../', r['isError'] and 'outside' in t, t)
    r, t = c.tool('read_file', profile='../engine', path='scan.py')
    check('bad profile name refused', r['isError'], t)
    r, t = c.tool('check', profile='example', what='bank')
    check('check bank', not r['isError'], t)
    r, t = c.tool('tailor', profile='example', plan='resumes/bosch-general/plan.json', template='docx-basic')
    check('tailor (docx-basic)', not r['isError'] and 'wrote' in t, t)
    check('tailor returns a page image', any(x['type'] == 'image' for x in r['content']), 'no image')
    shutil.rmtree(os.path.join(REPO, 'profiles', 'example', 'resumes', 'bosch-general', 'try-docx-basic'), ignore_errors=True)

    # write path: a throwaway profile
    shutil.rmtree(os.path.join(REPO, 'profiles', TMP), ignore_errors=True)
    try:
        r, t = c.tool('create_profile', name=TMP)
        check('create_profile', not r['isError'], t)
        r, t = c.tool('write_file', profile=TMP, path='notes.json', content='{bad')
        check('write_file rejects bad JSON', r['isError'] and not os.path.exists(os.path.join(REPO, 'profiles', TMP, 'notes.json')), t)
        r, t = c.tool('write_file', profile=TMP, path='notes.txt', content='hello')
        check('write_file', not r['isError'], t)
        r, t = c.tool('write_file', profile=TMP, path='/etc/x', content='x')
        check('write_file refuses absolute path', r['isError'], t)
        r, t = c.tool('check', profile=TMP, what='all')
        check('check flags example data in a new profile', r['isError'] and 'FICTIONAL' in t.upper(), t)
        r, t = c.tool('save_jobs', profile=TMP, source='naukri', jobs=[{'company': 'X'}])
        check('save_jobs validates fields', r['isError'], t)
        r, t = c.tool('tracker_list', profile=TMP)
        check('tracker_list on empty profile', 'No rows' in t or not r['isError'], t)
    finally:
        shutil.rmtree(os.path.join(REPO, 'profiles', TMP), ignore_errors=True)

    c.p.stdin.close()
    c.p.wait(10)
    print(f'\n{len(fails)} failure(s)' if fails else '\nAll passed.')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
