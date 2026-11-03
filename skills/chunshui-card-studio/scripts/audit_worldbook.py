"""Read-only worldbook lint and literal-trigger cases; no literary-quality score."""
import argparse
import json
import re
import sys
from collections import defaultdict
from itertools import combinations
from pathlib import Path

from cardkit import check_book, dumps, read_json, simulate


BROAD = {'我', '你', '他', '她', '人', '去', '继续', '过去', '经历', '历史',
         '性格', '外貌', '身体', '关系', '公司', '家', '朋友', '孩子', '一起', '以后'}
PLACEHOLDER = re.compile(r'待补充|此处填写|其余类似|自行脑补|后续自由发挥')
ANY_TEXT = {r'[\s\S]', r'(?s).+'}


def normalized(value):
    return re.sub(r'\s+', '', value).casefold()


def entry_ref(entry):
    return {'id': entry['id'], 'name': entry['entryName']}


def lint(entries):
    """Heuristic candidates only. Do not mutate content or treat warnings as facts."""
    findings = []
    keywords, identical = defaultdict(list), defaultdict(list)
    bodies = []
    for e in entries:
        body = normalized(e['content'])
        identical[body].append(e)
        if len(body) >= 120:
            bodies.append((e, body, {body[i:i + 4] for i in range(len(body) - 3)}))
        if not e['enabled']:
            continue
        if not e['regexMatch']:
            wide = sorted(set(e['keywords']) & BROAD)
            if wide:
                findings.append({'kind': 'broad_keywords', **entry_ref(e), 'keywords': wide})
            for k in set(e['keywords']):
                keywords[k.casefold()].append(e)
        areas = e.get('triggerAreas')
        if (areas is not None and 'system' in areas) or (areas is None and e.get('triggerArea') in ('all', 'system')):
            findings.append({'kind': 'system_scan_review', **entry_ref(e)})
        placeholders = sorted(set(PLACEHOLDER.findall(e['content'])))
        if placeholders:
            findings.append({'kind': 'possible_placeholder', **entry_ref(e), 'phrases': placeholders})
    for key, group in keywords.items():
        if len(group) > 1:
            findings.append({'kind': 'shared_keyword', 'keyword': key,
                             'entries': [entry_ref(e) for e in group],
                             'bodyCharacters': sum(len(e['content']) for e in group)})
    for group in identical.values():
        if len(group) > 1:
            findings.append({'kind': 'identical_body', 'entries': [entry_ref(e) for e in group]})
    near_total = 0
    for (a, sa, ga), (b, sb, gb) in combinations(bodies, 2):
        if sa == sb or min(len(sa), len(sb)) / max(len(sa), len(sb)) < .8:
            continue
        overlap = len(ga & gb) / len(ga | gb)
        if overlap >= .82:
            near_total += 1
            if near_total <= 40:
                findings.append({'kind': 'near_duplicate_review', 'entries': [entry_ref(a), entry_ref(b)],
                                 'shingleJaccard': round(overlap, 3)})
    if near_total > 40:
        findings.append({'kind': 'near_duplicate_report_truncated', 'pairsTotal': near_total, 'shown': 40})
    return findings


def resolve_plan(book, plan):
    if not isinstance(plan, dict) or not isinstance(plan.get('cases'), list) or not plan['cases']:
        raise ValueError('cases must be a nonempty array')
    ids = {e['id']: e for e in book['entries']}
    names = defaultdict(list)
    for e in book['entries']:
        names[e['entryName']].append(e['id'])

    def refs(value, label):
        if not isinstance(value, list) or any(not isinstance(x, str) or not x for x in value):
            raise ValueError(label + ' must be a string array')
        resolved = []
        for name in value:
            if name in ids:
                eid = name
            elif name not in names:
                raise ValueError(label + ': unknown entry selector: ' + name)
            elif len(names[name]) != 1:
                raise ValueError(label + ': ambiguous entry name; use id: ' + name)
            else:
                eid = names[name][0]
            if eid in resolved:
                raise ValueError(label + ': duplicate selector: ' + name)
            resolved.append(eid)
        return set(resolved)

    required = refs(plan.get('requiredCoverage', []), 'requiredCoverage')
    cases, case_names = [], set()
    for c in plan['cases']:
        if not isinstance(c, dict):
            raise ValueError('Each case must be an object')
        name = c.get('name')
        if not isinstance(name, str) or not name.strip() or name in case_names:
            raise ValueError('Each case must have a nonempty unique name')
        case_names.add(name)
        messages = c.get('messages')
        if not isinstance(messages, list) or not messages:
            raise ValueError(name + ': messages must be nonempty')
        for m in messages:
            if (not isinstance(m, dict) or m.get('role') not in ('user', 'assistant') or
                    not isinstance(m.get('content'), str) or not m['content'].strip()):
                raise ValueError(name + ': use nonempty user/assistant messages in chronological order')
        must = refs(c.get('mustHit', []), name + '.mustHit')
        forbidden = refs(c.get('mustNotHit', []), name + '.mustNotHit')
        only = refs(c['onlyHit'], name + '.onlyHit') if 'onlyHit' in c else None
        maximum = c.get('maxCharacters')
        if 'maxCharacters' in c and (type(maximum) is not int or maximum < 0):
            raise ValueError(name + ': maxCharacters must be a nonnegative integer')
        if not must and not forbidden and only is None and maximum is None:
            raise ValueError(name + ': at least one expectation is required')
        if must & forbidden or (only is not None and not must <= only):
            raise ValueError(name + ': contradictory expectations')
        cases.append({'name': name, 'messages': messages, 'must': must, 'forbidden': forbidden,
                      'only': only, 'maximum': maximum})
    return required, cases


