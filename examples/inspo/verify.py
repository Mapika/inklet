"""Verify the complete scenes can be built while all reference reads are denied."""
import argparse,json,sys
from pathlib import Path
import xml.etree.ElementTree as ET
import numpy as np

def main():
    p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    blocked=[]
    def guard(event,values):
        if event!='open' or not isinstance(values[0],(str,bytes)):return
        path=str(values[0]).lower()
        if path.endswith(('.jpg','.jpeg')) or 'trace-cache' in path:
            blocked.append(path);raise AssertionError('Reference artwork access: '+path)
    sys.addaudithook(guard)
    from anatomy import Anatomy
    from canvas import Page
    from authored_charts import chemosensory,dimorphism,furniture
    from anatomical_panels import draw_chemosensory,draw_dimorphism
    from chart_data import prepare
    from layout import PANELS
    anatomy=Anatomy(args.data);data=prepare(args.data,args.output/'chart-data')
    report={'reference_read_attempts':blocked,'pages':[]}
    for name,anatomical,charts in [('chemosensory',draw_chemosensory,chemosensory),('dimorphism',draw_dimorphism,dimorphism)]:
        page=Page(name,args.output);anatomical(page,anatomy);charts(page,anatomy,data);furniture(page)
        assert len(PANELS[name])=={'chemosensory':13,'dimorphism':17}[name]
        root=ET.parse(args.output/(name+'.svg')).getroot()
        counts={k:sum(n.tag.endswith('}'+k) for n in root.iter()) for k in ['image','text','path']}
        assert counts['image']==0
        assert counts['text']>150
        report['pages'].append({'name':name,'panels':len(PANELS[name]),'native_labels':page.labels,'svg_elements':counts,'guarded_scene_build':'passed'})
    assert np.isfinite(data['matrix']).all() and (data['matrix']>=0).all()
    assert np.all(np.abs(data['syn_signed'])<=1)
    report['numeric_checks']='finite nonnegative connection matrix; signed contrast within [-1,1]'
    report['audit_regressions']=audit_checks(args.output,data)
    (args.output/'validation.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))


def audit_checks(output,data):
    """Independent checks for the quantitative/association errors in the audit."""
    chart=output/'chart-data'
    read=lambda name:json.loads((chart/name).read_text())
    rows=read('orn-counts.json')['rows']
    assert len(rows)==len({r['type'] for r in rows})==len({r['glomerulus'] for r in rows})
    assert all(isinstance(r[k],int) and r[k]>=0 for r in rows for k in ['male','female'])
    xy=np.array([(r['x'],r['y']) for r in read('scatter-g.json')['points']])
    stats=read('scatter-g-statistics.json')
    assert np.isclose(stats['pearson_r'],np.corrcoef(xy.T)[0,1])
    residual=xy[:,1]-(stats['intercept']+stats['slope']*xy[:,0])
    assert abs(residual.sum())<1e-8 and abs((residual*xy[:,0]).sum())<1e-6
    network=read('network.json')
    for edge in network['edges']:
        x,y=edge['tip'];x0,y0,x1,y1=network['nodes'][str(edge['post'])]
        assert not (x0<x<x1 and y0<y<y1), 'head hidden by destination'
    for name in ['hierarchy-labels.json','matrix-zoom.json']:
        records=read(name)
        if isinstance(records,dict):records=records['labels']
        boxes=sorted((r['box'] for r in records),key=lambda b:b[1])
        assert all(b[1]>a[3] for a,b in zip(boxes,boxes[1:])), 'label collision'
    zoom=read('matrix-zoom.json')
    lo,hi=zoom['slice'];n=data['matrix'].shape[0]
    assert np.allclose(zoom['source_box'],[370+lo*259/n,991+lo*231/n,(hi-lo)*259/n,(hi-lo)*231/n])
    for row in read('cdf-h-summary.json'):
        values=data[f"{row['prefix']}_fraction_{row['flag']}"]
        assert row['n']==len(values)
        assert np.isclose(row['percent'],100*np.mean(values>=.3))
    scatter=data['scatter']
    populations=data['scatter_population_counts']
    if populations[1]:assert np.any(scatter[:,0]==0)
    if populations[2]:assert np.any(scatter[:,1]==0)
    aligned=read('text-alignment.json')
    assert all(np.allclose(row['target'],row['actual'],atol=1e-9) for row in aligned)
    key=read('h-legend.json');x0,y0,x1,y1=key['box']
    for curve in key['curves']:
        for a,b in zip(curve,curve[1:]):
            assert not segment_hits_box(a,b,(x0-2,y0-2,x1+2,y1+2)), 'H legend crowds a curve'
    return {'unique_orn_types':len(rows),'correlation_and_OLS':'passed',
            'visible_target_arrow_tips':len(network['edges']),
            'label_clearance':'passed','matrix_zoom':'passed',
            'CDF_marginals':'passed','zero_weight_gutters':'passed',
            'centered_C_D_labels':len(aligned),'H_legend_curve_clearance':'passed'}


def segment_hits_box(a,b,box):
    """Slab intersection includes segments whose endpoints are both outside."""
    enter,leave=0.,1.
    for start,end,lo,hi in [(a[0],b[0],box[0],box[2]),(a[1],b[1],box[1],box[3])]:
        delta=end-start
        if abs(delta)<1e-12:
            if start<lo or start>hi:return False
        else:
            t0,t1=sorted(((lo-start)/delta,(hi-start)/delta))
            enter=max(enter,t0);leave=min(leave,t1)
            if enter>leave:return False
    return True
if __name__=='__main__':main()
