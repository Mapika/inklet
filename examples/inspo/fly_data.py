"""Acquire the real MaleCNS/FlyWire anatomy used by the reference figures.

Data stay in the requested output directory, never in the package. Downloads
are public, resumable by file, and recorded with hashes. No credentials needed.
"""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
from pathlib import Path
import urllib.request
import urllib.parse

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.ipc as ipc

BUCKET = 'https://storage.googleapis.com/flyem-male-cns/'
RELEASE = BUCKET + 'v1.0/'
GITHUB = 'https://raw.githubusercontent.com/'
FLYBRAINS_REF = '273333c8d8bf5adeebebd274e554621462e388bd'
STUDY_REF = '67767d2233657983993ff6c2be48e836a935863c'
ANNOTATIONS_REF = '8587524c1748ce5ef2080822a2fc890fc03bf597'


def download(url, target):
    target = Path(target)
    if target.exists():
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + '.download')
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=90) as source, temporary.open('wb') as out:
                while chunk := source.read(1024 * 1024):
                    out.write(chunk)
            temporary.replace(target)
            return target
        except Exception:
            if attempt == 2:
                raise


def get_mesh(base, identifier, target):
    """Read Neuroglancer legacy meshes (vertices in nm, triangle indices)."""
    target = Path(target)
    if target.exists():
        return target
    with urllib.request.urlopen(base + '/' + str(identifier) + ':0', timeout=90) as source:
        fragments = json.load(source)['fragments']
    vertices, faces = [], []
    offset = 0
    for fragment in fragments:
        with urllib.request.urlopen(base + '/' + urllib.parse.quote(fragment), timeout=90) as source:
            blob = source.read()
        n = int(np.frombuffer(blob, dtype='<u4', count=1)[0])
        v = np.frombuffer(blob, dtype='<f4', count=n*3, offset=4).reshape(-1, 3)
        f = np.frombuffer(blob, dtype='<u4', offset=4+n*12).reshape(-1, 3)
        vertices.append(v.copy()); faces.append(f.copy() + offset)
        offset += n
    np.savez_compressed(target, vertices=np.concatenate(vertices), faces=np.concatenate(faces))
    return target


