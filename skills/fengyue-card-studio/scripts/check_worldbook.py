"""Validate Fengyue's native format; optional literal-key/regex approximation cases."""
import argparse
import json
import re
from pathlib import Path


def no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f'duplicate JSON key: {key}')
        result[key] = value
    return result


def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'), object_pairs_hook=no_duplicates)


def entry_id(entry, index):
    found = re.match(r'【([^·】]+)[·】]', entry.get('value', ''))
    return found.group(1) if found else str(index + 1)


def validate(doc):
    errors, warnings = [], []
    if not isinstance(doc, dict) or not isinstance(doc.get('world_book'), list):
        return ['root must contain world_book array'], warnings
    if not doc['world_book']:
        errors.append('empty world_book')
    seen = set()
    for i, e in enumerate(doc['world_book']):
        prefix = f'entry {i+1}'
        if not isinstance(e, dict):
            errors.append(prefix + ': must be object')
            continue
        for key in ('key', 'value', 'group'):
            if not isinstance(e.get(key), str):
                errors.append(f'{prefix}: {key} must be string')
        for key, lo, hi in [('key_region',1,7), ('value_region',1,7), ('depth',0,20), ('probability',1,100), ('match_type',2,3), ('value_type',0,1)]:
            value = e.get(key)
            if type(value) is not int or not lo <= value <= hi:
                errors.append(f'{prefix}: invalid {key}')
        if type(e.get('sort')) is not int or type(e.get('enable')) is not bool:
            errors.append(prefix + ': invalid sort/enable')
        configs = e.get('value_configs')
        if not isinstance(configs, list):
            errors.append(prefix + ': value_configs must be array')
        elif e.get('value_type') == 1:
            if not configs:
                errors.append(prefix + ': probability mode requires values')
            for v in configs:
                if not isinstance(v, dict) or not isinstance(v.get('value'), str) or not v['value'].strip() or type(v.get('probability')) is not int or not 1 <= v['probability'] <= 100:
                    errors.append(prefix + ': invalid probability value')
        elif not isinstance(e.get('value'), str) or not e['value'].strip():
            errors.append(prefix + ': empty regular content')
        key = e.get('key', '')
        if isinstance(key, str) and e.get('match_type') == 2:
            if not key.startswith(('_or_', '_and_')):
                errors.append(prefix + ': missing _or_ / _and_')
            else:
                tokens = key.split('_', 2)[2].split('@wb@')
                if any(not t.strip() for t in tokens) or len(tokens) != len(set(tokens)):
                    errors.append(prefix + ': empty or duplicate keyword')
                if any(t in {'她','他','你','今天','人物','喜欢'} for t in tokens):
                    warnings.append(prefix + ': broad trigger; inspect fan-out')
        elif isinstance(key, str) and e.get('match_type') == 3:
            if re.search(r'\(\?(?:[=!]|<[=!])|\\[1-9]|\(\?P=', key):
                errors.append(prefix + ': unsupported lookaround/backreference profile')
            try:
                re.compile(key)
            except re.error as exc:
                errors.append(f'{prefix}: regex syntax {exc}')
            warnings.append(prefix + ': regex needs actual platform verification')
        identity = entry_id(e, i) if isinstance(e.get('value'), str) else str(i)
        if identity in seen:
            errors.append(prefix + ': duplicate author ID ' + identity)
        seen.add(identity)
    return errors, warnings


def matches(entry, messages):
    if not entry['enable']:
        return False
    bits = {'system':1, 'user':2, 'assistant':4}
    text = '\n'.join(m['text'] for m in messages if bits.get(m['role'],0) & entry['key_region'])
    if entry['match_type'] == 3:
        return bool(re.search(entry['key'], text))
    key = entry['key']
    tokens = key[4:].split('@wb@') if key.startswith('_or_') else key[5:].split('@wb@')
    return (any if key.startswith('_or_') else all)(t in text for t in tokens)


def run_cases(doc, cases):
    results = []
    for case in cases:
        messages = case.get('messages', [{'role':'user', 'text':case.get('text','')}])
        hit = [entry_id(e,i) for i,e in enumerate(doc['world_book']) if matches(e,messages)]
        passed = set(case.get('must',[])) <= set(hit) and not set(case.get('must_not',[])) & set(hit)
        chars = sum(len(e['value']) for i,e in enumerate(doc['world_book']) if entry_id(e,i) in hit)
        results.append({'name':case.get('name',case.get('text','')), 'passed':passed, 'matched':hit, 'content_chars_estimate':chars})
    return results


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file')
    parser.add_argument('--cases')
    args = parser.parse_args()
    try:
        doc = load(args.file)
        errors, warnings = validate(doc)
        cases = run_cases(doc, load(args.cases)) if args.cases and not errors else []
        passed = not errors and all(c['passed'] for c in cases)
        print(json.dumps({'passed':passed,'errors':errors,'warnings':warnings,'cases':cases,'limits':'depth, server engine, probability draw and recursive injection are not simulated'},ensure_ascii=False,indent=2))
    except (ValueError, OSError, TypeError, KeyError) as exc:
        print(json.dumps({'passed':False,'error':str(exc)},ensure_ascii=False))
        passed = False
    raise SystemExit(0 if passed else 1)
