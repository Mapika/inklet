"""Verify gallery measurements and the saved vector/layout contracts."""
from pathlib import Path
import argparse,json,sys
import numpy as np
import pandas as pd
from data import ROOT


def verify(data,output):
    metrics=json.loads((output/'skeleton-metrics.json').read_text())
    assert len(metrics)==254
    zero=0
    for row in metrics:
        raw=np.loadtxt(data/'skeletons'/f"{row['body_id']}.swc",comments='#',ndmin=2)
        ids=raw[:,0].astype(int);parents=raw[:,6].astype(int)
        valid=parents[np.isin(parents,ids)];counts=pd.Series(valid).value_counts()
        branches=int((counts>1).sum());tips=int(sum(int(v) not in counts for v in ids))
        assert row['nodes']==len(ids) and row['branch_nodes']==branches and row['tips']==tips
        zero+=branches==0
    assert zero==17
    values=np.load(output/'measurements.npz');matrix=values['matrix'];top=values['top'];order=values['order']
    assert matrix.shape==(311,311) and np.isfinite(matrix).all() and (matrix>=0).all()
    assert len(set(order))==311 and len(top)==24 and np.array_equal(top,order[:24])
    assert values['community_sizes'].sum()==8231
    weights=values['olfactory_weights'];fractions=weights/weights.sum(1,keepdims=True)
    assert weights.shape==(4,18) and (weights>=0).all() and np.allclose(fractions.sum(1),1)
    assert (fractions<=1).all()
    counts=json.loads((output/'orn-counts.json').read_text());assert len(counts)==len({r['type'] for r in counts})==53
    a,b=np.triu_indices(311,1);reciprocal=int(((matrix[a,b]>0)&(matrix[b,a]>0)).sum());assert reciprocal==23497
    sample=json.loads((output/'source-cache/synapse-sampling.json').read_text());assert sample['records']==756 and sample['unique_coordinate_type_tuples']==742
    records=json.loads((output/'validation.json').read_text());assert {r['name'] for r in records}=={'olfactory','communities'}
    for record in records:
        assert len(record['panels'])=={'olfactory':15,'communities':17}[record['name']]
        svg=(output/(record['name']+'.svg')).read_text();assert '<image' not in svg
        assert svg.count('<text')==record['native_text_elements'] and record['native_text_elements']>180
        for row in record['panels'].values():
            a,b=row['slot'],row['content'];assert a[0]<=b[0]<=b[2]<=a[2]+1e-5 and a[1]<=b[1]<=b[3]<=a[3]+1e-5
    report={'source_skeleton_metrics':'254 verified against raw SWCs','zero_branch_arbors_preserved':zero,'ORN_types':53,'communities':311,'member_types':8231,'reciprocal_pairs':reciprocal,'local_annotation_records':756,'unique_coordinate_type_tuples':742,'allocation_normalization':'within 18 shown targets; range [0,1]','layout':'15 + 17 named panels fit without scaling type','embedded_images':0,'render':'SVG/PDF editable text; PNG preview','limitations':'No hypothesis tests; deterministic anatomy samples; X-ray paths; upstream license terms apply.'}
    (output/'verification.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--data',type=Path,default=ROOT/'out/inspo-recreated/data');parser.add_argument('--output',type=Path,default=ROOT/'out/scientific-gallery');args=parser.parse_args();verify(args.data,args.output)
