"""Real released anatomy, composed as independent Inklet scenes."""
import inklet as i
import numpy as np
import json
from anatomy import paths
from native_plots import draw_pies, draw_clusters
from detailed_panels import panel_a, panel_c, panel_i, panel_j
BLUE="#668fb8"; GOLD="#e4b83e"; GREEN="#6d9259"; PINK="#bd4396"

def draw_chemosensory(p,a):
    panel_a(p,a)
    panel_c(p,a)

    # E: real female registered meshes and matched male MZ_lv2PN skeleton.
    for is_female,box in [(True,(812,510,132,132)),(False,(949,510,129,132))]:
        male_ids=a.ids('MZ_lv2PN',side='L')
        frame=a.arbor_frame(box,male_ids,female_group='MZ_lv2PN',pad=8)
        if is_female:p.nodes+=a.female('MZ_lv2PN',frame,color=PINK,opacity=.5)
        else:p.nodes+=a.neurons_draw(male_ids,frame,color='#5a994d',width=.75,opacity=.8)
        # Separate framed locator: its whole-brain fit is not an arbor overlay.
        locator=(box[0],620,43,26);p.rect(*locator,'white','#999',.5)
        whole=a.frame(locator,pad=1)
        p.nodes+=a.shell(whole,color='#fafafa',outline='#999',width=.35)
        if is_female:p.nodes+=a.female('MZ_lv2PN',whole,color=PINK,opacity=.8)
        else:p.nodes+=a.neurons_draw(male_ids,whole,color=GREEN,width=.45,opacity=.8)
    p.nodes.append(paths([[(948,484),(948,644)]],'#999999',width=.65).styled(stroke_dash=(2,3)))

    # F: anatomical location inset.
    frame=a.frame((389,682,87,54),pad=1)
    p.nodes+=a.shell(frame,color='#f8f7f7',outline='#777777',width=.4)
    p.nodes+=a.roi('LH-L',frame,color='#868686',outline='#777777',width=.4)

    panel_i(p,a)
    panel_j(p,a)

    # M: source-data partner selections. The precise IDs and input fractions
    # are exposed in the manifest, rather than passing illustrative arbors off
    # as neurons selected by the paper's authors.
    for col,group in enumerate(['pharyngeal','labellar','leg-ascending','leg-local','wing']):
        for cat_index,category in enumerate(['dimorphic','isomorphic']):
            name=group+'-'+category
            box=(177+col*188+cat_index*87,1318,83,184)
            frame=a.frame(box,full=True,central=True,pad=1)
            p.nodes+=a.shell(frame,full=True,central=True,color='#faf9f9',outline=None)
            fractions=a.manifest['groups'][name]['fractions']
            ramp=i.ramp(['#6f397b','#b55c68','#ed9b45','#f1c555'])
            colors={body:ramp(float(np.clip((fraction-.02)/.04,0,1))) for body,fraction in fractions.items()}
            p.nodes+=a.neurons_draw(a.ids(name),frame,color='#794370',width=.37,opacity=.6,colors=colors)


def draw_dimorphism(p,a):
    draw_pies(p)
    records=draw_clusters(p,a.data)
    (p.out/'cluster-chart-data.json').write_text(json.dumps(records,indent=2)+'\n')
    # B: real matched vpoEN neurons in frontal and dorsal projections.
    # Select the neurons occupying the same physical hemisphere in the
    # supplied registered coordinates (MaleCNS L and FlyWire right).
    ids=a.ids('vpoEN',side='L')
    for box,view in [((478,228,202,131),'front'),((488,366,192,91),'dorsal')]:
        frame=a.arbor_frame(box,ids,female_group='vpoEN',view=view,pad=2)
        p.nodes+=a.female('vpoEN',frame,view=view,color='#bd7a9b',opacity=.35)
        p.nodes+=a.neurons_draw(ids,frame,view=view,color='#709a5a',width=.5,opacity=.55)
    for box,view in [((490,307,99,54),'front'),((490,365,98,34),'dorsal')]:
        frame=a.frame(box,view=view,pad=1)
        p.nodes+=a.shell(frame,view=view,color='#fafafa',outline='#777777',width=.6)
        p.nodes+=a.neurons_draw(ids,frame,view=view,color='#777777',width=.5,opacity=.6)

    # D: source aSP10C_a neurons, framed inside the real brain outline.
    frame=a.frame((941,301,101,132),central=True,pad=2)
    p.nodes+=a.shell(frame,central=True,color='#fdfdfd',outline='#777777',width=.55)
    p.nodes+=a.neurons_draw(a.ids('aSP10C_a',side='R'),frame,color='#648a4e',width=.6,opacity=.8)

    frame=a.frame((752,714,390,206),pad=1)
    p.nodes+=a.shell(frame,color='#ffffff',outline='#bbbbbb',width=1)

    # P: every one of the 255 published cluster-102 members, with the source
    # annotation controlling the blue vs yellow colour, not invented curves.
    frame=a.frame((927,986,286,423),full=True,pad=1)
    p.nodes+=a.shell(frame,full=True,color='#f0eeee',outline=None)
    ids=a.ids('cluster-102')
    colors={str(body):GOLD if 'dimorphic' in str(a.neurons.loc[body,'dimorphism']) else BLUE for body in ids}
    p.nodes+=a.neurons_draw(ids,frame,color=BLUE,colors=colors,width=.34,opacity=.27)


def clipped(nodes,box):
    x,y,w,h=box
    return i.Diagram(children=tuple(nodes),clip_region=tuple(i.Vec2(*v) for v in [(x,y),(x+w,y),(x+w,y+h),(x,y+h)]),kind='clipped-anatomy')

