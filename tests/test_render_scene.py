"""Compiled snapshots, revision invalidation and native backend agreement."""
from dataclasses import FrozenInstanceError, replace
from io import BytesIO
from pathlib import Path
import random
import pytest

import inklet as i
from inklet.core import Affine, Diagram, Envelope, ImagePrim, Rect, RectPrim, Style, Vec2
from inklet.render.bounds import painted_bounds


def box(x=0, color='blue', name=None):
    return Diagram(prim=RectPrim(10,8),style=Style(fill=color,stroke='none'),
                   transform=Affine.translation(x,0),name=name)


def test_unchanged_revision_reuses_every_node_and_resource():
    a,b=box(-12),box(12)
    root=Diagram(children=(a,b))
    first=i.compile_scene(root)
    second=i.compile_scene(root,previous=first)
    assert first.root is second.root
    assert second.stats['reused_nodes']==3 and second.stats['rebuilt_nodes']==0
    assert second.stats['reused_geometry']==1 and second.stats['new_geometry']==0
    assert second.changes==()
    assert second.damage_bounds(first) is None
    assert first.to_svg()==second.to_svg()
    assert first.to_pdf()==second.to_pdf()


def test_paint_edit_reuses_geometry_and_unaffected_subtree():
    a,b=box(-12),box(12)
    root=Diagram(children=(a,b))
    first=i.compile_scene(root)
    changed=replace(a,style=replace(a.style,fill='red'),_cache={})
    second=i.compile_scene(replace(root,children=(changed,b),_cache={}),previous=first)
    assert second.root.children[0].geometry is first.root.children[0].geometry
    assert second.root.children[1] is first.root.children[1]
    assert second.stats['new_geometry']==0
    assert next(c for c in second.changes if c.key==(0,)).reasons==('paint',)
    assert second.damage_bounds(first)==Rect(-17,-4,-7,4)
    assert second.to_pdf()!=first.to_pdf()


def test_inherited_paint_and_transform_changes_rebuild_context_without_geometry():
    child=box()
    root=Diagram(children=(child,))
    previous=i.compile_scene(root)
    revised=replace(root,style=Style(fill_opacity=.3),transform=Affine.rotation(30),_cache={})
    scene=i.compile_scene(revised,previous=previous)
    assert scene.stats['new_geometry']==0
    assert scene.root.children[0].style.fill_opacity==.3
    assert scene.root.children[0].world==Affine.rotation(30)
    assert set(scene.changes[0].reasons)=={'paint','transform'}


def test_geometry_replacement_and_removal_record_old_damage():
    a,b=box(-12),box(12)
    root=Diagram(children=(a,b))
    first=i.compile_scene(root)
    wider=replace(a,prim=RectPrim(14,8),_cache={})
    second=i.compile_scene(replace(root,children=(wider,),_cache={}),previous=first)
    assert second.stats['new_geometry']==1
    assert any(c.reasons==('removed',) and c.node_id==b.id for c in second.changes)
    assert second.damage_bounds(first).x1>=17


def test_repeated_primitive_uses_one_geometry_resource_in_distinct_contexts():
    prim=RectPrim(10,8)
    root=Diagram(children=tuple(Diagram(prim=prim,transform=Affine.translation(j*12,0),
                                      style=Style(fill='red' if j%2 else 'blue')) for j in range(50)))
    scene=i.compile_scene(root)
    assert scene.stats['new_geometry']==1
    assert len({id(n.geometry) for n in scene.root.children})==1
    assert len({n.world for n in scene.root.children})==50


def test_exporters_do_not_resolve_style_or_placement_again(monkeypatch):
    scene=i.compile_scene(i.window(box(),Rect(-3,-3,3,3)).rotated(20))
    def forbidden(*args,**kwargs):raise AssertionError('backend resolved authoring state again')
    monkeypatch.setattr(Style,'over',forbidden)
    monkeypatch.setattr(Affine,'__matmul__',forbidden)
    assert '<clipPath' in scene.to_svg()
    assert scene.to_pdf().startswith(b'%PDF')


def test_clip_revision_invalidates_descendant_visibility():
    root=i.window(box(),Rect(-5,-4,5,4))
    first=i.compile_scene(root)
    root=replace(root,clip_region=Rect(-2,-2,2,2).corners,_cache={})
    second=i.compile_scene(root,previous=first)
    assert first.root.children[0].visible_at(Vec2(4,0))
    assert not second.root.children[0].visible_at(Vec2(4,0))
    assert second.root.children[0].geometry is first.root.children[0].geometry
    assert 'clip' in second.changes[0].reasons


def png(color):
    Image=pytest.importorskip('PIL.Image')
    stream=BytesIO();Image.new('RGB',(5,5),color).save(stream,format='PNG');return stream.getvalue()