def run_cases(book, plan):
    required, cases = resolve_plan(book, plan)
    by_id = {e['id']: e for e in book['entries']}
    # Only successful explicit positive expectations count as required coverage.
    positive_coverage, observed = set(), set()
    results = []
    for case in cases:
        result = simulate(book, case['messages'])
        hits = {h['id'] for h in result['hits']}
        observed |= hits
        unknown = bool(result['unsupported'])
        issues, pending = [], []
        for eid in case['must'] - hits:
            # The old simulator's unsupported rows identify by name, which may be
            # duplicated. Conservatively leave missing expectations inconclusive.
            (pending if unknown else issues).append('missing expected: ' + by_id[eid]['entryName'])
        for eid in case['forbidden'] & hits:
            issues.append('forbidden hit: ' + by_id[eid]['entryName'])
        if case['only'] is not None:
            for eid in hits - case['only']:
                issues.append('unexpected hit: ' + by_id[eid]['entryName'])
        if case['maximum'] is not None and result['bodyCharacters'] > case['maximum']:
            issues.append('bodyCharacters exceeds case budget: ' + str(case['maximum']))
        status = 'failed' if issues else 'inconclusive' if unknown else 'passed'
        if status == 'passed':
            positive_coverage |= case['must'] & hits
        results.append({'name': case['name'], 'status': status, 'hits': result['hits'],
                        'bodyCharacters': result['bodyCharacters'], 'issues': issues,
                        'pendingExpectations': pending, 'unsupported': result['unsupported']})
    statuses = [r['status'] for r in results]
    uncovered = required - positive_coverage
    status = ('failed' if 'failed' in statuses else 'inconclusive' if 'inconclusive' in statuses
              else 'failed' if uncovered else 'passed')
    return {'status': status, 'cases': results,
            'requiredNotConfirmed': [entry_ref(e) for e in book['entries'] if e['id'] in uncovered],
            'entriesNotObserved': [entry_ref(e) for e in book['entries'] if e['enabled'] and e['id'] not in observed],
            'observedEntries': len(observed), 'positiveCoverageEntries': len(positive_coverage),
            'largestCaseBodyCharacters': max(r['bodyCharacters'] for r in results)}


def audit(book, plan=None):
    errors, warnings = check_book(book)
    report = {'scope': 'Offline structure, heuristic lint, and literal matching only; no recursion or platform budget.',
              'onlineTested': False, 'modelPlaytested': False, 'paidModelCalls': 0,
              'structure': {'valid': not errors, 'errors': errors, 'warnings': warnings},
              'contentReview': 'manual_required', 'triggerTests': {'status': 'not_run'}}
    if errors:
        return report
    entries = book['entries']
    constants = [e for e in entries if e['enabled'] and e['regexMatch'] and any(k in ANY_TEXT for k in e['keywords'])]
    report['metrics'] = {'entries': len(entries), 'enabledEntries': sum(e['enabled'] for e in entries),
                         'totalBodyCharacters': sum(len(e['content']) for e in entries),
                         'alwaysOnCandidateEntries': [entry_ref(e) for e in constants],
                         'alwaysOnCandidateBodyCharacters': sum(len(e['content']) for e in constants),
                         'characterMeasure': 'Python Unicode characters in content including whitespace, not tokens'}
    report['findings'] = lint(entries)
    if plan is not None:
        report['triggerTests'] = run_cases(book, plan)
    return report


def exit_code(report):
    status = report['triggerTests']['status']
    if not report['structure']['valid'] or status == 'failed':
        return 1
    return 2 if status == 'inconclusive' else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('book')
    parser.add_argument('--cases')
    parser.add_argument('--out')
    parser.add_argument('--overwrite', action='store_true')
    args = parser.parse_args()
    target = Path(args.out) if args.out else None
    if target:
        if target.resolve() in {Path(p).resolve() for p in (args.book, args.cases) if p}:
            raise ValueError('Report must not replace a worldbook or case file')
        if target.exists() and not args.overwrite:
            raise FileExistsError('Report exists; use --overwrite only for your generated report')
    report = audit(read_json(args.book), read_json(args.cases) if args.cases else None)
    if target:
        target.parent.mkdir(parents=True, exist_ok=True)
        # Exclusive creation prevents racing with a new report when not authorized to overwrite.
        with target.open('w' if args.overwrite else 'x', encoding='utf-8') as f:
            f.write(dumps(report))
        print(dumps({'report': str(target.resolve()), 'structureValid': report['structure']['valid'],
                     'triggerStatus': report['triggerTests']['status'], 'onlineTested': False}), end='')
    else:
        print(dumps(report), end='')
    return exit_code(report)


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyError, TypeError) as exc:
        print(json.dumps({'error': str(exc), 'onlineTested': False}, ensure_ascii=False))
        sys.exit(1)
