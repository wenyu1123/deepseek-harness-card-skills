"""Check deliverable files, not configuration JSON. Does not verify browser or platform behavior."""
import argparse
import json
from html.parser import HTMLParser
from pathlib import Path

SOURCE = '引导页_直接粘贴.txt'
PREVIEW = '引导页_本地预览.html'


class Markup(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
        self.capture = None
        self.css = []
        self.js = []

    def handle_starttag(self, tag, attrs):
        self.tags.append(tag)
        attrs = dict(attrs)
        if tag == 'style':
            self.capture = 'css'
        elif tag == 'script':
            kind = attrs.get('type', '').lower()
            self.capture = 'js' if kind in ('', 'text/javascript', 'application/javascript', 'module') else None

    def handle_endtag(self, tag):
        if tag in ('style', 'script'):
            self.capture = None

    def handle_data(self, data):
        if self.capture == 'css':
            self.css.append(data)
        elif self.capture == 'js':
            self.js.append(data)


def inspect_html(text, label):
    errors = []
    try:
        json.loads(text)
    except (ValueError, TypeError):
        pass
    else:
        return [label + '是JSON数据，不是HTML成品；不能通过修改后缀代替构建。']
    if text.lstrip().startswith('```'):
        errors.append(label + '包含Markdown代码围栏，请直接保存原始代码。')
    markup = Markup()
    markup.feed(text)
    if not any(tag in markup.tags for tag in ('section', 'div', 'main')):
        errors.append(label + '缺少页面内容结构。')
    if not ''.join(markup.css).strip():
        errors.append(label + '缺少内嵌CSS，代码不完整。')
    if not ''.join(markup.js).strip():
        errors.append(label + '缺少交互代码；配置JSON不等于可执行脚本。')
    if sum(markup.tags.count(tag) for tag in ('input', 'textarea', 'select')) < 3:
        errors.append(label + '缺少独立填写控件。')
    if markup.tags.count('button') < 2:
        errors.append(label + '缺少操作按钮。')
    return errors


def check_delivery(directory, source=SOURCE, preview=PREVIEW):
    directory = Path(directory)
    errors = []
    contents = {}
    for name in (source, preview):
        path = directory / name
        if not path.is_file():
            errors.append('缺少成品：' + str(path))
            continue
        try:
            contents[name] = path.read_text(encoding='utf-8-sig')
        except (UnicodeError, OSError) as exc:
            errors.append('无法读取UTF-8成品：' + str(path) + ' / ' + str(exc))
            continue
        errors.extend(inspect_html(contents[name], name))
    if source in contents and preview in contents:
        if contents[source].strip() not in contents[preview]:
            errors.append('TXT源码与HTML预览不一致；更新后需同步生成，不能交付旧预览。')
        page = Markup()
        page.feed(contents[preview])
        if not all(tag in page.tags for tag in ('html', 'head', 'body')):
            errors.append('预览必须是可直接打开的完整HTML文档。')
    return errors


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory', type=Path)
    parser.add_argument('--source', default=SOURCE)
    parser.add_argument('--preview', default=PREVIEW)
    args = parser.parse_args()
    problems = check_delivery(args.directory, args.source, args.preview)
    if problems:
        print('引导页交付未通过：\n- ' + '\n- '.join(problems))
        raise SystemExit(1)
    print('交付检查通过：完整源码与HTML预览均存在且内容一致。浏览器交互与平台保存需另外验证。')