def test_compiled_images_remain_stable_after_source_replacement_and_deletion(tmp_path):
    path=tmp_path/'input.png';path.write_bytes(png('red'))
    root=Diagram(prim=ImagePrim(str(path),10,10))
    first=i.compile_scene(root)
    svg,pdf=first.to_svg(),first.to_pdf()
    path.write_bytes(png('blue'))
    assert not first.sources_current()
    second=i.compile_scene(root,previous=first)
    assert second.stats['new_geometry']==1
    assert second.to_svg()!=svg and second.to_pdf()!=pdf
    path.unlink()
    assert first.to_svg()==svg and first.to_pdf()==pdf
    assert second.root.prim.data==png('blue')


def test_document_recompiles_changed_image_inputs_and_keeps_previous_export(tmp_path):
    path=tmp_path/'input.png';path.write_bytes(png('red'))
    doc=i.document(width=40);doc.add('image',Diagram(prim=ImagePrim(str(path),10,10)))
    first=doc.compile();original=first.to_pdf()
    assert doc.compile() is first
    path.write_bytes(png('blue'))
    second=doc.compile()
    assert second is not first and second.to_pdf()!=original
    assert first.to_pdf()==original
    assert first.scene is first._figure._scene_override


def test_mutable_blend_notes_cannot_change_a_completed_snapshot():
    node=Diagram(children=(box(),),kind='blend',notes={'blend_mode':'multiply'})
    first=i.compile_scene(node);svg=first.to_svg();pdf=first.to_pdf()
    node.notes['blend_mode']='screen'
    assert first.to_svg()==svg and first.to_pdf()==pdf
    second=i.compile_scene(node,previous=first)
    assert second.root.blend_mode=='screen'
    assert second.to_svg()!=svg


def test_compiled_structure_and_statistics_are_read_only():
    scene=i.compile_scene(box())
    with pytest.raises(FrozenInstanceError):scene.root.world=Affine()
    with pytest.raises(TypeError):scene.stats['new_geometry']=99


def test_changed_font_is_refused_by_completed_scene(tmp_path):
    node=i.text('Font snapshot',size=4)
    font=tmp_path/'font.ttf';font.write_bytes(Path(node.prim.font_path).read_bytes())
    prim=replace(node.prim,font_path=str(font),lines=tuple(replace(line,runs=tuple(
        replace(run,font_path=str(font)) for run in line.runs)) for line in node.prim.lines))
    scene=i.compile_scene(replace(node,prim=prim))
    font.write_bytes(font.read_bytes()+b'changed')
    for backend in (scene.to_svg,scene.to_pdf):
        with pytest.raises(i.DiagramError,match='compiled font changed'):backend()
    with pytest.raises(i.DiagramError,match='compiled font changed'):
        i.compile_scene(replace(node,prim=prim),previous=scene)


@pytest.mark.parametrize('seed',range(5))
def test_seeded_revisions_match_cold_compilation_and_bounds(seed):
    rng=random.Random(seed)
    children=tuple(box(j*12) for j in range(8))
    root=Diagram(children=children)
    previous=i.compile_scene(root)
    for step in range(10):
        index=rng.randrange(len(children));node=children[index]
        if step%3==0:node=replace(node,style=Style(fill=rng.choice(['red','green','blue']),stroke='none'),_cache={})
        elif step%3==1:node=replace(node,transform=Affine.translation(rng.uniform(-30,30),rng.uniform(-10,10)),_cache={})
        else:node=replace(node,prim=RectPrim(rng.uniform(3,15),rng.uniform(3,15)),_cache={})
        children=children[:index]+(node,)+children[index+1:]
        root=replace(root,children=children,_cache={})
        current=i.compile_scene(root,previous=previous);cold=i.compile_scene(root)
        assert current.to_svg()==cold.to_svg()
        assert current.to_pdf()==cold.to_pdf()
        assert current.root.painted_bounds==painted_bounds(root,root.transform,root.style)
        previous=current


def test_layout_only_resize_invalidates_full_page_coverage():
    root=Diagram(children=(box(),),envelope_override=Envelope.from_rect(Rect(0,0,20,20)))
    old=i.compile_scene(root)
    new=i.compile_scene(replace(root,envelope_override=Envelope.from_rect(Rect(0,0,40,20)),_cache={}),previous=old)
    assert new.root is old.root
    assert new.damage_bounds(old)==Rect(0,0,40,20)


def test_document_replace_retains_previous_scene_for_reuse():
    a,b=box(name='left'),box(name='right')
    doc=i.document(width=80,columns=2)
    doc.add('left',a);doc.add('right',b,column=1,row=0)
    first=doc.compile()
    doc.replace('left',a.styled(fill='red'))
    second=doc.compile()
    assert second.scene.stats['reused_nodes']>0
    assert second.scene.stats['reused_geometry']>0
    assert second.scene.stats['new_geometry']==0
    old={n.id:n for n in first.scene.walk()}
    assert all(old[n.id] is n for n in second.scene.walk() if n.id.startswith('cell-right/'))
