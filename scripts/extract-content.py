#!/usr/bin/env python3
"""Extract Drupal page content into clean markdown for an Astro content collection.
Scrubs contact info (phone + email), drops generic alt-text, fixes image URLs."""
from bs4 import BeautifulSoup
import html2text
import re, os, shutil
from pathlib import Path

MIRROR = Path('/Users/claudeai/Projects/Civic Solutions/bucknam-mirror/bucknam-inc.com')
OUT = Path(__file__).resolve().parent.parent / 'src' / 'content'
PUBLIC_IMG = Path(__file__).resolve().parent.parent / 'public' / 'images'

PAGES = {
    '27':  ('pages', 'about-us',           'About Us'),
    '222': ('pages', 'pavement-management','Pavement Management'),
    '224': ('pages', 'row-inventory',      'ROW Inventory'),
    '293': ('pages', 'gis-services',       'GIS Services'),
    '16':  ('pages', 'gis-as-needed',      'GIS As-Needed Services'),
    '292': ('pages', 'myroads-application','MyRoads Application'),
    '26':  ('jobs',  'available-positions','Available Positions'),
    '349': ('blog',  'roads-under-pressure','Roads Under Pressure'),
    '359': ('blog',  'why-pavement-management-matters',
            'Why Pavement Management Matters: From County Roads to HOA Streets'),
    '18':  ('blog',  'introducing-myroads-app','Introducing MyRoads App'),
}

CONTACT_SCRUB = [
    re.compile(r'\b\d{3}[-.\s]\d{3}[-.\s]\d{4}\b'),
    re.compile(r'\b[\w.+-]+@[\w-]+\.[\w.-]+\b'),
    re.compile(r'Contact\s+us\s+for\s+a[^\n]+', re.I),
    re.compile(r'\[Contact us\]\([^)]+\)[^\n]*', re.I),
    re.compile(r'!\[Alt\]\([^)]+\)', re.I),
]

def clean_img_src(src):
    src = re.sub(r'%3[Ff][^"\')]*$', '', src)
    src = re.sub(r'\?.*$', '', src)
    return src

def copy_image(src):
    PUBLIC_IMG.mkdir(parents=True, exist_ok=True)
    rel = src.lstrip('/')
    for candidate in [MIRROR / rel,
                      MIRROR / 'sites' / 'default' / 'files' / os.path.basename(rel)]:
        if candidate.exists():
            dest = PUBLIC_IMG / candidate.name
            if not dest.exists():
                shutil.copy2(candidate, dest)
            return f'/images/{candidate.name}'
    return f'/images/{os.path.basename(rel)}'

def extract(soup):
    region = soup.find('div', class_='region-content') or soup.find('main') or soup.find('article')
    if not region:
        return ''
    for sel in ['.submitted', '.field-label', '.tabs', '.links', '#comments',
                '.comment-wrapper', '.meta', '#block-system-help', 'h1']:
        for el in region.select(sel): el.decompose()
    for img in region.find_all('img'):
        src = img.get('src') or ''
        if not src or src.startswith('data:'):
            img.decompose(); continue
        img['src'] = copy_image(clean_img_src(src))
        if (img.get('alt') or '').strip().lower() == 'alt':
            img['alt'] = ''
    # Remove empty links
    for a in list(region.find_all('a')):
        if not a.get_text(strip=True) and not a.find('img'):
            a.decompose()
    h = html2text.HTML2Text()
    h.body_width = 0
    h.wrap_links = False
    h.single_line_break = True
    md = h.handle(str(region))
    for pat in CONTACT_SCRUB:
        md = pat.sub('', md)
    # Collapse any h2 from the Drupal page that duplicates the title
    md = re.sub(r'^\s*##\s+[A-Z][^\n]+\n+', '', md, count=1)
    md = re.sub(r'^\s*(Our Approach To|get to know|What is GIS\?|Get It Located|Why\s+[A-Z]\w+)\s*\n+',
                '', md, count=1, flags=re.I)
    md = re.sub(r'\n{3,}', '\n\n', md).strip()
    # Normalize bullets: "•" chars become markdown bullets
    md = re.sub(r'^\s*•\s*', '- ', md, flags=re.M)
    return md

def main():
    for nid, (coll, slug, title) in PAGES.items():
        src = MIRROR / 'node' / f'{nid}.html'
        if not src.exists():
            print('MISSING', src); continue
        soup = BeautifulSoup(src.read_text(), 'lxml')
        body = extract(soup)
        out = OUT / coll / f'{slug}.md'
        out.parent.mkdir(parents=True, exist_ok=True)
        safe = title.replace('"', '\\"')
        out.write_text(f'---\ntitle: "{safe}"\nslug: "{slug}"\nsourceNode: "{nid}"\n---\n\n{body}\n')
        print(f'wrote {coll}/{slug}.md ({len(body)} chars)')

if __name__ == '__main__':
    main()
