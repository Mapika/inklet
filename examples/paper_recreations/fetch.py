"""Download pinned source data and review images; verify every SHA-256."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import argparse
import hashlib
import json
import urllib.request

HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--references', type=Path,
                        default=HERE.parents[1] / 'out/paper-recreations/references')
    args = parser.parse_args()
    args.references.mkdir(parents=True, exist_ok=True)

    def fetch(item):
        path = args.references / item['filename']
        data = path.read_bytes() if path.exists() else urllib.request.urlopen(
            urllib.request.Request(item['url'], headers={'User-Agent': 'Inklet figure reproduction'}),
            timeout=120).read()
        if hashlib.sha256(data).hexdigest() != item['sha256']:
            raise ValueError(f'Source hash mismatch: {path.name}; inspect upstream changes')
        if not path.exists():
            path.write_bytes(data)
        return path.name

    sources = json.loads((HERE / 'sources.json').read_text())
    with ThreadPoolExecutor(max_workers=4) as pool:
        for name in pool.map(fetch, sources['files']):
            print('Verified', name)


if __name__ == '__main__':
    main()
