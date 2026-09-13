"""Pinned public connectome inputs for original Inklet gallery figures.

No paper image, manually transcribed chart, or earlier plotted coordinates are
read. The legacy acquisition adapter supplies registration and source caching
only. All numerical plots below are newly derived from released tables/SWCs.
"""
from pathlib import Path
import json,sys
import numpy as np
import pandas as pd
import inklet as i

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'examples/inspo'))
from anatomy import Anatomy

GROUPS=['ORN_DA1','ORN_VA1v','ORN_VA1d','ORN_DL3','DA1_lPN','MZ_lv2PN']
COLORS=['#087f8c','#e58f29','#8055a5','#3b73b9','#b9647e','#659451']

class Data:
    def __init__(self,path,output):
        self.path=Path(path);self.output=Path(output);self.output.mkdir(parents=True,exist_ok=True)
        self.anatomy=Anatomy(self.path);a=self.anatomy
        self.annotations=pd.read_feather(self.path/'annotations.feather')
        self.communities=pd.read_feather(self.path/'communities.feather').sort_values('community_id')
        edges=pd.read_feather(self.path/'edges.feather');self.edges=edges
        subset=edges[edges.pre.isin(GROUPS[:4])]
        self.partners=subset.groupby('post').weight_m.sum().nlargest(18).index.tolist()
        self.olfactory_weights=subset.groupby(['pre','post']).weight_m.sum().unstack(fill_value=0).reindex(index=GROUPS[:4],columns=self.partners).fillna(0).to_numpy()
        membership={t:int(row.community_id) for row in self.communities.itertuples() for t in row.types}
        pre=edges.pre.map(membership).fillna(-1).to_numpy(int);post=edges.post.map(membership).fillna(-1).to_numpy(int)
        valid=(pre>=0)&(post>=0);self.matrix=np.zeros((len(self.communities),len(self.communities)))
        np.add.at(self.matrix,(pre[valid],post[valid]),edges.weight_m.to_numpy()[valid])
        self.sizes=np.array([len(v) for v in self.communities.types])
        self.strength_out=self.matrix.sum(1);self.strength_in=self.matrix.sum(0)
        self.top=np.argsort(-(self.strength_out+self.strength_in),kind='stable')[:12]
        self.female=pd.read_csv(self.path/'female-annotations.tsv',sep='\t',low_memory=False)
        m=self.annotations.loc[self.annotations.type.str.startswith('ORN_',na=False)].groupby('type').size()
        f=self.female.loc[self.female.cell_type.str.startswith('ORN_',na=False)].groupby('cell_type').size()
        assert set(m.index)==set(f.index)
        self.orn=[{'type':key,'male':int(m[key]),'female':int(f[key])} for key in sorted(m.index,key=lambda k:(-int(m[k]+f[k]),k))]
        self.ids={g:a.ids(g) for g in GROUPS}
        self.lines={};self.points={};self.tree_stats=[]
        for group in GROUPS:
            self.lines[group],self.points[group]=self.skeletons(self.ids[group])
            for body in self.ids[group]:
                xyz,index,parents=a.skeleton(body)
                counts=pd.Series(parents[np.isin(parents,index)]).value_counts();branch=int((counts>1).sum())
                self.tree_stats.append({'group':group,'body_id':int(body),'nodes':len(index),'branch_nodes':branch,'tips':int(sum(int(v) not in counts for v in index)),'span':np.ptp(xyz,axis=0).tolist()})
        self.lines['LH008m'],self.points['LH008m']=self.skeletons(a.ids('LH008m'))
        from fly_data import download
        from concurrent.futures import ThreadPoolExecutor
        self.community_ids={int(k):sorted(map(int,self.communities.iloc[k].bodyId))[:16] for k in self.top[:6]}
        requests=[(a.manifest['skeleton_base']+str(body)+'.swc',self.path/'skeletons'/f'{body}.swc') for ids in self.community_ids.values() for body in ids]
        with ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(lambda pair:download(*pair),requests))
        self.community_arbors={k:self.skeletons(ids) for k,ids in self.community_ids.items()}
        self.cluster_ids=a.ids('cluster-102')
        self.cluster_lines,self.cluster_points=self.skeletons(self.cluster_ids)
        self.brain=a.display_mesh('male-brain',4500);self.vnc=a.display_mesh('male-vnc',2500)
        self.rois={name:a.display_mesh('roi-'+name,650) for name in ['AL-L','AL-R','LH-L','LH-R']}
        from synapses import sample_records
        (self.output/'source-cache').mkdir(exist_ok=True)
        syn=sample_records(self.path,self.output/'source-cache')
        self.al_xyz=a.warp(syn['xyz_nm']);self.al_type=syn['type']
        # Front is x/y in the provided registered plotting coordinates.
        self.camera=a.camera(a.frame((0,0,1,1)))
        self.dorsal=a.camera(a.frame((0,0,1,1),view='dorsal'),view='dorsal')
        self.provenance={
            'purpose':'Original exploratory Inklet documentation examples; not a recreation or statistical reanalysis of a published figure.',
            'sources':{'MaleCNS':'https://male-cns.janelia.org/download/','tables':'https://github.com/flyconnectome/2025malecns/tree/67767d2233657983993ff6c2be48e836a935863c','FlyWire annotations':'https://github.com/flyconnectome/flywire_annotations/tree/8587524c1748ce5ef2080822a2fc890fc03bf597'},
            'licenses':{'MaleCNS':'CC BY 4.0','FlyWire':'CC BY-NC 4.0','template repository':'GPL-3.0; see original template attribution'},
            'coordinates':'Public registered plotting space; all meshes and paths transformed together. No physical length inference from registration.',
            'counts':'Bilateral counts of all annotated ORN_ types, including unknown sides. All 53 types shown, ranked by combined male/female count.',
            'skeleton_selection':self.ids,'skeleton_selection_rule':'All cached body IDs in each named source-manifest group. This is a deterministic convenience sample, not a random or representative sample.', 'input_manifest':a.manifest,'skeleton_metrics':'Count of SWC sample nodes, branch nodes (>1 children), and tips; these depend on reconstruction sampling, not synapse counts.',
            'synapses':'Deterministic spatial-index sample from levels 3–5 (see source-cache/synapse-sampling.json); annotation records, not unique sites or whole-brain totals.',
            'communities':'Released final memberships; weights aggregate weight_m over matched types. Top 24 by incoming + outgoing aggregate weight, including within-community weights.',
            'included_weight':float(edges.weight_m.to_numpy()[valid].sum()),'omitted_weight':float(edges.weight_m.to_numpy()[~valid].sum()),
            'matrix_edge_rows':int(valid.sum()),'unmapped_edge_rows':int((~valid).sum()),'communities_count':len(self.sizes),
            'community_anatomy_selection':self.community_ids,'community_anatomy_rule':'First 16 sorted body IDs per community among the six highest combined strengths; deterministic convenience sample.',
            'cluster_102':'All 255 cached released members; visualization only.',
            'figure_panels':{'olfactory':15,'communities':17},'arbor_count':len(self.tree_stats),'zero_branch_arbors':sum(r['branch_nodes']==0 for r in self.tree_stats),
            'limitations':['Curated anatomy samples; approximate display mesh simplification.','X-ray paths are not surface-occluded; degree-two chains simplified in 3D at 0.35 registered-coordinate units, keeping branch/tip endpoints.','No hypothesis tests or inferred intermediate hierarchy.','Matrix and graph show community aggregates, not individual synapses or neuron-type edges.']}
        (self.output/'provenance.json').write_text(json.dumps(self.provenance,indent=2))
        (self.output/'orn-counts.json').write_text(json.dumps(self.orn,indent=2))
        (self.output/'skeleton-metrics.json').write_text(json.dumps(self.tree_stats,indent=2))
        np.savez_compressed(self.output/'measurements.npz',matrix=self.matrix,community_sizes=self.sizes,top=np.argsort(-(self.strength_in+self.strength_out),kind="stable")[:24],order=np.argsort(-(self.strength_in+self.strength_out),kind="stable"),al_xyz=self.al_xyz,al_type=self.al_type,olfactory_weights=self.olfactory_weights)

    def skeletons(self,ids):
        lines=[];points=[]
        for body in ids:
            xyz,index,parents=self.anatomy.skeleton(body);lookup={int(value):k for k,value in enumerate(index)}
            points.extend(xyz)
            # Simplify within degree-two chains in 3D, retaining every branch/tip.
            children=np.zeros(len(index),dtype=int)
            for parent in parents:
                if int(parent) in lookup:children[lookup[int(parent)]]+=1
            for start in np.flatnonzero(children!=1):
                chain=[xyz[start]];current=start
                while int(parents[current]) in lookup:
                    current=lookup[int(parents[current])];chain.append(xyz[current])
                    if children[current]!=1:break
                if len(chain)>1:lines.append(simplify(np.asarray(chain),.35))
        return lines,np.asarray(points)


def simplify(points,tolerance):
    """3D Ramer–Douglas–Peucker, keeping chain endpoints exactly."""
    keep={0,len(points)-1};pending=[(0,len(points)-1)]
    while pending:
        a,b=pending.pop()
        if b-a<2:continue
        segment=points[b]-points[a];square=segment@segment;v=points[a+1:b]-points[a]
        t=np.clip(v@segment/square,0,1) if square else np.zeros(len(v))
        distances=np.linalg.norm(v-t[:,None]*segment,axis=1);k=int(np.argmax(distances))
        if distances[k]>tolerance:
            middle=a+1+k;keep.add(middle);pending.extend([(a,middle),(middle,b)])
    return points[sorted(keep)]
