"""Prepare released numerical data; no reference image is read."""
from pathlib import Path
import json, gzip, urllib.request
import numpy as np
import pandas as pd

SYN='https://storage.googleapis.com/flyem-male-cns/v1.0/male-cns-v1.0-synapses-precomputed/'

def prepare(data,out):
    out.mkdir(exist_ok=True,parents=True)
    target=out/'computed.npz'
    if target.exists():
        result=dict(np.load(target,allow_pickle=False))
        if int(result.get('display_schema',0)) < 2:
            edges=pd.read_feather(data/'edges.feather')
            _noise_summary(result,edges)
            _display_summary(result,edges)
            np.savez_compressed(target,**result)
        orn_counts(data,out)
        return result
    print('Preparing released type connections and spatial synapses',flush=True)
    a=pd.read_feather(data/'annotations.feather').set_index('bodyId')
    e=pd.read_feather(data/'edges.feather')
    c=pd.read_feather(data/'communities.feather').sort_values('community_id')
    result={}
    # Exact cumulative curves from the released matched type table.
    grid=np.geomspace(1,1000,120);result['weight_grid']=grid
    dim=a.groupby('type').dimorphism.first().fillna('')
    codes=dim.map(lambda v:2 if 'specific' in v else 1 if 'dimorphic' in v else 0)
    cat=np.maximum(e.pre.map(codes).fillna(0),e.post.map(codes).fillna(0))
    for k in range(3):
        w=np.sort(e.loc[cat.eq(k),'weight_m'].values);result[f'cdf{k}']=np.searchsorted(w,grid,side='right')
    # The stratified positive/zero display sample is prepared by _display_summary.
    for direction in ['pre','post']:
        total=e.groupby(direction).weight_m.sum();d=e[e.verdict_corr.eq('dimorphic')].groupby(direction).weight_m.sum()
        fraction=d.reindex(total.index,fill_value=0)/total.replace(0,np.nan)
        result['fraction_'+direction]=np.sort(fraction.dropna().values)
    # Aggregate adjacency matrix by the actual 311 published communities.
    mapping={t:int(r.community_id) for r in c.itertuples() for t in r.types}
    pre=e.pre.map(mapping).fillna(-1).astype(int).values;post=e.post.map(mapping).fillna(-1).astype(int).values
    valid=(pre>=0)&(post>=0);matrix=np.zeros((311,311));dm=matrix.copy()
    np.add.at(matrix,(pre[valid],post[valid]),e.weight_m.values[valid])
    valid &= e.verdict_corr.eq('dimorphic').values
    np.add.at(dm,(pre[valid],post[valid]),e.weight_m.values[valid]);result['matrix']=matrix;result['dim_matrix']=dm
    # Cell-type fractions, split by annotation class and fru/dsx expression.
    inp=e.groupby('post').weight_m.sum();outp=e.groupby('pre').weight_m.sum()
    di=e[e.verdict_corr.eq('dimorphic')].groupby('post').weight_m.sum()
    do=e[e.verdict_corr.eq('dimorphic')].groupby('pre').weight_m.sum()
    fraction=pd.concat([di.reindex(inp.index,fill_value=0)/inp.replace(0,np.nan),do.reindex(outp.index,fill_value=0)/outp.replace(0,np.nan)],axis=1).max(axis=1).dropna()
    expression=a.groupby('type').fruDsx.first().notna()
    for flag in [0,1]:
        selected=fraction.index.map(codes).fillna(0).to_numpy()>0
        if flag==0:selected=~selected
        result['type_fraction_'+str(flag)]=np.sort(fraction.values[selected])
        expr=fraction.index.map(expression).fillna(False).to_numpy(dtype=bool)
        result['expr_fraction_'+str(flag)]=np.sort(fraction.values[selected & expr])
    classes=a.groupby('type').superclass.first()
    class_order=['cb_intrinsic','cb_sensory','ascending_neuron','descending_neuron','visual_centrifugal','visual_projection']
    result['community_class']=np.array([class_order.index(v) if v in class_order else 6 for v in [classes.reindex(r.types).dropna().mode().iloc[0] if len(classes.reindex(r.types).dropna()) else 'other' for r in c.itertuples()]])
    # Published neuron-level synapse locations from spatial index level 3.
    shard=data/'synapse-spatial-level3.shard';info=data/'synapse-info.json'
    if not shard.exists():urllib.request.urlretrieve(SYN+'by_spatial_level_3/0.shard',shard)
    if not info.exists():urllib.request.urlretrieve(SYN+'info',info)
    b=shard.read_bytes();idx=np.frombuffer(b[:16],'<u8');z=np.frombuffer(gzip.decompress(b[16+int(idx[0]):16+int(idx[1])]),'<u8').reshape(3,-1)
    dtype=np.dtype({'names':['xyz','postxyz','conf_pre','conf_post','body_pre','body_post','roi'],
                    'formats':[('<f4',3),('<f4',3),'<f4','<f4','<u4','<u4','<i2'],
                    'offsets':[0,12,24,28,40,44,48],'itemsize':64})
    offset=16;chunks=[]
    for gap,size in zip(z[1],z[2]):
        offset+=int(gap);raw=gzip.decompress(b[offset:offset+int(size)]);offset+=int(size)
        n=int.from_bytes(raw[:8],'little');chunks.append(np.frombuffer(raw,dtype,count=n,offset=8))
    syn=np.concatenate(chunks);syn=syn[(syn['conf_pre']>=.5)&(syn['conf_post']>=.5)]
    pt=pd.Series(syn['body_pre']).map(a.type);qt=pd.Series(syn['body_post']).map(a.type)
    keys=pd.MultiIndex.from_arrays([pt,qt]);ed=e.set_index(['pre','post'])
    matched=ed.reindex(keys)
    valid=matched.verdict_corr.eq('dimorphic').fillna(False).to_numpy(dtype=bool)
    # Reweight both sex-specific edge totals at the same observed male locations.
    # This is explicitly a male-coordinate proxy, not measured female locations.
    wm=matched.weight_m.fillna(0).values;wf=matched.weight_f.fillna(0).values
    signed=(wm-wf)/np.maximum(wm+wf,1)
    result['syn_xyz_nm']=syn['xyz'][valid]*8
    result['syn_signed']=signed[valid]
    alpn=pt.isin(a.loc[a['class'].eq('ALPN'),'type']).values & np.isin(syn['roi'],[41])
    result['lh_syn_xyz_nm']=syn['xyz'][alpn]*8
    result['lh_syn_dim']=pd.Series(syn['body_post']).map(a.dimorphism).fillna('').str.contains('dimorphic|specific').to_numpy(dtype=bool)[alpn]
    _noise_summary(result,e)
    _display_summary(result,e)
    orn_counts(data,out)
    np.savez_compressed(target,**result)
    (out/'computed-provenance.json').write_text(json.dumps({'source':'MaleCNS v1.0 and 2025malecns release tables','edge_rows':len(e),'spatial_sample_rows':len(syn),'dimorphic_spatial_rows':int(valid.sum()),'spatial_url':SYN,'spatial_level':3,'density_method':'Observed male presynaptic locations, colored by (male-female)/(male+female) type connection weight. A proxy; female spatial distribution is not measured here.','matrix':'311 final communities; aggregate male weights; not original type-resolution matrix.','curves':'Computed from released edges, with release-table filters rather than unreleased original plotting selections.'},indent=2))
    return result


