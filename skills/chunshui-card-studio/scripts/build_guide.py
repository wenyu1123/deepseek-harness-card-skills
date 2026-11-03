"""Build a complete sectional persona guide. Static compatibility is explicit, not the default."""
import argparse
import html
import json
import re
from pathlib import Path
from urllib.parse import urlparse

ASSETS=Path(__file__).resolve().parent.parent/'assets'


def esc(value):
    return html.escape(str(value),quote=True)


def button(text, attrs='', secondary=False):
    return f'<button type="button" class="cs-button{" cs-secondary" if secondary else ""}" data-js-button disabled {attrs}>{text}</button>'


def paragraphs(text):
    return ''.join('<p>'+esc(p)+'</p>' for p in re.split(r'\n\s*\n',text) if p.strip())


def validate(cfg):
    for key in ('title','subtitle','world','play'):
        if not isinstance(cfg.get(key),str) or not cfg[key].strip():raise ValueError('missing '+key)
    for key in ('characters','openings','fields'):
        if not isinstance(cfg.get(key),list) or not cfg[key]:raise ValueError('empty '+key)
    keys=[]
    for f in cfg['fields']:
        if not isinstance(f,dict) or not re.fullmatch(r'[a-z][a-z0-9_-]*',f.get('key','')):raise ValueError('invalid field key')
        if not isinstance(f.get('label'),str) or not f['label']:raise ValueError('field label is required')
        if f.get('type','textarea') not in ('text','textarea','select','number'):raise ValueError('unsupported field type')
        if f.get('type')=='select' and (not isinstance(f.get('options'),list) or not f['options']):raise ValueError('select needs options')
        keys.append(f['key'])
    if len(keys)!=len(set(keys)):raise ValueError('duplicate field key')
    for c in cfg['characters']:
        for key in ('name','role','appearance','history','personality','relationship'):
            if not isinstance(c.get(key),str):raise ValueError('missing character '+key)
    for o in cfg['openings']:
        if not isinstance(o.get('title'),str) or not isinstance(o.get('text'),str):raise ValueError('invalid opening')
    opening_pairs=[(o['title'].strip(),o['text'].strip()) for o in cfg['openings']]
    if len(opening_pairs)!=len(set(opening_pairs)):raise ValueError('duplicate opening')
    if cfg.get('theme','rose-letter') not in ('rose-letter','jade-scroll'):raise ValueError('unsupported theme')
    if not isinstance(cfg.get('fixed_notes',[]),list):raise ValueError('fixed_notes must be list')
    background=cfg.get('background','')
    if background and urlparse(background).scheme not in ('https','data'):raise ValueError('background must be https or image data URL')
    if background.startswith('data:') and not background.startswith(('data:image/png;base64,','data:image/jpeg;base64,','data:image/webp;base64,')):raise ValueError('unsupported image data URL')


def field_html(f):
    kind=f.get('type','textarea');required=' required' if f.get('required') else ''
    attrs=f'data-input="{esc(f["key"])}" name="{esc(f["key"])}" placeholder="{esc(f.get("placeholder",""))}"{required}'
    default=str(f.get('default',''))
    if kind=='select':
        options=['<option value="">暂不设定</option>']
        for item in f['options']:
            value=str(item.get('value',item.get('label',''))) if isinstance(item,dict) else str(item)
            label=str(item.get('label',value)) if isinstance(item,dict) else str(item)
            options.append(f'<option value="{esc(value)}"'+(' selected' if value==default else '')+f'>{esc(label)}</option>')
        control=f'<select {attrs}>'+''.join(options)+'</select>'
    elif kind=='textarea':control=f'<textarea {attrs} rows="3">{esc(default)}</textarea>'
    else:control=f'<input type="{kind}" {attrs} value="{esc(default)}">'
    hint=f'<small>{esc(f["hint"])}</small>' if f.get('hint') else ''
    return f'<label class="cs-field{" cs-wide" if f.get("wide") else ""}"><span class="cs-label-text">{esc(f["label"])}'+('<span class="cs-required">必填</span>' if f.get('required') else '')+'</span>'+control+hint+'</label>'


