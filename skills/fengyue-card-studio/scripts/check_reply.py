"""Check a single Fengyue reply, not a whole preview page. Status has no size cap."""
import argparse
import json
import re
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

VOID = {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}


class Node:
    def __init__(self, tag='', attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []

    def text(self):
        return ''.join(n.text() if isinstance(n, Node) else n for n in self.children)

    def nodes(self, tag=None, cls=None):
        result = []
        for n in self.children:
            if isinstance(n, Node):
                if (tag is None or n.tag == tag) and (cls is None or cls in n.attrs.get('class','').split()):
                    result.append(n)
                result += n.nodes(tag,cls)
        return result


class Document(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.root, self.errors = Node(), []
        self.stack = [self.root]
        self.feed(source)
        self.close()
        if len(self.stack) != 1:
            self.errors.append('unclosed HTML tags')

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.stack[-1].children.append(Node(tag, attrs))

    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if len(self.stack) == 1 or self.stack[-1].tag != tag:
            self.errors.append('mismatched end tag: ' + tag)
            return
        self.stack.pop()

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def chars(text):
    return len(re.sub(r'\s','',text))


def table_rows(table):
    bodies = table.nodes('tbody')
    return bodies[0].nodes('tr') if len(bodies) == 1 else []


def check(source, active=None, min_story=0, previous=None):
    doc = Document(source)
    errors, warnings = list(doc.errors), []
    root = doc.root
    allnodes = root.nodes()
    if any(n.tag in {'script','style','iframe','object'} or any(k.startswith('on') or k=='style' for k in n.attrs) for n in allnodes):
        errors.append('reply contains executable/inline style content')
    for cls in ('rl-story','rl-status','rl-memory','rl-dossier-list','rl-scene'):
        if len(root.nodes(cls=cls)) != 1:
            errors.append(f'expected exactly one {cls}')
    status = root.nodes(cls='rl-status')
    memory = root.nodes(cls='rl-memory')
    if status and memory and memory[0] not in status[0].nodes(cls='rl-memory'):
        errors.append('memory must be inside the status wrapper')
    dossiers = root.nodes(cls='rl-dossier')
    ids = [n.attrs.get('data-person','') for n in dossiers]
    if not all(ids) or len(ids) != len(set(ids)):
        errors.append('missing or duplicate data-person')
    if active is not None and (set(ids) != set(active) or len(ids) != len(active)):
        errors.append('displayed roster differs from actual active roster')
    for dossier in dossiers:
        keys = [n.attrs['data-field'] for n in dossier.nodes() if 'data-field' in n.attrs]
        if not keys:
            errors.append('dossier needs stable data-field keys')
        if len(keys) != len(set(keys)):
            errors.append('duplicate field in ' + dossier.attrs.get('data-person','?'))
        if dossier.nodes(cls='rl-dossier'):
            errors.append('nested old dossier')
    if any('open' in n.attrs for n in root.nodes('details')):
        warnings.append('details initially open; default is collapsed')
    story = root.nodes(cls='rl-story')
    story_cjk = len(re.findall(r'[\u3400-\u4dbf\u4e00-\u9fff]', story[0].text())) if story else 0
    if story_cjk < min_story:
        errors.append(f'story has {story_cjk} Chinese characters; required {min_story}')
    saved = {'N':None,'B':0,'long':[],'short':[]}
    if len(memory) == 1:
        m = memory[0]
        try:
            N, B = int(m.attrs['data-turn']), int(m.attrs.get('data-base-turn','0'))
            if N < B or B < 0:
                raise ValueError()
            saved.update(N=N,B=B)
        except (ValueError,KeyError):
            errors.append('invalid memory turn/baseline')
            N, B = 0, 0
        for cls, headers, limit, key in [('rl-ltm',['No.','Time','Scene','Event'],400,'long'),('rl-stm',['No.','Time','Scene','Layer','Event'],150,'short')]:
            tables = m.nodes('table',cls)
            if len(tables) != 1:
                errors.append('expected one ' + cls)
                continue
            table = tables[0]
            if [n.text().strip() for n in table.nodes('th')] != headers:
                errors.append('wrong table headers: '+cls)
            rows = table_rows(table)
            empties = [r for r in rows if 'rl-empty' in r.attrs.get('class','').split()]
            real = [r for r in rows if r not in empties]
            if (not real and len(empties)!=1) or (real and empties):
                errors.append('invalid empty-row state: '+cls)
            for row in empties:
                cells = row.nodes('td')
                if len(cells)!=1 or cells[0].attrs.get('colspan')!=str(len(headers)):
                    errors.append('wrong empty colspan: '+cls)
            for row in real:
                cells = row.nodes('td')
                values = [c.text().strip() for c in cells]
                if len(values)!=len(headers):
                    errors.append('wrong cell count: '+cls)
                    continue
                if chars(values[-1]) > limit:
                    errors.append(f'{cls} {values[0]} Event exceeds {limit}')
                if not values[-1]:
                    errors.append('empty Event: '+cls)
                if any(chars(v)>80 for v in values[1:-1]):
                    warnings.append('long non-Event cell; inspect displaced summary')
                saved[key].append({'values':values, 'legacy':row.attrs.get('data-legacy')=='true'})
            numbers = [r['values'][0] for r in saved[key]]
            if len(numbers)!=len(set(numbers)):
                errors.append('duplicate row number: '+cls)
        legacy = sum(r['legacy'] for r in saved['long'])
        M, k = len(saved['long']), len(saved['short'])
        if M-legacy != (N-B)//6 or k != (N-B)%6:
            errors.append('six-turn archive/count mismatch')
        expected = list(range(N-k+1,N+1))
        if [r['values'][0] for r in saved['short']] != [str(x) for x in expected]:
            errors.append('STM sequence mismatch')
        if not legacy and [r['values'][0] for r in saved['long']] != [f'L{i:02d}' for i in range(1,M+1)]:
            errors.append('LTM sequence mismatch')
        summaries = [n for n in m.children if isinstance(n,Node) and n.tag=='summary']
        expected_title = f'记忆区（长期{M}篇｜短期{k}篇）'
        if len(summaries)!=1 or summaries[0].text().strip()!=expected_title:
            errors.append('visible memory count mismatch')
        counter = m.nodes(cls='rl-counter')
        if len(counter)!=1 or f'累计第{N}轮' not in counter[0].text() or f'本组短期{k}/6' not in counter[0].text():
            errors.append('visible turn counter mismatch')
        if previous:
            old = check(previous).get('memory',{})
            if old.get('N') is not None and old.get('B') == B:
                if N not in (old['N'],old['N']+1):
                    errors.append('turn jump; expected same or +1')
                current = {r['values'][0]:r['values'] for r in saved['long']}
                for row in old['long']:
                    no = row['values'][0]
                    if no not in current:
                        errors.append('lost prior LTM '+no)
                    elif current[no] != row['values']:
                        warnings.append('prior LTM changed; confirm explicit correction: '+no)
                if k and N>=old['N']:
                    current_stm = {r['values'][0]:r['values'] for r in saved['short']}
                    for row in old['short']:
                        no=row['values'][0]
                        if no not in current_stm:
                            errors.append('lost unarchived STM '+no)
    status_chars = chars(status[0].text())-chars(memory[0].text()) if status and memory else 0
    return {'passed':not errors,'errors':errors,'warnings':warnings,'story_cjk':story_cjk,'status_chars':status_chars,'status_limit':None,'persons':ids,'memory':saved}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('file'); p.add_argument('--active',nargs='*'); p.add_argument('--min-story',type=int,default=0); p.add_argument('--previous')
    a=p.parse_args()
    source=Path(a.file).read_text(encoding='utf-8-sig')
    previous=Path(a.previous).read_text(encoding='utf-8-sig') if a.previous else None
    result=check(source,a.active,a.min_story,previous)
    print(json.dumps(result,ensure_ascii=False,indent=2))
    raise SystemExit(0 if result['passed'] else 1)
