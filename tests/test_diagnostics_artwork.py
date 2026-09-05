import inklet as i
from inklet.render.bundle import component_paths


def test_artwork_hairlines_are_consolidated_without_losing_targets():
    a=i.polyline([(0,0),(10,0)],stroke='#333',stroke_width=.01)
    b=i.polyline([(0,1),(10,1)],stroke='#333',stroke_width=.02)
    artwork=i.Diagram(children=(a,b),kind=i.abutting('illustration'),name='protein')
    outside=i.polyline([(0,20),(10,20)],stroke='#333',stroke_width=.03)
    root=i.Diagram(children=(artwork,outside))
    findings=i.lint(root,rules=['HAIRLINE'])
    assert len(findings)==2
    grouped=next(d for d in findings if len(d.targets)==2)
    assert set(grouped.targets)=={a.id,b.id}
    assert 'protein' in grouped.message and '2 strokes' in grouped.message
    assert grouped.where is not None
    assert any(d.targets==(outside.id,) for d in findings)


def test_review_context_keeps_nested_component_names_and_target_ids():
    label=i.text('colliding label')
    module=i.Diagram(children=(label,),name='Evoformer')
    cell=i.Diagram(children=(module,),name='architecture',kind='document-cell')
    root=i.Diagram(children=(cell,),name='page',kind='page')
    paths=component_paths(root)
    assert paths[label.id]=='architecture / Evoformer'
    assert paths[module.id]=='architecture / Evoformer'
    assert paths[root.id]==''


def test_document_preserves_artwork_kind_when_cell_needs_no_translation():
    from inklet.core import Envelope, Rect
    parts=tuple(i.as_drawn(i.polyline([(1,y),(19,y)],stroke='#333',stroke_width=.01)) for y in (2,4))
    artwork=i.Diagram(children=parts,kind=i.abutting('illustration'),name='protein',
                       envelope_override=Envelope.from_rect(Rect(0,0,20,10)))
    doc=i.document(width=20,height=10,margin=0,gap=0)
    doc.add('artwork',artwork)
    compiled=doc.compile()
    warnings=[d for d in compiled.diagnostics if d.code=='HAIRLINE']
    assert len(warnings)==1 and len(warnings[0].targets)==2
    assert 'protein' in warnings[0].message
