# -*- coding: utf-8 -*-
import io
from html.parser import HTMLParser

p = r'C:/Users/Administrator/Doubao/chats/2026-08-31/new-chat-1/fengye-image-site/index.html'
data = io.open(p, encoding='utf-8').read()

VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}

class P(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.errors = []
    def handle_starttag(self, tag, attrs):
        if tag not in VOID:
            self.stack.append((tag, self.getpos()))
    def handle_endtag(self, tag):
        if tag in VOID:
            return
        if not self.stack:
            self.errors.append('extra </%s> at %s' % (tag, self.getpos()))
            return
        open_tag, pos = self.stack.pop()
        if open_tag != tag:
            self.errors.append('mismatch: <%s> at %s closed by </%s> at %s' % (open_tag, pos, tag, self.getpos()))

p2 = P()
p2.feed(data)
print('errors:', p2.errors[:10] if p2.errors else 'NONE')
print('unclosed:', [(t, pos) for t, pos in p2.stack] if p2.stack else 'NONE')

keys = ['id="douyin-panel"', 'id="dy-list"', 'id="dy-keyword"', 'data-panel="douyin"',
        'function renderDy', 'function switchTab', 'function dyEsc']
for k in keys:
    print(k, '->', data.count(k))
