"""Read-only character-cost inventory. Does not estimate tokens, prices or model quality."""
import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import Path

VERSION = 1
VOID = {'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}
ROOT_CLASSES = {
    'status': {'cs-status','rl-status','dfw-status'},
    'memory': {'cs-memory-table','rl-memory','dfw-memory','dfw-ltm','dfw-stm'},
    'story': {'cs-story','rl-story','dfw-story'},
}

def digest(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def load_text(path):
    return Path(path).read_text(encoding='utf-8-sig')

def visible_count(text):
    return len(re.sub(r'\s+', '', text))

class Regions(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=True)
        self.source=source
        self.starts=[0]
        self.starts += [m.end() for m in re.finditer('\n',source)]
        self.stack=[]
        self.regions=[]
        self.people=[]
        self.visible=[]
        self.inline=[]
        self.errors=[]

    def pos(self):
        line,col=self.getpos()
        return self.starts[line-1]+col

    def handle_starttag(self, tag, attrs):
        attrs=dict(attrs)
        classes=set(attrs.get('class','').split())
        kinds=[k for k,v in ROOT_CLASSES.items() if classes & v]
        if attrs.get('data-person'):
            self.people.append(attrs['data-person'])
        if attrs.get('style'):
            self.inline.append(attrs['style'])
        if tag not in VOID:
            self.stack.append({'tag':tag,'start':self.pos(),'kinds':kinds,'text':[]})

    def handle_startendtag(self, tag, attrs):
        if tag in VOID:
            self.handle_starttag(tag, attrs)
        else:
            # XML-style self-closing non-void elements contain no visible text.
            for key,value in attrs:
                if key=='style' and value:self.inline.append(value)

    def handle_data(self, data):
        if any(n['tag'] in {'style','script'} for n in self.stack):
            return
        self.visible.append(data)
        for n in self.stack:
            if n['kinds']:n['text'].append(data)

    def handle_endtag(self, tag):
        index=next((i for i in range(len(self.stack)-1,-1,-1) if self.stack[i]['tag']==tag),None)
        if index is None:return
        if index!=len(self.stack)-1:
            self.errors.append('implicitly closed or mismatched element before '+tag)
        end=self.source.find('>',self.pos())+1
        for n in self.stack[index:]:
            for kind in n['kinds']:
                self.regions.append({'kind':kind,'start':n['start'],'end':end,'visible':visible_count(''.join(n['text']))})
        self.stack=self.stack[:index]

    def totals(self, kind):
        spans=[r for r in self.regions if r['kind']==kind]
        outer=[r for r in spans if not any(s is not r and s['start']<r['start'] and r['end']<=s['end'] for s in spans)]
        return {'regions':len(outer),'raw_chars':sum(r['end']-r['start'] for r in outer),'visible_chars':sum(r['visible'] for r in outer)},outer

def reply_metrics(text):
    parser=Regions(text)
    parser.feed(text);parser.close()
    if parser.stack:parser.errors.append('unclosed elements remain')
    status,status_spans=parser.totals('status')
    memory,memory_spans=parser.totals('memory')
    story,_=parser.totals('story')
    inside=[m for m in memory_spans if any(s['start']<=m['start'] and m['end']<=s['end'] for s in status_spans)]
    status_only={'raw_chars':status['raw_chars']-sum(m['end']-m['start'] for m in inside),
                 'visible_chars':status['visible_chars']-sum(m['visible'] for m in inside)}
    counts=Counter(parser.people)
    return {'raw_chars':len(text),'visible_chars':visible_count(''.join(parser.visible)),
            'status_excluding_memory':status_only,'status_regions':status['regions'],
            'memory':memory,'story':story,'person_cards':len(parser.people),
            'duplicate_person_ids':[k for k,n in counts.items() if n>1],
            'inline_style_chars':sum(map(len,parser.inline)),
            'embedded_style_script_chars':sum(len(m[0]) for m in re.finditer(r'<(style|script)\b[^>]*>[\s\S]*?</\1\s*>',text,re.I)),
            'html_parse_notes':parser.errors,
            'unrecognized_regions':not any(parser.regions)}

def book_metrics(doc):
    if isinstance(doc,dict) and isinstance(doc.get('world_book'),list):
        entries=doc['world_book']; platform='fengyue'; bodykey='value'
        enabled=lambda e:e.get('enable',True)
        keylist=lambda e:re.sub(r'^_(or|and)_','',e.get('key','')).split('@wb@')
    elif isinstance(doc,dict) and isinstance(doc.get('entries'),list) and doc.get('format')=='worldbook':
        entries=doc['entries']; platform='chunshui'; bodykey='content'
        enabled=lambda e:e.get('enabled',True)
        keylist=lambda e:e.get('keywords',[])
    else:raise ValueError('Expected native Chunshui worldbook or Fengyue world_book, not author config')
    groups=defaultdict(list);shared=defaultdict(list);broad=[];multi=[]
    for i,e in enumerate(entries):
        if not isinstance(e,dict) or not isinstance(e.get(bodykey),str):raise ValueError('Invalid worldbook entry')
        ref=e.get('id') or (re.match(r'【([^·】]+)',e[bodykey]).group(1) if re.match(r'【([^·】]+)',e[bodykey]) else str(i+1))
        normalized=re.sub(r'\s+','',re.sub(r'^【[^】]+】\s*','',e[bodykey]))
        if len(normalized)>=80:groups[digest(normalized)].append(str(ref))
        if not enabled(e):continue
        for k in keylist(e):
            if isinstance(k,str) and k:
                shared[k].append(str(ref))
                if k in {'她','他','你','今天','人物','外貌','经历','性格','过去','喜欢','状态'}:broad.append({'entry':str(ref),'key':k})
        positions=e.get('insertionPositions',[])
        region=e.get('value_region',0)
        if (platform=='fengyue' and isinstance(region,int) and region.bit_count()>1) or (platform=='chunshui' and isinstance(positions,list) and len(set(positions))>1):multi.append(str(ref))
    return {'platform':platform,'entries':len(entries),'enabled_entries':sum(bool(enabled(e)) for e in entries),
            'body_chars':sum(len(e[bodykey]) for e in entries),
            'enabled_body_chars':sum(len(e[bodykey]) for e in entries if enabled(e)),
            'duplicate_bodies':[v for v in groups.values() if len(v)>1],
            'shared_keys':[{'key':k,'entries':v} for k,v in shared.items() if len(v)>1],
            'broad_key_candidates':broad,'multiple_insertion_candidates':multi,
            'runtime_injection_measured':False}

def scene_metrics(doc):
    cases=doc.get('triggerTests',{}).get('cases') if isinstance(doc,dict) else None
    if cases is None:cases=doc.get('cases') if isinstance(doc,dict) else doc
    if not isinstance(cases,list):raise ValueError('Unrecognized scene result format; run the platform trigger checker first')
    rows=[]
    for c in cases:
        n=c.get('bodyCharacters',c.get('content_chars_estimate'))
        if isinstance(n,(int,float)):
            rows.append({'name':c.get('name',''),'body_chars':n,'checker_status':c.get('status',c.get('passed','unknown'))})
    return {'measured_cases':len(rows),'largest_body_chars':max([r['body_chars'] for r in rows],default=None),'cases':rows,
            'meaning':'Direct offline matches only; not server injection, history, tokenizer or total bill.'}

def make_report(args):
    report={'version':VERSION,'unit':'Unicode characters after UTF-8 decoding and newline normalization; not tokens or prices',
            'read_only':True,'prompts':[],'worldbooks':[],'replies':[],'scene_reports':[]}
    blocks=defaultdict(list)
    for path in args.prompt:
        text=load_text(path)
        report['prompts'].append({'file':str(Path(path).resolve()),'chars':len(text),'sha256_normalized':digest(text)})
        for n,b in enumerate(re.split(r'\n\s*\n',text),1):
            b=re.sub(r'\s+','',b)
            if len(b)>=60:blocks[digest(b)].append({'file':str(Path(path).resolve()),'paragraph':n,'chars':len(b)})
    report['repeated_prompt_blocks']=[v for v in blocks.values() if len(v)>1]
    for path in args.worldbook:report['worldbooks'].append({'file':str(Path(path).resolve()),**book_metrics(json.loads(load_text(path)))})
    for path in args.reply:report['replies'].append({'file':str(Path(path).resolve()),**reply_metrics(load_text(path))})
    for path in args.scene_report:report['scene_reports'].append({'file':str(Path(path).resolve()),**scene_metrics(json.loads(load_text(path)))})
    report['totals']={'selected_prompt_chars':sum(r['chars'] for r in report['prompts']),
                      'archive_worldbook_body_chars':sum(r['body_chars'] for r in report['worldbooks']),
                      'selected_reply_chars':sum(r['raw_chars'] for r in report['replies'])}
    if len(report['replies'])>1:
        first,last=report['replies'][0],report['replies'][-1]
        report['snapshot_comparison']={'status_visible_delta':last['status_excluding_memory']['visible_chars']-first['status_excluding_memory']['visible_chars'],
                                      'memory_visible_delta':last['memory']['visible_chars']-first['memory']['visible_chars'],
                                      'note':'Growth is a review signal, not a failure. Compare active actors and new facts; legitimate detail is allowed.'}
    if args.baseline:
        before=json.loads(load_text(args.baseline))
        if before.get('version')!=VERSION or not isinstance(before.get('totals'),dict):raise ValueError('Unsupported baseline')
        report['baseline_comparison']={'requires_same_selected_files_and_scenarios':True,
                                      'current_minus_baseline':{k:v-before['totals'].get(k,0) for k,v in report['totals'].items()}}
    report['limits']=['No automatic shortening or deletion.', 'Literal duplicates and broad triggers need human review.',
                      'Unknown CSS prefixes are not treated as zero-cost proof.', 'No platform/history/cache behavior or live-model quality measured.']
    return report

def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['prompt','worldbook','reply','scene-report']:p.add_argument('--'+name,action='append',default=[])
    p.add_argument('--baseline');p.add_argument('--out',required=True);p.add_argument('--overwrite',action='store_true')
    args=p.parse_args()
    inputs=args.prompt+args.worldbook+args.reply+args.scene_report+([args.baseline] if args.baseline else [])
    if not inputs:p.error('Provide at least one source file')
    target=Path(args.out).resolve()
    if target in {Path(f).resolve() for f in inputs}:raise ValueError('Report cannot overwrite any input')
    if target.exists() and not args.overwrite:raise FileExistsError('Report exists; use --overwrite only for this generated report')
    report=make_report(args)
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('w' if args.overwrite else 'x',encoding='utf-8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
    print(json.dumps({'report':str(target),'totals':report['totals'],'prompt_duplicate_groups':len(report['repeated_prompt_blocks']),
                      'worldbook_duplicate_groups':sum(len(b['duplicate_bodies']) for b in report['worldbooks']),
                      'not_token_or_quality_score':True},ensure_ascii=False))

if __name__=='__main__':
    if hasattr(sys.stdout,'reconfigure'):sys.stdout.reconfigure(encoding='utf-8')
    try:main()
    except (OSError,ValueError,KeyError,TypeError) as e:
        print(json.dumps({'error':str(e)},ensure_ascii=False));raise SystemExit(1)
