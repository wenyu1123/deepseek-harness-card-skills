"""Local, standard-library helpers for the documented Chunshui reference schema."""
import argparse
import json
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path


def reject_constant(value):
    raise ValueError('Non-finite JSON number: ' + value)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key: ' + key)
        result[key] = value
    return result


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'),
                      object_pairs_hook=unique_object, parse_constant=reject_constant)


def dumps(data):
    return json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n'


def emit(data):
    print(dumps(data), end='')


def check_book(book):
    errors, warnings = [], []
    if not isinstance(book, dict):
        return ['Top level must be an object'], warnings
    if book.get('format') != 'worldbook' or type(book.get('version')) is not int or book.get('version') != 1:
        errors.append('Expected reference format=worldbook and integer version=1')
    for field in ['title', 'exportedAt']:
        if not isinstance(book.get(field), str) or not book[field].strip():
            errors.append('Missing nonempty string: ' + field)
    groups, entries = book.get('categories'), book.get('entries')
    if not isinstance(groups, list) or not isinstance(entries, list):
        return errors + ['categories and entries must be arrays'], warnings
    if not entries:
        warnings.append('Worldbook has no entries')
    group_ids, entry_ids = set(), set()
    for i, group in enumerate(groups):
        loc = f'categories[{i}]'
        if not isinstance(group, dict):
            errors.append(loc + ' must be an object'); continue
        gid = group.get('id')
        if not isinstance(gid, str) or not gid:
            errors.append(loc + ': missing string id')
        elif gid in group_ids:
            errors.append(loc + ': duplicate category id')
        else:
            group_ids.add(gid)
        if not isinstance(group.get('name'), str) or not group['name'].strip():
            errors.append(loc + ': missing category name')
    for i, entry in enumerate(entries):
        loc = f'entries[{i}]'
        if not isinstance(entry, dict):
            errors.append(loc + ' must be an object'); continue
        eid = entry.get('id')
        if not isinstance(eid, str) or not eid:
            errors.append(loc + ': missing string id')
        elif eid in entry_ids:
            errors.append(loc + ': duplicate entry id')
        else:
            entry_ids.add(eid)
        cid = entry.get('categoryId')
        if not isinstance(cid, str) or cid not in group_ids:
            errors.append(loc + ': categoryId does not reference a category')
        for field in ['entryName', 'content']:
            if not isinstance(entry.get(field), str) or not entry[field].strip():
                errors.append(loc + ': missing nonempty ' + field)
        keys = entry.get('keywords')
        if not isinstance(keys, list) or not keys or any(not isinstance(k, str) or not k.strip() for k in keys):
            errors.append(loc + ': keywords must be a nonempty string array'); keys = []
        for field in ['enabled', 'caseSensitive', 'matchWholeWords', 'regexMatch']:
            if type(entry.get(field)) is not bool:
                errors.append(loc + ': ' + field + ' must be boolean')
        secondary = entry.get('secondaryKeywords', [])
        if not isinstance(secondary, list) or any(not isinstance(k, str) or not k.strip() for k in secondary):
            errors.append(loc + ': secondaryKeywords must be a string array')
        for field in ['priority', 'scanDepth', 'triggerProbability']:
            if type(entry.get(field)) is not int:
                errors.append(loc + ': ' + field + ' must be integer')
        if type(entry.get('scanDepth')) is int and entry['scanDepth'] < 1:
            warnings.append(loc + ': scanDepth below 1 requires platform-specific interpretation')
        if type(entry.get('triggerProbability')) is int and not 0 <= entry['triggerProbability'] <= 100:
            errors.append(loc + ': triggerProbability must be 0..100 in this reference profile')
        areas = entry.get('triggerAreas')
        if areas is not None:
            if not isinstance(areas, list) or not areas or any(a not in ['user', 'assistant', 'system'] for a in areas):
                errors.append(loc + ': invalid triggerAreas')
            elif 'system' in areas:
                warnings.append(loc + ': scans system; inspect self-trigger risk')
        elif entry.get('triggerArea') not in ['user', 'assistant', 'system', 'all']:
            errors.append(loc + ': missing recognized trigger area')
        if entry.get('position') != 'system_prompt':
            warnings.append(loc + ': nonreference insertion position; verify on platform')
        if entry.get('matchLogic') not in ['or', 'and']:
            warnings.append(loc + ': matching logic outside local simulator')
        if entry.get('regexMatch') is True:
            for k in keys:
                if re.search(r'\(\?(?:[=!]|<[=!])|\\(?:[1-9]|k[<{]|g[<{])|\(\?P=', k):
                    errors.append(loc + ': lookaround/backreference is not supported by the recorded RE2-style engine')
                elif k not in [r'[\s\S]', r'(?s).+']:
                    warnings.append(loc + ': regex requires actual target-engine validation: ' + k)
        else:
            for k in keys:
                if k in ['我', '你', '他', '她', '去', '人', '继续']:
                    warnings.append(loc + ': broad keyword may over-trigger: ' + k)
        if len(keys) != len(set(keys)):
            warnings.append(loc + ': duplicate keywords')
    return errors, warnings