def qa_plan(cfg):
    fields=[]
    for i,f in enumerate(cfg['fields']):
        item={'selector':'[data-input="'+f['key']+'"]','value':'测试资料'+str(i),'updatedValue':'更新资料'+str(i)}
        if f.get('type')=='number':item.update(value='27',updatedValue='28')
        if f.get('type')=='select':
            values=[str(v.get('value',v.get('label',''))) if isinstance(v,dict) else str(v) for v in f['options']]
            item.update(type='select',value=values[0],updatedValue=values[-1])
        fields.append(item)
    return {'version':1,'page':'引导页_本地预览.html','paste':'引导页_直接粘贴.txt','fields':fields,'generate':'[data-generate]','result':'[data-output]','copy':'[data-copy]','status':'[data-feedback]','details':'.cs-person'}


def build(cfg, compatibility=False):
    validate(cfg)
    css=(ASSETS/'guide.css').read_text(encoding='utf-8')
    js=(ASSETS/'guide.js').read_text(encoding='utf-8')
    title=esc(cfg['title']);theme=cfg.get('theme','rose-letter')
    background=cfg.get('background','')
    cover=f'<img class="cs-cover" src="{esc(background)}" alt="作品背景"><div class="cs-veil"></div>' if background else ''
    badges=''.join('<span>'+esc(t)+'</span>' for t in cfg.get('badges',['人物自定义','多种开局','故事由你续写']))
    quote=esc(cfg.get('quote',cfg['subtitle']))
    hero=f'''<div class="cs-masthead"><span><span class="cs-seal">{title[0]}</span>{esc(cfg.get('kicker','写下名字，故事由此开始'))}</span><span class="cs-edition">{esc(cfg.get('edition','入场手记 · VOL. 01'))}</span>{button("暂停动效", "data-motion aria-pressed=false", True)}</div><header class="cs-hero">{cover}<div class="cs-orbit" aria-hidden="true"></div><i class="cs-fleck" aria-hidden="true"></i><i class="cs-fleck" aria-hidden="true"></i><i class="cs-fleck" aria-hidden="true"></i><div class="cs-title-block"><span class="cs-eyebrow">{esc(cfg.get('eyebrow','A STORY WAITING FOR YOU'))}</span><h1>{title}</h1><p class="cs-subtitle">{esc(cfg['subtitle'])}</p><div class="cs-badges">{badges}</div>{button('建立我的角色 <span aria-hidden="true">→</span>','data-go="2"')}</div><aside class="cs-letter"><span class="cs-eyebrow">{esc(cfg.get('letter_label','写给即将入场的你'))}</span><blockquote>{quote}</blockquote><footer>{esc(cfg.get('letter_footer','此刻落笔 · 后来皆有回声'))}</footer></aside></header>'''
    nav='<nav class="cs-nav" aria-label="引导页分区">'+''.join(f'<button type="button" data-js-button disabled data-tab="{i}" aria-pressed="false"><span>0{i+1}</span>{name}</button>' for i,name in enumerate(('故事卷首','人物来信','写下人设','带入故事')))+'</nav>'
    def heading(n,en,text,lead=''):
        return f'<div class="cs-section-head"><div><span class="cs-eyebrow">{en}</span><h2>{text}</h2>'+('<p class="cs-muted">'+esc(lead)+'</p>' if lead else '')+f'</div><span class="cs-page-number" aria-hidden="true">0{n}</span></div>'
    features=cfg.get('features',[{'title':'成为故事里的人','text':'填写身份与经历，明确哪些是已经发生的事实。'},{'title':'关系有自己的来路','text':'相识、旧友或重逢，分别承接你设定的基础。'},{'title':'选择不同的第一幕','text':'选定入口后汇总资料，复制消息即可开始。'}])
    feature_html='<div class="cs-features">'+''.join(f'<article class="cs-feature"><small>0{i+1}</small><b>{esc(f["title"])}</b><p>{esc(f["text"])}</p></article>' for i,f in enumerate(features))+'</div>'
    panel0='<section class="cs-panel" role="region" data-panel="0">'+heading(1,'BEFORE THE FIRST PAGE','故事，始于一个选择')+f'<div class="cs-intro-layout"><aside class="cs-side-note"><span class="cs-eyebrow">你将如何入场</span><p>{esc(cfg.get("entry_note",cfg["play"]))}</p></aside><div class="cs-prose">{paragraphs(cfg["world"])}</div></div>'+feature_html+'<p class="cs-muted">'+esc(cfg['play'])+'</p><div class="cs-actions">'+button('认识故事里的人 →','data-go="1"')+'</div></section>'
    people=''
    for i,c in enumerate(cfg['characters']):
        description=''.join(f'<dt>{label}</dt><dd>{esc(c[key])}</dd>' for key,label in [('appearance','01 / 外貌与气质'),('history','02 / 经历与当下'),('personality','03 / 性格与相处'),('relationship','04 / 与你的关系')])
        people+=f'<details class="cs-person"><summary><span class="cs-monogram">{esc(c["name"][0])}</span><span><span class="cs-person-name">{esc(c["name"])}</span><span class="cs-role">{esc(c["role"])}</span></span></summary><div class="cs-person-body"><dl>{description}</dl></div></details>'
    panel1='<section class="cs-panel" role="region" data-panel="1">'+heading(2,'THE PEOPLE YOU WILL MEET','每一个名字，都有来处','展开人物卡，了解他们的经历、性格与关系。')+f'<div class="cs-cast-grid">{people}</div><div class="cs-actions">'+button('写下我的人设 →','data-go="2"')+'</div></section>'
    groups={}
    for f in cfg['fields']:groups.setdefault(f.get('group','角色资料'),[]).append(f)
    fieldsets=''.join(f'<fieldset class="cs-fieldset"><legend>{esc(group)}</legend><div class="cs-fields">'+''.join(field_html(f) for f in fields)+'</div></fieldset>' for group,fields in groups.items())
    extra=''
    if cfg.get('custom_people'):
        extra_fields=''.join(f'<label class="cs-field"><span class="cs-label-text">{label}</span><'+('textarea' if key in ('traits','history','relationship') else 'input')+f' data-person-field="{key}" data-label="{label}"'+(' rows="3"></textarea>' if key in ('traits','history','relationship') else ' type="text">')+'</label>' for key,label in [('name','姓名'),('age','年龄'),('identity','身份'),('traits','外貌与性格'),('history','经历'),('relationship','与你及他人的关系')])
        extra='<div class="cs-extra-head"><h3>补充人物 <small class="cs-role" data-extra-count>0 位</small></h3>'+button('＋ 添加人物','data-add-person',True)+'</div><div data-people-list></div><template data-person-template><section class="cs-person-editor" data-extra-person><div class="cs-editor-head"><h3>补充人物 <span data-person-number></span></h3><button type="button" class="cs-remove" data-remove-person>移除此人</button></div><div class="cs-fields">'+extra_fields+'</div></section></template>'
    fixed=''.join('<p>'+esc(line)+'</p>' for line in cfg.get('fixed_notes',[]))
    panel2='<section class="cs-panel" role="region" data-panel="2">'+heading(3,'WRITE YOUR OWN CHARACTER','把你，写进这一页','每项独立填写。没有标注必填的项目，可以留空。')+'<div class="cs-form-layout"><div>'+fieldsets+extra+'</div><aside class="cs-form-note"><span class="cs-eyebrow">PERSONAL NOTES</span><h3>你的入场资料</h3><div class="cs-completion" data-completion>0 / 0</div><div class="cs-progress"><i data-progress></i></div><p>这一页填写身份和经历，下方选择开局并汇总。填写比例仅作提示，不要求填满。</p>'+fixed+'</aside></div><div class="cs-actions">'+button('选择开局并汇总 →','data-go="3"')+'</div></section>'
    openings=''.join(f'<label class="cs-opening"><span><input type="radio" name="cs-opening" data-opening value="{i}"'+(' checked' if i==0 else '')+f'><strong>{esc(o["title"])}</strong></span><p>{esc(o["text"])}</p></label>' for i,o in enumerate(cfg['openings']))
    panel3='<section class="cs-panel" role="region" data-panel="3">'+heading(4,'LET THE STORY BEGIN','为故事，落下第一笔','选择一个开局，将刚才填写的资料汇总为一条完整消息。')+f'<div class="cs-opening-grid">{openings}</div><div class="cs-output-box"><div class="cs-output-top"><h3>你的开局信笺</h3><span class="cs-counter" data-output-count>0 字符</span></div><label class="cs-field"><span class="cs-label-text">生成结果 · 可继续编辑</span><textarea class="cs-output" data-output placeholder="点击下方“汇总我的开局”，这里会生成可直接发送的完整消息。"></textarea></label><div class="cs-actions">'+button('汇总我的开局','data-generate')+button('复制开局','data-copy',True)+'<button type="button" class="cs-button cs-text" data-js-button disabled data-reset>清空重填</button></div><p class="cs-feedback" data-feedback aria-live="polite" role="status"></p></div><div class="cs-actions">'+button('← 返回修改人设','data-go="2"',True)+'</div></section>'
    runtime='<p class="cs-runtime-note" data-runtime-note>此环境尚未启用交互脚本，生成和复制按钮暂不可用。完整交互需要在允许脚本的页面中运行。</p>'
    config=json.dumps(cfg,ensure_ascii=False).replace('<','\\u003c').replace('>','\\u003e').replace('&','\\u0026')
    component=f'<section class="cs-guide" data-theme="{theme}" data-interactive="true">{hero}{nav}{runtime}<form autocomplete="off">{panel0}{panel1}{panel2}{panel3}</form><footer class="cs-footer">{esc(cfg.get("footer","写下已发生的事，把尚未到来的故事留给相遇。"))}</footer><script type="application/json" data-config>{config}</script></section>'
    fragment='<style>'+css+'</style>'+component+'<script>'+js+'</script>'
    preview='<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+title+' · 完整引导页</title><style>body{margin:0;padding:22px 12px;background:#ece6df} @media(max-width:600px){body{padding:8px 5px}}</style></head><body>'+fragment+'</body></html>'
    outputs={'引导页_直接粘贴.txt':preview,'引导页_本地预览.html':preview,'cardqa.plan.json':json.dumps(qa_plan(cfg),ensure_ascii=False,indent=2)}
    if compatibility:
        plain='【本局开局资料】\n开局：\n'+'\n'.join(f['label']+'：' for f in cfg['fields'])
        static=f'<style>{css}</style><section class="cs-guide" data-theme="{theme}"><div class="cs-panel"><span class="cs-eyebrow">兼容展示版 · 无自动生成/复制</span><h1>{title}</h1><p>{esc(cfg["subtitle"])}</p>{paragraphs(cfg["world"])}<div class="cs-cast-grid">{people}</div><h2>自定义资料</h2>{fieldsets}<div class="cs-compatible"><p>此版仅作兼容展示，不能自动汇总输入。完整功能见交互版；需要手动开局时可复制下方模板填写。</p><pre>{esc(plain)}</pre></div></div></section>'
        outputs['引导页_兼容展示版.html']=static
    return outputs


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('config');p.add_argument('--out',required=True);p.add_argument('--compatibility',action='store_true',help='Also produce explicitly limited static display, only when requested/needed');a=p.parse_args()
    cfg=json.loads(Path(a.config).read_text(encoding='utf-8-sig'));out=Path(a.out)
    outputs=build(cfg,a.compatibility)
    collisions=[str(out/name) for name in outputs if (out/name).exists()]
    if collisions:raise SystemExit('Back up existing output or choose another directory: '+', '.join(collisions))
    out.mkdir(parents=True,exist_ok=True)
    for name,content in outputs.items():(out/name).write_text(content,encoding='utf-8')
    from check_guide_delivery import check_delivery
    errors=check_delivery(out)
    if errors:raise SystemExit('交付检查失败：'+'；'.join(errors))
    print('引导页已生成；请向用户交付下面两份成品，而不是输入的JSON配置：')
    print('完整代码，复制到引导页 HTML：'+str(out/'引导页_直接粘贴.txt'))
    print('打开浏览器预览：'+str(out/'引导页_本地预览.html'))
    print('平台保存后的交互兼容性尚未验证，需按实际测试结果说明。')
