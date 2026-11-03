#!/usr/bin/env python3
"""Offline validation of rendered LTM/STM HTML. No model calls or file mutation."""
import argparse
import json
import re
from html.parser import HTMLParser
from pathlib import Path


class Node:
    def __init__(self, tag='', attrs=()):
        self.tag, self.attrs, self.children = tag, dict(attrs), []

    def has(self, cls):
        return cls in (self.attrs.get('class') or '').split()

    def text(self):
        return ''.join(c.text() if isinstance(c, Node) else c for c in self.children)

    def find(self, tag=None, cls=None):
        result = []
        for child in self.children:
            if isinstance(child, Node):
                if (tag is None or child.tag == tag) and (cls is None or child.has(cls)):
                    result.append(child)
                result.extend(child.find(tag, cls))
        return result


class Document(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.root = Node()
        self.stack = [self.root]
        self.feed(source)
        self.close()

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}:
            self.stack.append(node)

    def handle_endtag(self, tag):
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag:
                del self.stack[i:]
                break

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def compact(text):
    return re.sub(r'\s', '', text)


def inspect(source):
    errors, snapshots = [], []
    blocks = Document(source).root.find('details', 'cs-memory-table')
    if not blocks:
        return [], ['没有找到 details.cs-memory-table；不能用四项手札替代表格。']
    for index, block in enumerate(blocks, 1):
        local = []
        fail = local.append
        snap = {'N': None, 'ltm': [], 'stm': [], 'event_lengths': {'ltm': [], 'stm': []}}
        try:
            snap['N'] = int(block.attrs['data-turn'])
            if snap['N'] < 0:
                raise ValueError()
        except (KeyError, ValueError, TypeError):
            fail('data-turn 必须为非负累计轮号。')
        summary = [c for c in block.children if isinstance(c, Node) and c.tag == 'summary']
        title = re.search(r'长期(\d+)篇[｜|]短期(\d+)篇', compact(summary[0].text())) if len(summary) == 1 else None
        if not title:
            fail('需要直接子级summary及“长期M篇｜短期k篇”实际数字。')
        if block.find('style') or block.find('script'):
            fail('记忆片段不得含style或script。')
        if '{{' in block.text() or '}}' in block.text():
            fail('实际样例残留模板占位符。')
        for kind, headers, cap in [('ltm', ['No.', 'Time', 'Scene', 'Event'], 400),
                                   ('stm', ['No.', 'Time', 'Scene', 'Layer', 'Event'], 150)]:
            tables = block.find('table', 'cs-' + kind)
            if len(tables) != 1:
                fail(f'{kind}: 必须有且仅有一张表。')
                continue
            table = tables[0]
            heads, bodies = table.find('thead'), table.find('tbody')
            if len(heads) != 1 or [compact(x.text()) for x in heads[0].find('th')] != headers:
                fail(f'{kind}: 列名/列数错误，要求 {headers}。')
            if len(bodies) != 1:
                fail(f'{kind}: 需要一个tbody。')
                continue
            empties = 0
            for row in bodies[0].find('tr'):
                cells = row.find('td')
                if row.has('cs-mem-empty'):
                    empties += 1
                    if len(cells) != 1 or cells[0].attrs.get('colspan') != str(len(headers)):
                        fail(f'{kind}: 空表提示colspan错误。')
                    continue
                if len(cells) != len(headers):
                    fail(f'{kind}: 记忆行应有{len(headers)}列。')
                    continue
                values = [c.text().strip() for c in cells]
                length = len(compact(values[-1]))
                snap[kind].append(values)
                snap['event_lengths'][kind].append(length)
                if not length or length > cap:
                    fail(f'{kind} {values[0]}: Event为{length}字，必须1—{cap}字（含数字标点）。')
                if kind == 'stm' and values[3] not in {'现实', '梦境', '回忆', '混合'}:
                    fail(f'stm {values[0]}: Layer值错误。')
            if empties != (0 if snap[kind] else 1):
                fail(f'{kind}: 空表需要且只需一条空提示，有数据时不得保留空提示。')
        m, k = len(snap['ltm']), len(snap['stm'])
        if title and tuple(map(int, title.groups())) != (m, k):
            fail('标题篇数与实际记忆行数不符，空提示不计篇数。')
        if k > 5:
            fail('STM已满6条却未归档；完成回复中应为0—5条。')
        if [r[0] for r in snap['ltm']] != [f'L{i:02d}' for i in range(1, m + 1)]:
            fail('LTM编号应为L01、L02……，不重复、不覆盖。')
        if snap['N'] is not None:
            n = snap['N']
            if k > n or [r[0] for r in snap['stm']] != [str(i) for i in range(n - k + 1, n + 1)]:
                fail('STM No.未沿用当前累计轮号。')
            metas = block.find(cls='cs-mem-meta')
            expected = f'启用后第{n}轮·本组短期{k}/6'
            if len(metas) != 1 or compact(metas[0].text()) != expected:
                fail('副标题累计轮号/本组条数不符。')
        if len(block.find(cls='cs-mem-context')) != 1:
            fail('需要一份续写位置辅助区，归档后也不能丢现场。')
        snapshots.append(snap)
        errors.extend(f'组件{index}: {e}' for e in local)
    return snapshots, errors


def transition(previous, current, mode, allow_correction=False):
    errors = []
    if previous['N'] is None or current['N'] is None:
        return ['无法比较无效轮号。']
    pn, n = previous['N'], current['N']
    pl, ps, cl, cs = previous['ltm'], previous['stm'], current['ltm'], current['stm']
    if n != pn + (mode == 'story'):
        errors.append('剧情只加1轮，场外保持轮数。')
    archive = mode == 'story' and len(ps) == 5
    if len(cl) != len(pl) + archive:
        errors.append('旧长期必须保留；仅本组满6条时新增一篇。')
    if [r[0] for r in cl[:len(pl)]] != [r[0] for r in pl]:
        errors.append('旧LTM编号或次序丢失。')
    if not allow_correction and cl[:len(pl)] != pl:
        errors.append('未授权纠错却改写/丢失了旧LTM。')
    expected_k = 0 if archive else len(ps) + (mode == 'story')
    if len(cs) != expected_k:
        errors.append('本组STM清空或追加数量错误。')
    if not archive and not allow_correction and cs[:len(ps)] != ps:
        errors.append('未归档旧STM应完整携带。')
    if archive and len(cl) > len(pl) and not re.search(rf'第{n-5}[—–\-~至]{n}轮', compact(cl[-1][-1])):
        errors.append('新归档未标明本组六轮范围。')
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('html', type=Path)
    parser.add_argument('--previous', type=Path)
    parser.add_argument('--transition', choices=['story', 'meta'], default='story')
    parser.add_argument('--allow-correction', action='store_true')
    args = parser.parse_args()
    snapshots, errors = inspect(args.html.read_text(encoding='utf-8-sig'))
    if args.previous:
        old, previous_errors = inspect(args.previous.read_text(encoding='utf-8-sig'))
        errors += ['上一份: ' + e for e in previous_errors]
        if len(old) != 1 or len(snapshots) != 1:
            errors.append('连续检查要求每个文件恰好一份记忆。')
        elif not previous_errors:
            errors += transition(old[0], snapshots[0], args.transition, args.allow_correction)
    result = {'ok': not errors, 'components': len(snapshots),
              'snapshots': [{'N': x['N'], 'M': len(x['ltm']), 'k': len(x['stm']),
                             'event_lengths': x['event_lengths']} for x in snapshots],
              'errors': errors, 'modelTested': False}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(bool(errors))


if __name__ == '__main__':
    raise SystemExit(main())
