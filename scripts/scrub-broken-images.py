#!/usr/bin/env python3
"""Remove markdown + HTML image references whose target file doesn't exist in public/images."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / 'src' / 'content'
IMAGES = ROOT / 'public' / 'images'

def image_exists(ref):
    # Strip any URL-encoded or literal query string
    ref = re.sub(r'%3[Ff].*$', '', ref)
    ref = re.sub(r'\?.*$', '', ref)
    name = ref.rsplit('/', 1)[-1]
    return (IMAGES / name).exists()

# Strip markdown image syntax
md_img = re.compile(r'!\[[^\]]*\]\((/images/[^)]+)\)')
# Strip <img> tags
html_img = re.compile(r'<img\b[^>]*\bsrc=["\'](/images/[^"\']+)["\'][^>]*/?>')

def fix(text):
    def md_sub(m):
        if image_exists(m.group(1)):
            return m.group(0)
        return ''
    def html_sub(m):
        if image_exists(m.group(1)):
            return m.group(0)
        return ''
    text = md_img.sub(md_sub, text)
    text = html_img.sub(html_sub, text)
    # Collapse 3+ blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text

removed = 0
for md in CONTENT.rglob('*.md'):
    orig = md.read_text()
    fixed = fix(orig)
    if orig != fixed:
        md.write_text(fixed)
        # Count removals
        before = len(md_img.findall(orig)) + len(html_img.findall(orig))
        after = len(md_img.findall(fixed)) + len(html_img.findall(fixed))
        print(f'  {md.relative_to(ROOT)}: removed {before - after} broken img refs')
        removed += before - after
print(f'\nTotal broken refs removed: {removed}')