def _noise_summary(result, edges):
    noise=edges.verdict_corr.eq('noise')
    result['noise_connection_pct']=np.asarray(float(100*noise.mean()))
    result['noise_synapse_pct']=np.asarray(float(100*edges.loc[noise,'weight_m'].sum()/edges.weight_m.sum()))


def _display_summary(result, edges):
    # Stratify zeros explicitly so their display never depends on a log clamp.
    groups = [edges.weight_m.gt(0)&edges.weight_f.gt(0),
              edges.weight_m.eq(0)&edges.weight_f.gt(0),
              edges.weight_f.eq(0)&edges.weight_m.gt(0)]
    samples=[]
    for mask,budget in zip(groups,[36000,2000,2000]):
        ids=np.flatnonzero(mask.to_numpy())
        take=ids[np.linspace(0,len(ids)-1,min(budget,len(ids)),dtype=int)] if len(ids) else ids
        samples.append(edges.iloc[take][['weight_m','weight_f','p_corr']].fillna(1).values)
    result['scatter']=np.concatenate(samples)
    result['scatter_population_counts']=np.array([int(mask.sum()) for mask in groups])
    result['display_schema']=np.asarray(2)


def orn_counts(data,out):
    """One keyed row per released ORN type; bilateral totals, no name guessing."""
    path=out/'orn-counts.json'
    if path.exists():
        rows=json.loads(path.read_text())['rows']
    else:
        male=pd.read_feather(data/'annotations.feather')
        female=pd.read_csv(data/'female-annotations.tsv',sep='\t',low_memory=False)
        m=male.loc[male.type.str.startswith('ORN_',na=False)].groupby('type').size()
        f=female.loc[female.cell_type.str.startswith('ORN_',na=False)].groupby('cell_type').size()
        if set(m.index)!=set(f.index):
            raise ValueError('ORN type sets differ; resolve unmatched types explicitly')
        keys=sorted(m.index,key=lambda key:(-int(m[key]-f[key]),key))
        rows=[{'type':key,'glomerulus':key.removeprefix('ORN_'),'male':int(m[key]),'female':int(f[key])} for key in keys]
        path.write_text(json.dumps({'method':'Bilateral counts of all annotated ORN_ types in the pinned MaleCNS and FlyWire tables, including unknown side; not original paper selection.','rows':rows},indent=2))
    assert len({r['type'] for r in rows}) == len(rows)
    assert len({r['glomerulus'] for r in rows}) == len(rows)
    assert all(isinstance(r[k],int) and r[k]>=0 for r in rows for k in ['male','female'])
    return rows
