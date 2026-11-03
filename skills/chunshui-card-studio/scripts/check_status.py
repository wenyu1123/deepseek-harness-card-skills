#!/usr/bin/env python3
"""Offline check of a single reply's ordinary status budget (excludes LTM/STM)."""
import argparse
import json
import re
from pathlib import Path
from check_memory import Document, Node, compact

LIMITS = {'world': 120, 'self': 180, 'people': 300, 'threads': 150, 'actions': 90}
TOTAL_LIMIT = 900
RAW_LIMIT = 6000


def inspect_status(source):
    document = Document(source).root
    errors, metrics = [], {}
    blocks = document.find('section', 'cs-status')
    if len(blocks) != 1:
        return {'ok': False, 'errors': ['一条剧情样例必须只有一份section.cs-status，不能叠加旧快照。'], 'metrics': {'status_blocks':len(blocks)}}
    block = blocks[0]
    if block.find('section'):
        errors.append('普通状态区不得嵌套旧section或另一组快照。')
    if block.find(cls='cs-memory-table'):
        errors.append('LTM/STM必须在普通状态区之外；不能混算预算。')
    for old in ('cs-state', 'cs-actions', 'cs-memory'):
        if document.find(cls=old):
            errors.append(f'发现旧组件{old}，请合并，避免另出重复状态或行动组。')
    descendants = block.find()
    if any(x.tag in {'script','style','svg','img','iframe'} for x in descendants):
        errors.append('普通状态不应携带脚本、重复样式、大型图像或SVG。')
    if any('style' in x.attrs or 'hidden' in x.attrs or any(k.startswith('on') for k in x.attrs) for x in [block]+descendants):
        errors.append('不要用内联样式、隐藏内容或事件脚本构造状态。')
    if '{{' in block.text() or '}}' in block.text():
        errors.append('实际回复残留模板占位。')
    visible = len(compact(block.text()))
    metrics['visible_chars'] = visible
    if visible > TOTAL_LIMIT:
        errors.append(f'普通状态可见文字{visible}字，超过{TOTAL_LIMIT}字。')
    raw = re.search(r'<section\b[^>]*\bclass=["\'][^"\']*\bcs-status\b[^"\']*["\'][^>]*>[\s\S]*?</section\s*>', source, re.I)
    metrics['raw_html_chars'] = len(raw[0]) if raw else None
    if not raw:
        errors.append('未找到完整闭合的状态section。')
    elif len(raw[0]) > RAW_LIMIT:
        errors.append(f'普通状态原始HTML为{len(raw[0])}字符，超过{RAW_LIMIT}，请减少重复标记。')
    panels = [x for x in block.children if isinstance(x,Node) and x.tag == 'details' and x.has('cs-panel')]
    if not 2 <= len(panels) <= 5:
        errors.append('普通状态为2—5个栏目：world/self必有，其余按需。')
    if len(block.find('details')) != len(panels):
        errors.append('禁止嵌套折叠树或夹带旧折叠栏。')
    keys = [p.attrs.get('data-section') for p in panels]
    if len(set(keys)) != len(keys) or any(k not in LIMITS for k in keys):
        errors.append('栏目键未知或重复，允许world/self/people/threads/actions各一份。')
    if 'world' not in keys or 'self' not in keys:
        errors.append('剧情样例缺少world/self基础当前快照。')
    metrics['panels'] = []
    for panel in panels:
        key = panel.attrs.get('data-section')
        chars = len(compact(panel.text()))
        metric = {'section':key,'visible_chars':chars}
        metrics['panels'].append(metric)
        if key in LIMITS and chars > LIMITS[key]:
            errors.append(f'{key}为{chars}字，超过该栏{LIMITS[key]}字。')
        summaries = [x for x in panel.children if isinstance(x,Node) and x.tag=='summary']
        bodies = panel.find(cls='cs-panel-body')
        if len(summaries) != 1 or len(bodies) != 1:
            errors.append(f'{key}需一份summary和cs-panel-body。')
            continue
        body = bodies[0]
        if key in ('world','self'):
            terms, values = body.find('dt'), body.find('dd')
            limit = 4 if key=='world' else 6
            if not 1 <= len(terms) <= limit or len(terms)!=len(values) or any(not compact(v.text()) for v in values):
                errors.append(f'{key}需1—{limit}组有值的dt/dd字段。')
            if len({compact(t.text()) for t in terms}) != len(terms):
                errors.append(f'{key}存在重复字段。')
        elif key=='people':
            people = body.find('article','cs-person')
            names = [x.attrs.get('data-person','').strip() for x in people]
            metric['people_count']=len(people)
            if not 1<=len(people)<=3 or any(not n for n in names) or len(set(names))!=len(names):
                errors.append('people需1—3个不同且具名的当前人物。')
            for person in people:
                length=len(compact(person.text()))
                if length>90:
                    errors.append(f'人物{person.attrs.get("data-person")}介绍{length}字，超过90字。')
        elif key in ('threads','actions'):
            items=body.find('li')
            cap=40 if key=='threads' else 25
            metric['items']=len(items)
            if not 1<=len(items)<=3:
                errors.append(f'{key}需1—3项，空栏整体省略。')
            if any(not compact(x.text()) or len(compact(x.text()))>cap for x in items):
                errors.append(f'{key}每项须1—{cap}字。')
    return {'ok':not errors,'errors':errors,'metrics':metrics,'limits':{'visible_chars':TOTAL_LIMIT,'raw_html_chars':RAW_LIMIT},'modelTested':False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('html',type=Path)
    args=p.parse_args()
    result=inspect_status(args.html.read_text(encoding='utf-8-sig'))
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return int(not result['ok'])


if __name__=='__main__':
    raise SystemExit(main())
