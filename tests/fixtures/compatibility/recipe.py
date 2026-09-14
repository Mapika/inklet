"""Frozen simulated recipe used to reopen files written by released Inklet wheels."""
import json
from pathlib import Path
import inklet as i


def composition(root):
    values=json.loads((Path(root)/'measurements.json').read_text())
    result=i.composition(100,50)
    result.add('left',i.module(f'A: {values[0]}'),x=10,y=15)
    result.add('right',i.module(f'B: {values[1]}'),x=60,y=15)
    return result


def write(root):
    from inklet.experimental.project import AssetManifest, EntityMap, FigureProject
    from inklet.experimental.selection import KeyedTable, SelectionState
    root=Path(root);inputs=root/'inputs';inputs.mkdir(parents=True)
    (inputs/'measurements.json').write_text('[2, 4]\n')
    assets=AssetManifest.capture(inputs,[dict(id='measurements',path='measurements.json',
        source='Original simulated compatibility fixture',license='MIT',unit='arbitrary')])
    identities=EntityMap(['a','b'],{'rows':{'sample-7':'a','sample-9':'b'},
        'composition':{'/left':'a','/right':'b'}})
    study=FigureProject('Compatibility study',composition(inputs),assets=assets,identities=identities)
    study.editor.command('edit',{'path':'/left','placement':{'x':14}})
    study.select('rows',['sample-7']);study.save(root/'project',asset_root=inputs)
    table=KeyedTable('measurements',dict(id=['sample-7','sample-9'],value=[2,4]))
    (root/'selection.json').write_text(SelectionState.for_table(table,selected=['sample-7'],visible=['sample-9']).to_json()+'\n')
    (root/'layout.json').write_text(json.dumps(study.editor.overrides(),indent=2)+'\n')
