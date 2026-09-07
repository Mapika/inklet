"""Prepare the pinned Natural Earth country example, with source verification."""
import argparse
import csv
import hashlib
import io
import json
from pathlib import Path
from urllib.request import urlopen

REVISION='9380cca83db5f9aef52d5e762765100745f84b27'
URL=f'https://raw.githubusercontent.com/nvkelso/natural-earth-vector/{REVISION}/geojson/ne_110m_admin_0_countries.geojson'
SHA256='6866c877d39cba9c357620878839b336d569f8c662d3cfab4cb1dbe2d39c977f'
OUTPUT=Path(__file__).resolve().parents[1]/'examples/v4/data'


def prepare(raw):
    if hashlib.sha256(raw).hexdigest()!=SHA256: raise ValueError('Natural Earth source checksum mismatch')
    source=json.loads(raw)
    # This older export declares CRS84: the longitude/latitude order already
    # required by GeoJSON. Remove that legacy field only after checking it.
    if source.get('crs',{}).get('properties',{}).get('name')!='urn:ogc:def:crs:OGC:1.3:CRS84':
        raise ValueError('unexpected source CRS; cannot normalize it implicitly')
    features=[];rows=[]
    for feature in source['features']:
        p=feature['properties'];key=p['ADM0_A3']
        if key=='ATA':continue  # Not a population comparison; its polar ring also crosses ±180.
        features.append(dict(type='Feature',id=key,properties={},geometry=feature['geometry']))
        population=p['POP_EST']
        if population is None or population<0: population=None
        rows.append(dict(id=key,country=p['ADMIN'],continent=p['CONTINENT'],
                         population=population,population_year=p['POP_YEAR'],
                         population_millions=population/1e6 if population is not None else None))
    # Stable code order controls table navigation and boundary overlap ties.
    features.sort(key=lambda f:f['id']);rows.sort(key=lambda r:r['id'])
    text=json.dumps(dict(type='FeatureCollection',features=features),separators=(',',':'),ensure_ascii=False)+'\n'
    stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=list(rows[0]),lineterminator='\n')
    writer.writeheader();writer.writerows(rows)
    files={'world-countries.geojson':text.encode(),'world-population.csv':stream.getvalue().encode()}
    manifest=dict(dataset='Natural Earth Admin 0 countries, 1:110m',source_url=URL,source_revision=REVISION,
        source_sha256=SHA256,license='Public domain',license_url='https://www.naturalearthdata.com/about/terms-of-use/',
        credit='Made with Natural Earth',retrieved='2026-09-08',source_features=len(source['features']),features=len(features),
        transformations=['Remove verified legacy CRS84 declaration; retain longitude/latitude coordinates unchanged.',
            'Exclude Antarctica (ATA); retain the other 176 source country/map units.',
            'Set feature IDs from ADM0_A3; sort by that source code. These are Natural Earth codes, not a guaranteed ISO list.',
            'Copy ADMIN, CONTINENT, POP_EST and POP_YEAR to CSV. Derive population_millions as POP_EST / 1000000.',
            'Strip unused GeoJSON properties; retain all polygon parts and holes without simplifying coordinates.'],
        population_year_counts={str(y):sum(r['population_year']==y for r in rows) for y in sorted({r['population_year'] for r in rows})},
        files={name:hashlib.sha256(data).hexdigest() for name,data in files.items()})
    files['world-map-source.json']=(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n').encode()
    return files


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,help='Use a local copy of the pinned source instead of downloading')
    parser.add_argument('--check',action='store_true',help='Compare prepared bytes with the committed inputs')
    args=parser.parse_args()
    if args.source:raw=args.source.read_bytes()
    else:
        with urlopen(URL,timeout=60) as response:raw=response.read()
    for name,data in prepare(raw).items():
        path=OUTPUT/name
        if args.check:
            if path.read_bytes()!=data: raise ValueError(f'prepared file differs: {name}')
        else:OUTPUT.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    print('Verified Natural Earth inputs' if args.check else 'Prepared Natural Earth inputs')


if __name__=='__main__':main()