def make_book(master):
    if not isinstance(master, dict):
        raise ValueError('Master must be an object')
    ns = uuid.UUID(master['namespace'])
    groups = master['groups']; records = master['entries']
    if not isinstance(groups, list) or not isinstance(records, list):
        raise ValueError('groups/entries must be arrays')
    def sid(kind, key): return str(uuid.uuid5(ns, kind + ':' + key))
    seen_groups, seen_entries = set(), set()
    categories, entries = [], []
    for i, g in enumerate(groups):
        key = g['key']
        if not isinstance(key, str) or not key or key in seen_groups:
            raise ValueError('Missing/duplicate group key')
        seen_groups.add(key)
        categories.append(dict(id=sid('group', key), name=g['name'], color=g.get('color', '#859A85'),
                               description=g.get('description', ''), sort=i))
    for r in records:
        key = r['key']
        if not isinstance(key, str) or not key or key in seen_entries:
            raise ValueError('Missing/duplicate entry key')
        seen_entries.add(key)
        if r['group'] not in seen_groups:
            raise ValueError('Unknown group for ' + key)
        constant = r.get('constant', False)
        if type(constant) is not bool:
            raise ValueError('constant must be boolean')
        areas = ['user'] if constant else r.get('areas', ['user', 'assistant'])
        entries.append(dict(id=sid('entry', key), entryName=r['name'], content=r['content'],
            keywords=[r'[\s\S]'] if constant else r['keywords'], secondaryKeywords=[],
            enabled=r.get('enabled', True), categoryId=sid('group', r['group']),
            position='system_prompt', insertionPositions=['system_prompt'],
            priority=r.get('priority', 100 if constant else 40), scanDepth=1 if constant else r.get('depth', 2),
            caseSensitive=False, matchWholeWords=False, regexMatch=constant,
            triggerArea=areas[0] if isinstance(areas, list) and len(areas) == 1 else 'all', triggerAreas=areas,
            matchLogic='or', triggerProbability=100))
    book = dict(format='worldbook', version=1, exportedAt=datetime.now(timezone.utc).isoformat(),
                title=master['title'], categories=categories, entries=entries)
    errors, _ = check_book(book)
    if errors: raise ValueError('; '.join(errors))
    return book


def write_book(master, target, overwrite=False):
    target = Path(target)
    book = make_book(master)
    reading = target.with_name(target.stem + '_阅读版.txt')
    index = target.with_name(target.stem + '_触发目录.txt')
    paths = [target, reading, index]
    if not overwrite and any(p.exists() for p in paths):
        raise FileExistsError('Output exists; choose a new version or explicitly use --overwrite')
    if any(p.is_dir() for p in paths):
        raise IsADirectoryError('An output path is a directory')
    rows, triggers = [book['title'], '完整阅读版', ''], [book['title'], '触发目录（非线上测试结果）', '']
    for c in book['categories']:
        rows.append('\n【' + c['name'] + '】')
        for e in book['entries']:
            if e['categoryId'] != c['id']: continue
            rows.extend([e['entryName'], e['content'], ''])
            triggers.extend([e['entryName'], ' / '.join(e['keywords']),
                             '范围=' + ','.join(e['triggerAreas']) + '; 深度=' + str(e['scanDepth']), ''])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(dumps(book), encoding='utf-8')
    reading.write_text('\n'.join(rows), encoding='utf-8-sig')
    index.write_text('\n'.join(triggers), encoding='utf-8-sig')
    return {'files': [str(p.resolve()) for p in paths], 'entries': len(book['entries']),
            'bodyCharacters': sum(len(e['content']) for e in book['entries']), 'onlineTested': False}


