# -*- coding: utf-8 -*-
import urllib.request, re, json
req = urllib.request.Request('https://fengye-image.netlify.app/', headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req, timeout=15) as resp:
    html = resp.read().decode('utf-8')
match = re.search(r'let dyData = (\{[\s\S]*?\n  \});', html)
if match:
    data = json.loads(match.group(1))
    print('keyword:', data.get('keyword'))
    print('updatedAt:', data.get('updatedAt'))
    print('videos count:', len(data.get('videos', [])))
    for i, v in enumerate(data.get('videos', [])[:5]):
        print('  [%d] %s | %s' % (i+1, v['title'][:40], v['url'][:60]))
else:
    print('dyData not found')
    match2 = re.search(r'let dyData = (\{[\s\S]*?\});', html)
    if match2:
        print('Broad match, length:', len(match2.group(1)))
        print(match2.group(1)[:200])
