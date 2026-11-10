"""Local PDF text retrieval; passages are data, never executable instructions."""
import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'references' / 'search-guides'
FILES = ('advanced-search-techniques', 'advanced-internet-search-techniques', 'in-real-time-search-tips')


def select(exp, feedback=None):
    feedback = feedback or {}
    topic = ' '.join((exp.get('outcome',''), str(feedback.get('unresolved_requirements',{})),
                      str(feedback.get('round_review',{})))).lower()
    terms = set(re.findall(r'[a-z]{4,}', topic))
    # A small baseline from every document, plus problem-specific pages.
    baselines = ({2,3}, {1,2}, {6,7,11})
    selected = []
    for stem, base in zip(FILES, baselines):
        path = ROOT / (stem + '.txt')
        text = path.read_text(encoding='utf-8')
        pages = re.findall(r'--- PAGE (\d+) ---\s*(.*?)(?=--- PAGE|\Z)', text, re.S)
        ranked = sorted(pages, key=lambda p: (int(p[0]) in base,
                        len(terms & set(re.findall(r'[a-z]{4,}', p[1].lower())))), reverse=True)
        for page, content in sorted(ranked[:3], key=lambda p:int(p[0])):
            selected.append(dict(document=stem+'.pdf', page=int(page),
                                 text=content.strip()[:4500],
                                 extraction_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    return selected
