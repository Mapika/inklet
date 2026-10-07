"""Write docs/llms-full.txt from the packaged agent guide.

    python tools/gen_llms.py          # write
    python tools/gen_llms.py --check  # exit 1 if the file is out of date

`llms-full.txt` is `inklet guide --api` for agents that read documentation
from the web; generating it keeps it identical to what the CLI prints.
"""
from __future__ import annotations

import sys
from pathlib import Path

from inklet.agent import guide

TARGET = Path(__file__).resolve().parent.parent / 'docs' / 'llms-full.txt'


def main(argv):
    text = guide(api=True)
    if '--check' in argv:
        current = TARGET.read_text(encoding='utf-8') if TARGET.exists() else ''
        if current != text:
            print(f'{TARGET} is out of date; run python tools/gen_llms.py')
            return 1
        return 0
    TARGET.write_text(text, encoding='utf-8')
    print(f'wrote {TARGET}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