def prepare(root):
    root = Path(root); root.mkdir(parents=True, exist_ok=True)
    urls = {
        'annotations.feather': RELEASE+'connectome-data/flat-connectome/body-annotations-male-cns-v1.0-minconf-0.5.feather',
        'weights.feather': RELEASE+'connectome-data/flat-connectome/connectome-weights-male-cns-v1.0-minconf-0.5.feather',
        'edges.feather': GITHUB+f'flyconnectome/2025malecns/{STUDY_REF}/supplemental_data/mcns_fw_edge_comp.feather',
        'communities.feather': GITHUB+f'flyconnectome/2025malecns/{STUDY_REF}/supplemental_data/mcns_lvl_6_hsbm_communities.feather',
        'female-annotations.tsv': GITHUB+f'flyconnectome/flywire_annotations/{ANNOTATIONS_REF}/supplemental_files/Supplemental_file1_neuron_annotations.tsv',
        'male-brain.ply': GITHUB+f'navis-org/navis-flybrains/{FLYBRAINS_REF}/flybrains/meshes/JRCFIB2022M_brain.ply',
        'male-vnc.ply': GITHUB+f'navis-org/navis-flybrains/{FLYBRAINS_REF}/flybrains/meshes/JRCFIB2022M_vnc.ply',
        'JRCFIB2022M_plotting_landmarks.csv': GITHUB+f'navis-org/navis-flybrains/{FLYBRAINS_REF}/flybrains/data/JRCFIB2022M_plotting_landmarks.csv',
    }
    for filename, url in urls.items():
        download(url, root/filename)
    a = pd.read_feather(root/'annotations.feather').set_index('bodyId', drop=False)
    f = pd.read_csv(root/'female-annotations.tsv', sep='\t', low_memory=False)
    communities = pd.read_feather(root/'communities.feather')
    groups = {}

    def select(name, mask, limit=None):
        ids = sorted(a.loc[mask, 'bodyId'].astype(int).tolist())
        # Deterministic display subsampling, explicitly recorded in the manifest.
        chosen = ids if limit is None or len(ids) <= limit else [ids[k] for k in np.linspace(0, len(ids)-1, limit).astype(int)]
        groups[name] = dict(ids=chosen, available=len(ids), selection='all' if len(chosen)==len(ids) else 'evenly spaced sorted body IDs')

    for name in ['vpoEN', 'MZ_lv2PN', 'DA1_lPN', 'ORN_DA1', 'ORN_VA1v', 'ORN_VA1d', 'ORN_DL3', 'KCg-s1', 'LH008m', 'aSP10C_a']:
        select(name, a.type.eq(name), 60 if name.startswith('ORN_') else 12)
    # Published names can be represented as synonyms in the current annotations.
    if not groups['aSP10C_a']['ids']:
        select('aSP10C_a', a.synonyms.fillna('').str.contains('aSP10C_a', regex=False), 4)
    if not groups['KCg-s1']['ids']:
        select('KCg-s1', a.type.fillna('').str.startswith('KCg'), 8)
    for name, mask in [
        ('labellar', a['class'].eq('gustatory') & a.subclass.eq('labellar bristle')),
        ('pharyngeal', a['class'].eq('gustatory') & a.subclass.eq('pharyngeal sensillum')),
        ('taste-peg', a['class'].eq('gustatory') & a.subclass.eq('taste peg')),
        ('leg-ascending', a.type.fillna('').str.startswith('LgAG')),
        ('leg-local', a.type.fillna('').str.startswith('LgLG')),
        ('wing', a['class'].eq('gustatory') & a.subclass.eq('wing bristle')),
    ]:
        select(name, mask, 40)
        groups[name]['all_ids'] = sorted(a.loc[mask, 'bodyId'].astype(int).tolist())
    cluster = communities.loc[communities.community_id.eq(102)].iloc[0]
    groups['cluster-102'] = dict(ids=list(map(int, cluster.bodyId)), available=len(cluster.bodyId), selection='all published cluster members')

    # Find actual downstream partners for panel M, using every input GRN in the
    # requested subclass, and the public unthresholded connection table.
    partner_file = root/'gustatory-partners-v2.json'
    if partner_file.exists():
        partner_groups = json.loads(partner_file.read_text())
    else:
        names = ['pharyngeal', 'labellar', 'leg-ascending', 'leg-local', 'wing']
        pre_to_group = {body: n for n in names for body in groups[n]['all_ids']}
        allowed = pa.array(list(pre_to_group), type=pa.int64())
        records = []
        with pa.memory_map(str(root/'weights.feather'), 'r') as source:
            reader = ipc.open_file(source)
            for j in range(reader.num_record_batches):
                batch = reader.get_batch(j)
                filtered = batch.filter(pc.is_in(batch.column('body_pre'), value_set=allowed))
                if filtered.num_rows:
                    records.append(filtered.to_pandas())
        edges = pd.concat(records, ignore_index=True)
        edges['sensory_group'] = edges.body_pre.map(pre_to_group)
        partner_groups = {}
        for name in names:
            totals = edges.loc[edges.sensory_group.eq(name)].groupby('body_post').weight.sum()
            total = int(totals.sum())
            known = a.reindex(totals.index).copy()
            known['input_weight'] = totals
            known['non_isomorphic'] = known.dimorphism.fillna('').str.contains('dimorphic|specific')
            type_weights = known.groupby('type').input_weight.sum()
            for category, flag in [('dimorphic', True), ('isomorphic', False)]:
                chosen = known[known.non_isomorphic.eq(flag) & known.type.notna()].sort_values('input_weight', ascending=False).head(12)
                partner_groups[name+'-'+category] = dict(
                    ids=list(map(int, chosen.bodyId)), available=len(known),
                    selection='12 neurons with largest summed input from all source GRNs in subclass',
                    sensory_total_synapses=total,
                    fractions={str(int(row.bodyId)):float(type_weights[row.type]/total) for row in chosen.itertuples()},
                    individual_fractions={str(int(row.bodyId)):float(row.input_weight/total) for row in chosen.itertuples()},
                    color_encoding='fraction of all sensory-subclass output to the complete target cell type',
                    types={str(int(row.bodyId)):row.type for row in chosen.itertuples()},
                )
        partner_file.write_text(json.dumps(partner_groups, indent=2)+'\n')
    groups.update(partner_groups)

    ids = sorted({body for group in groups.values() for body in group['ids']})
    skeleton_base = RELEASE+'segmentation/skeletons-malecns/skeletons-swc/'
    failures = []
    def fetch(body):
        try:
            download(skeleton_base+str(body)+'.swc', root/'skeletons'/f'{body}.swc')
            return body, None
        except Exception as error:
            return body, str(error)
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
        for n, (body, error) in enumerate(pool.map(fetch, ids), 1):
            if error: failures.append(dict(body_id=body, error=error))
            if n % 100 == 0: print(f'  Skeletons: {n}/{len(ids)}', flush=True)
    if failures:
        raise RuntimeError(f'Could not retrieve required skeletons: {failures}')

    female_groups = {}
    mesh_base = BUCKET+'flywire2mcns_meshes/783'
    for name in ['vpoEN', 'MZ_lv2PN']:
        selected = f[f.cell_type.eq(name) & f.side.eq('right')].root_id.astype('int64').tolist()
        female_groups[name] = selected
        for body in selected:
            get_mesh(mesh_base, body, root/f'female-{body}.npz')
    roi_base = BUCKET+'rois/fullbrain-roi-v4/mesh'
    for name, label in {'AL-L':1, 'AL-R':2, 'CA-L':15, 'CA-R':16, 'LH-L':41, 'LH-R':42, 'GNG':29}.items():
        get_mesh(roi_base, label, root/f'roi-{name}.npz')
    get_mesh(BUCKET+'rois/fullbrain-major-shells/mesh', 1, root/'central-brain.npz')
    selected = a.loc[ids].reset_index(drop=True)
    selected.to_feather(root/'selected-neurons.feather')
    sources = {filename:dict(url=url, sha256=hashlib.file_digest((root/filename).open('rb'), 'sha256').hexdigest()) for filename,url in urls.items()}
    manifest = dict(
        dataset='MaleCNS v1.0; FlyWire v783 mapped to MaleCNS nm space',
        license='CC BY 4.0 (MaleCNS data)', citation='Berg et al., Cell 189, 5504–5526 (2026), doi:10.1016/j.cell.2026.08.015',
        licenses={'MaleCNS':'CC BY 4.0; https://male-cns.janelia.org/download/',
                  'FlyWire':'CC BY-NC 4.0; https://home.flywire.ai/guidelines',
                  'navis-flybrains':'GPL-3.0 repository; mesh and landmark provenance in template metadata'},
        sources=sources, skeleton_base=skeleton_base, skeleton_units='8 nm; multiplied by 8 before registration',
        skeletons={str(body):hashlib.sha256((root/'skeletons'/f'{body}.swc').read_bytes()).hexdigest() for body in ids},
        groups=groups, female_groups=female_groups, female_mesh_base=mesh_base, roi_mesh_base=roi_base,
        central_brain_mesh=BUCKET+'rois/fullbrain-major-shells/mesh/1:0',
        note='Published cluster 102 is complete. Other large anatomical groups are display subsets; see each selection. GRN partners are recomputed from release data, not asserted to be the exact neurons shown by the authors.',
    )
    (root/'manifest.json').write_text(json.dumps(manifest, indent=2)+'\n')
    return manifest


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, default=Path('out/inspo-recreated/data'))
    args = parser.parse_args()
    manifest = prepare(args.data)
    print(f"Prepared {len(manifest['skeletons'])} real neurons.")
