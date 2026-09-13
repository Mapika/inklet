"""Additional real neuropil surfaces and denser observed LH synapse samples."""
import gzip,json
import numpy as np
import pandas as pd
from fly_data import download,get_mesh,BUCKET
from detailed_panels import EXTRA_ROIS

def ensure_rois(data):
    for name,key in EXTRA_ROIS.items():
        folder='malecns-vnc-neuropil-roi-v0' if key>=100 else 'fullbrain-roi-v4'
        get_mesh(BUCKET+'rois/'+folder+'/mesh',key-100 if key>=100 else key,data/('roi-'+name+'.npz'))
    for name,key in {'ProLN-L':34,'ProLN-R':35,'MesoLN-L':22,'MesoLN-R':23,'MetaLN-L':24,'MetaLN-R':25,'ADMN-L':14,'ADMN-R':15}.items():
        get_mesh(BUCKET+'rois/malecns-vnc-nerve-roi-v2/mesh',key,data/('roi-'+name+'.npz'))

def local_synapses(data,out):
    """Denser independently sampled synapses, preserving measured coordinates."""
    cache=out/'local-synapses-v2.npz'
    if cache.exists():return dict(np.load(cache))
    from concurrent.futures import ThreadPoolExecutor
    a=pd.read_feather(data/'annotations.feather').set_index('bodyId')
    dtype=np.dtype({'names':['xyz','pre_conf','post_conf','pre','post','roi'],'formats':[('<f4',3),'<f4','<f4','<u4','<u4','<i2'],'offsets':[0,24,28,40,44,48],'itemsize':64})
    files=[]
    for level,shards in [(3,1),(4,1),(5,2)]:
        for shard in range(shards):
            name=data/(f'synapse-spatial-level{level}.shard' if shards==1 else f'synapse-spatial-level{level}-{shard}.shard')
            files.append((BUCKET+f'v1.0/male-cns-v1.0-synapses-precomputed/by_spatial_level_{level}/{shard:x}.shard',name))
    with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(lambda v:download(*v),files))
    alpn=a.index[a['class'].eq('ALPN')].values
    types=['ORN_DA1','ORN_VA1v','ORN_VA1d','ORN_DL3'];orn=a.index[a.type.isin(types)].values
    lh=[];al=[]
    for _,file in files:
        b=file.read_bytes();idx=np.frombuffer(b[:16],'<u8');index=np.frombuffer(gzip.decompress(b[16+int(idx[0]):16+int(idx[1])]),'<u8').reshape(3,-1);offset=16
        for gap,size in zip(index[1],index[2]):
            offset+=int(gap);raw=gzip.decompress(b[offset:offset+int(size)]);offset+=int(size);n=int.from_bytes(raw[:8],'little');v=np.frombuffer(raw,dtype,count=n,offset=8)
            conf=(v['pre_conf']>=.5)&(v['post_conf']>=.5)
            lh.append(v[conf&(v['roi']==41)&np.isin(v['pre'],alpn)])
            al.append(v[conf&np.isin(v['roi'],[1,2])&np.isin(v['pre'],orn)])
    lh=np.concatenate(lh);al=np.concatenate(al);dim=pd.Series(lh['post']).map(a.dimorphism).fillna('')
    category=np.where(dim.str.contains('specific'),2,np.where(dim.str.contains('dimorphic'),1,0))
    result=dict(lh_xyz_nm=lh['xyz']*8,lh_category=category,al_xyz_nm=al['xyz']*8,al_side=al['roi'],al_type=pd.Series(al['pre']).map(a.type).map({t:k for k,t in enumerate(types)}).to_numpy(dtype=int))
    np.savez_compressed(cache,**result)
    (out/'local-synapses-provenance.json').write_text(json.dumps({'method':'Actual presynaptic sites from spatial levels 3–5. Both confidences >= 0.5. C: ORN_DA1, ORN_VA1v, ORN_VA1d, ORN_DL3 with AL ROI 1/2. F: ALPN presynaptic sites in LH(L), ROI 41; target-body dimorphism sets color. F keeps all colored sites and every fifth isomorphic background site for visibility.','lh_rows':len(lh),'lh_categories':{str(k):int((category==k).sum()) for k in range(3)},'al_rows':len(al),'al_left_rows':int((al['roi']==1).sum()),'source_files':[url for url,_ in files]},indent=2))
    return result

def ensure_example_types(data):
    """Match named labels to the actual released cell types used in A and I."""
    import hashlib
    manifest=json.loads((data/'manifest.json').read_text())
    wanted={'KCab-s':8,'AN09B017d':2,'LgLG1a':8}
    missing={k:v for k,v in wanted.items() if k not in manifest['groups']}
    if not missing:return
    annotations=pd.read_feather(data/'annotations.feather')
    selected=pd.read_feather(data/'selected-neurons.feather')
    for cell_type,count in missing.items():
        rows=annotations[annotations.type.eq(cell_type)].sort_values('bodyId')
        chosen=rows.iloc[np.linspace(0,len(rows)-1,min(count,len(rows)),dtype=int)]
        ids=chosen.bodyId.astype(int).tolist()
        for body in ids:
            file=data/'skeletons'/f'{body}.swc';download(manifest['skeleton_base']+f'{body}.swc',file)
            manifest['skeletons'][str(body)]=hashlib.sha256(file.read_bytes()).hexdigest()
        manifest['groups'][cell_type]=dict(ids=ids,available=len(rows),selection='all' if len(rows)<=count else 'evenly spaced sorted body IDs')
        selected=pd.concat([selected,chosen],ignore_index=True).drop_duplicates('bodyId')
    selected.reset_index(drop=True).to_feather(data/'selected-neurons.feather')
    (data/'manifest.json').write_text(json.dumps(manifest,indent=2))
