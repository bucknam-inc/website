#!/usr/bin/env python3
"""Second-pass scrub of extracted markdown content:
   - Remove Drupal admin/comment links (`[__Admin](xxx.html#)`, `[__0 comments]`)
   - Strip related-post nav blocks at bottom of blog posts (siblings linked to *.html)
   - Remove leading H2 that duplicates the page title
   - Remove stray `__` underscores left over from Drupal icon-font placeholders
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / 'src' / 'content'

def scrub(text, slug):
    # 1. Drupal admin/comment artifacts at top of nodes: `[__Admin](349.html#) __[__0 comments](349.html#)`
    text = re.sub(r'^\s*\[__[^\]]*\]\([^)]+\)\s*(?:__)?\s*\[__\d+\s+comments?\]\([^)]+\)\s*\n+', '',
                  text, flags=re.M)
    # 2. Related-post nav block at bottom: two consecutive `[ __ ... .html)` links
    text = re.sub(r'\n\[\s*__[\s\S]+?\.html[\)\s\S]*$', '\n', text)
    # 3. Leading H2 that duplicates the page title (case-insensitive, after frontmatter)
    #    We only strip when the heading text itself (not the frontmatter) contains the slug words.
    title_from_slug = slug.replace('-', ' ').lower()
    def maybe_drop_h2(m):
        frontmatter, heading = m.group(1), m.group(2)
        return frontmatter if title_from_slug in heading.lower() else m.group(0)
    text = re.sub(r'(^---\n.*?\n---\n+)##\s+([^\n]+)\n+',
                  maybe_drop_h2, text, count=1, flags=re.S)
    # 4. Stray `__` placeholders from Drupal icon fonts
    text = re.sub(r'(^|\n)__\s*\n', r'\1', text)
    text = re.sub(r'^\s*__\s*$', '', text, flags=re.M)
    # 5. Collapse excess blank lines
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip() + '\n'

for md in sorted(CONTENT.rglob('*.md')):
    slug = md.stem
    orig = md.read_text()
    new = scrub(orig, slug)
    if new != orig:
        md.write_text(new)
        print(f'  scrubbed {md.relative_to(ROOT)}')
