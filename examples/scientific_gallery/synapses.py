"""Read spatial-index annotation records; do not infer unique synaptic sites."""
import gzip,json
import numpy as np
import pandas as pd
from fly_data import download,BUCKET


def sample_records(data,out):
    cache=out/'al-records.npz'
    types=['ORN_DA1','ORN_VA1v','ORN_VA1d','ORN_DL3']
    files=[]
    for level,shards in [(3,1),(4,1),(5,2)]:
        for shard in range(shards):
            name=data/(f'synapse-spatial-level{level}.shard' if shards==1 else f'synapse-spatial-level{level}-{shard}.shard')
            files.append((BUCKET+f'v1.0/male-cns-v1.0-synapses-precomputed/by_spatial_level_{level}/{shard:x}.shard',name))
    if cache.exists():result=dict(np.load(cache))
    else:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=4) as pool:list(pool.map(lambda pair:download(*pair),files))
        annotations=pd.read_feather(data/'annotations.feather').set_index('bodyId')
        selected=annotations.index[annotations.type.isin(types)].values
        dtype=np.dtype({'names':['xyz','pre_conf','post_conf','pre','roi'],'formats':[('<f4',3),'<f4','<f4','<u4','<i2'],'offsets':[0,24,28,40,48],'itemsize':64})
        rows=[]
        for _,file in files:
            blob=file.read_bytes();idx=np.frombuffer(blob[:16],'<u8');index=np.frombuffer(gzip.decompress(blob[16+int(idx[0]):16+int(idx[1])]),'<u8').reshape(3,-1);offset=16
            for gap,size in zip(index[1],index[2]):
                offset+=int(gap);raw=gzip.decompress(blob[offset:offset+int(size)]);offset+=int(size)
                n=int.from_bytes(raw[:8],'little');v=np.frombuffer(raw,dtype,count=n,offset=8)
                rows.append(v[(v['pre_conf']>=.5)&(v['post_conf']>=.5)&(v['roi']==1)&np.isin(v['pre'],selected)])
        rows=np.concatenate(rows)
        result={'xyz_nm':rows['xyz']*8,'type':pd.Series(rows['pre']).map(annotations.type).map({t:k for k,t in enumerate(types)}).to_numpy(int)}
        np.savez_compressed(cache,**result)
    unique=len(np.unique(np.column_stack([result['xyz_nm'],result['type']]),axis=0))
    (out/'synapse-sampling.json').write_text(json.dumps({'method':'All matching records from spatial levels 3–5, both confidences >=0.5, left AL ROI 1, presynaptic ORN types listed below. No random thinning. Repeated coordinates are retained; figures count annotation records, not unique presynaptic sites. Depth distributions are record-weighted.','types':types,'records':len(result['type']),'unique_coordinate_type_tuples':unique,'source_files':[url for url,_ in files]},indent=2))
    return result
