"""Build the plain-text handoff from the two canonical Markdown documents.

Run from any working directory: python tools/sync_handoff.py
No provider calls, environment reads, secret values or runtime-data access.
"""
from pathlib import Path
import posixpath
import re

ROOT = Path(__file__).resolve().parents[1]
SOURCES = ('docs/TECHNICAL-HANDOFF.md', 'docs/WORKSPACE-INVENTORY.md')


def plain_text(markdown, source):
    def link(match):
        label, target = match.groups()
        if not target.startswith(('https://', 'http://', '#')):
            target = posixpath.normpath(posixpath.join(posixpath.dirname(source), target))
        return f'{label} ({target})'
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', link, markdown)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.M)
    return re.sub(r'^```[^\n]*\n?', '', text.replace('**', ''), flags=re.M).strip()


def main():
    parts = [plain_text((ROOT / source).read_text(encoding='utf-8'), source) for source in SOURCES]
    text = '\n\n' + ('=' * 76) + '\n\n'
    (ROOT / 'notes.txt').write_text(text.join(parts) + '\n', encoding='utf-8')
    print(f'Updated notes.txt from {len(SOURCES)} canonical documents.')


if __name__ == '__main__':
    main()
