"""Six coordinated biology-style panels from one reproducible synthetic dataset.

No experimental observations, inferred embeddings, p-values or biological claims.
Run with Python from an Inklet checkout with the render extra installed.
"""
import argparse
import json
import math
from pathlib import Path
import random
import statistics

import inklet as i

ROOT = Path(__file__).resolve().parents[1]
STATES = ('Resting', 'Primed', 'Activated')
COLORS = ('#287b8e', '#a77720', '#984c78')
SEED = 20260907


def synthetic_cells(per_state=1500):
    rng = random.Random(SEED)
    rows = []
    for group in range(3):
        for _ in range(per_state):
            latent = rng.gauss(0, 1)
            x = (-2.3, 0, 2.4)[group]+.75*latent
            y = (.2, 1.5, -.3)[group]+.6*rng.gauss(0, 1)+.25*latent**2
            expression = [max(0., 1.2+.8*math.sin(g*.7)+
                (group-1)*(.75*math.cos(g*.42))+.22*latent+rng.gauss(0,.45)) for g in range(60)]
            rows.append(dict(state=group, x=x, y=y, expression=expression))
    return rows


def make_document(rows):
    groups = [[r for r in rows if r['state']==g] for g in range(3)]
    means = [[statistics.fmean(r['expression'][gene] for r in group) for gene in range(60)] for group in groups]
    panels = []
    def panel(**kwargs): return i.panel(78, 54, **kwargs)
    def add(name,title,p): panels.append((name,title,p.build()))

    p = panel(x=(-5,5.5), y=(-2,5), clip=True)
    for index,group in enumerate(groups):
        p.scatter([(r['x'],r['y']) for r in group],color=COLORS[index],size=.43,
                  stroke='none',raster=True,dpi=450,name=STATES[index])
    p.axes(x='Synthetic coordinate 1',y='Synthetic coordinate 2',count=4)
    p.legend(side='bottom',columns=3)
    add('cells',f'a  Cell states / {len(rows):,} cells',p)

    # Every 50th cell in each state: equal representation, no clustering implied.
    chosen = [r for group in groups for r in group[::50]]
    matrix = []
    for gene in range(60):
        values = [r['expression'][gene] for r in rows]
        mean,sd = statistics.fmean(values),statistics.pstdev(values)
        matrix.append([(r['expression'][gene]-mean)/sd for r in chosen])
    p = panel(x=(0,len(chosen)),y=(.5,60.5))
    p.matrix(matrix,x=range(len(chosen)+1),y=range(1,61),ramp=i.ramp('tol-sunset'),scale=i.linear((-2.5,2.5)),raster=True)
    p.axes(x='Selected cells / state order',y='Synthetic gene index',count=4)
    p.colorbar(side='right',label='Gene z-score')
    add('expression',f'b  Expression / 60 × {len(chosen)}',p)

    genes = list(range(0,60,5))
    p = panel(x=STATES,y=[f'G{g+1:02}' for g in genes])
    dot_records = []
    for group_index,group in enumerate(groups):
        for gene in genes:
            fraction = sum(r['expression'][gene]>1.2 for r in group)/len(group)
            dot_records.append(dict(state=STATES[group_index],gene=f'G{gene+1:02}',
                                    fraction=fraction,mean=means[group_index][gene]))
    p.scatter([(r['state'],r['gene']) for r in dot_records],
              size=[3.3*math.sqrt(r['fraction']) for r in dot_records],
              color=[r['mean'] for r in dot_records],ramp=i.ramp('tol-ylorbr'),scale=i.linear((0,3)),stroke='none')
    p.axes(y='Synthetic marker genes')
    p.colorbar(side='right',label='Mean / a.u.')
    dot_key = i.hstack([i.hstack([i.marker('circle',size=3.3*math.sqrt(f),fill='#586b6d',stroke='none'),
                         i.text(f'{f:.0%}',size=i.pt(7))],gap=1) for f in (.25,.5,1)],gap=4)
    panels.append(('markers','c  Marker fraction + mean',i.vstack([p.build(),dot_key,
        i.text('Area = fraction above 1.2 a.u.',size=i.pt(7))],gap=2)))

    values = {name:[r['expression'][0] for r in group] for name,group in zip(STATES,groups)}
    p = panel(x=STATES,y=(0,4),clip=True)
    p.violin(values,colors=COLORS,cut=0,median=True).boxplot(values,width=.17,outliers=False,stroke='#243848')
    p.axes(y='G01 expression / a.u.',count=4)
    add('distribution','d  Same cells / G01 distribution',p)

    p = i.plot_spec(78,54,x=(-2,2),y=(0,2.8),clip=True)
    shifts = [means[2][g]-means[0][g] for g in range(60)]
    abundance = [statistics.fmean(means[s][g] for s in range(3)) for g in range(60)]
    p.scatter(list(zip(shifts,abundance)),size=1.1,color='#586b6d',stroke='none')
    p.vline(0,stroke='#aab4b9',stroke_dash=(1,1))
    # Label the four extrema by a stated rule, without implying significance.
    extrema = ((min(range(60),key=shifts.__getitem__),'w'),
               (max(range(60),key=shifts.__getitem__),'e'),
               (min(range(60),key=abundance.__getitem__),'s'),
               (max(range(60),key=abundance.__getitem__),'n'))
    for gene,side in extrema:
        p.annotate(shifts[gene],abundance[gene],f'G{gene+1:02}',side=side,size=i.pt(7),clear=2)
    p.axes(x='Activated − resting / a.u.',y='Mean expression / a.u.',count=4)
    panels.append(('shifts','e  Gene-level mean shifts',p))

    # A descriptive covariance matrix, computed from the same cell measurements.
    selected = [0,5,10,15,20,25,30,35,40,45,50,55]
    columns = [[r['expression'][gene] for r in rows] for gene in selected]
    correlation = [[statistics.correlation(a,b) for b in columns] for a in columns]
    marker_ids = [f'G{gene+1:02}' for gene in selected]
    p = panel(x=marker_ids,y=marker_ids)
    p.matrix(correlation,x=marker_ids,y=marker_ids,ramp=i.ramp('tol-sunset'),scale=i.linear((-1,1)))
    p.axes(x='Synthetic marker genes')
    p.colorbar(side='right',label='Pearson r')
    add('correlation','f  Marker correlations',p)

    doc = i.document(width=345,columns=3,margin=8,gap=10)
    doc.add('title',i.text('Coordinated biology figures',size=i.pt(22)),colspan=3)
    doc.add('subtitle',i.text('Synthetic cell states / shared measurements, literal gene IDs and consistent state colors',size=i.pt(9)),colspan=3)
    for index,(name,title,diagram) in enumerate(panels):
        row,column = 2+(index//3)*2,index%3
        doc.add(name+'-title',i.text(title,size=i.pt(10)),row=row,column=column)
        doc.add(name,diagram,row=row+1,column=column)
    doc.add('caption',i.text('Synthetic demonstration only. Coordinates are generated directly, not UMAP or t-SNE. '
        'All six panels use the same cells; no significance tests or experimental conclusions are implied. '
        'Heatmap colors saturate at ±2.5 gene standard deviations. Dot areas encode threshold fractions.',
        width=325,size=i.pt(8)),colspan=3)
    return doc,dict(schema='inklet.biology-demo/0.1',seed=SEED,cells=len(rows),genes=60,
        state_counts={name:len(group) for name,group in zip(STATES,groups)},
        mean_expression=means,dots=dot_records,selected_heatmap_cells=len(chosen),
        source='Synthetic Gaussian latent states and non-negative expression; see executable recipe.',
        data_relationship='All panels derive from the same generated cell-expression records.')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'out/biology-panels')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    rows=synthetic_cells()
    doc,evidence=make_document(rows)
    fig=doc.compile();print(fig.report())
    if any(d.severity=='error' for d in fig.diagnostics): raise RuntimeError(fig.report())
    fig.export(args.output,dpi=180)
    (args.output/'data.json').write_text(json.dumps(dict(evidence=evidence,cells=rows),separators=(',',':'))+'\n')
    (args.output/'summary.json').write_text(json.dumps(evidence,indent=2)+'\n')


if __name__=='__main__':main()