def initialize(name, dest):
    if (not name.strip() or name != name.strip() or name.endswith('.') or len(name) > 100 or
            re.search(r'[<>:"/\\|?*\x00-\x1f]', name) or name in ['.', '..'] or
            re.match(r'^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)', name, re.I)):
        raise ValueError('Use a safe single folder name, without path separators or reserved names')
    parent = Path(dest).resolve(); project = parent / name
    if project.exists(): raise FileExistsError('Project already exists; no files changed')
    project.mkdir(parents=True)
    source = project / '源稿'; source.mkdir()
    master = {'title': name, 'namespace': str(uuid.uuid4()),
        'groups': [{'key': 'people', 'name': '人物', 'color': '#859A85'},
                   {'key': 'places', 'name': '地点', 'color': '#879AAF'}],
        'entries': [
            {'key': 'lin-core', 'group': 'people', 'name': '教学示例·林知夏核心',
             'keywords': ['林知夏', '林师傅'], 'content': '教学示例，须改为作品人物：林知夏，27岁，雨巷书店修书师。谨慎耐心，先核实旧信的出处再接修复委托。',
             'areas': ['user', 'assistant'], 'depth': 2},
            {'key': 'bookshop', 'group': 'places', 'name': '教学示例·雨巷书店入口',
             'keywords': ['雨巷书店', '旧书店'], 'content': '教学示例，须改为作品地点：雨巷书店里，修书师林知夏正在核对纸样。玩家可以问她那封受潮旧信的来历，暂不预定回答。',
             'areas': ['user', 'assistant'], 'depth': 2}]}
    (source / '世界母稿.json').write_text(dumps(master), encoding='utf-8')
    result = write_book(master, project / '01_世界书_导入.json')
    (project / '00_使用说明.txt').write_text('这是可运行的极小教学骨架，不是完成的用户作品。\n先编辑源稿/世界母稿.json，再调用build生成世界书。\n01_世界书_导入.json放春水世界书的导入JSON；阅读版与触发目录不导入。\n发布之前核对实际平台格式与保存结果。\n', encoding='utf-8-sig')
    result['project'] = str(project)
    return result


def simulate(book, messages):
    errors, warnings = check_book(book)
    if errors: raise ValueError('; '.join(errors))
    hits, unsupported = [], []
    for e in book['entries']:
        if not e['enabled']: continue
        reasons = []
        if e.get('secondaryKeywords'): reasons.append('secondary keyword semantics')
        if e['triggerProbability'] != 100: reasons.append('probability')
        if e['matchWholeWords']: reasons.append('whole-word semantics')
        if e['matchLogic'] not in ['or', 'and']: reasons.append('matching logic')
        if e['scanDepth'] < 1: reasons.append('scanDepth below 1')
        if e['regexMatch'] and any(k not in [r'[\s\S]', r'(?s).+'] for k in e['keywords']): reasons.append('complex regex')
        areas = e.get('triggerAreas')
        if areas is None:
            areas = ['user', 'assistant', 'system'] if e['triggerArea'] == 'all' else [e['triggerArea']]
        if 'system' in areas: warnings.append(e['entryName'] + ': system input not modeled')
        if reasons:
            unsupported.append({'name': e['entryName'], 'reasons': reasons}); continue
        texts = [m['content'] for m in messages[-e['scanDepth']:] if m['role'] in areas]
        if e['regexMatch']:
            matched = [k for k in e['keywords'] if any(len(t) > 0 for t in texts)]
        else:
            if not e['caseSensitive']: texts = [t.casefold() for t in texts]
            matched = [k for k in e['keywords'] if any((k if e['caseSensitive'] else k.casefold()) in t for t in texts)]
        yes = bool(matched) if e['matchLogic'] == 'or' else len(matched) == len(e['keywords'])
        if yes:
            hits.append({'name': e['entryName'], 'id': e['id'], 'matched': matched, 'characters': len(e['content'])})
    return {'scope': 'Local approximation; recent message-count depth, no recursion, budget or platform runtime',
            'hits': hits, 'bodyCharacters': sum(h['characters'] for h in hits), 'unsupported': unsupported,
            'warnings': warnings, 'onlineTested': False}


class MessageAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
        messages = list(getattr(namespace, self.dest, None) or [])
        messages.append({'role': option_string[2:], 'content': values})
        setattr(namespace, self.dest, messages)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    init = sub.add_parser('init'); init.add_argument('--name', required=True); init.add_argument('--dest', required=True)
    build = sub.add_parser('build'); build.add_argument('--source', required=True); build.add_argument('--out', required=True); build.add_argument('--overwrite', action='store_true')
    val = sub.add_parser('validate'); val.add_argument('file')
    sim = sub.add_parser('simulate'); sim.add_argument('file'); sim.add_argument('--user', dest='messages', action=MessageAction); sim.add_argument('--assistant', dest='messages', action=MessageAction)
    a = p.parse_args()
    if a.command == 'init': emit(initialize(a.name, a.dest))
    elif a.command == 'build': emit(write_book(read_json(a.source), a.out, a.overwrite))
    elif a.command == 'validate':
        book = read_json(a.file); errors, warnings = check_book(book)
        emit({'valid': not errors, 'errors': errors, 'warnings': warnings, 'onlineTested': False})
        return 1 if errors else 0
    else:
        if not a.messages: p.error('simulate requires at least one --user or --assistant message')
        emit(simulate(read_json(a.file), a.messages))
    return 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyError, TypeError) as exc:
        emit({'error': str(exc), 'onlineTested': False})
        sys.exit(1)
