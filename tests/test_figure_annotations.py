import pytest
import inklet as i
from inklet.core import Rect,Envelope,DiagramError


def base():return i.Diagram(envelope_override=Envelope.from_rect(Rect(0,0,60,40)))


def test_joint_annotations_preserve_pins_and_are_order_independent():
    specs={'free':i.FigureAnnotation(i.tag('free'),positions=((15,10),(45,10))),
           'pin':i.FigureAnnotation(i.tag('pinned'),at=(15,10))}
    one=i.place_annotations(base(),specs,pad=0)
    two=i.place_annotations(base(),dict(reversed(list(specs.items()))),pad=0)
    assert one.notes['annotations']['placements']==two.notes['annotations']['placements']
    assert Rect(*one.notes['annotations']['placements']['free']['box']).center.x==45
    assert one.notes['annotations']['placements']['pin']['locked']


def test_joint_annotations_search_alternatives_and_report_impossible():
    specs={'a':i.FigureAnnotation(i.tag('A'),positions=((15,10),(45,10))),
           'b':i.FigureAnnotation(i.tag('B'),positions=((15,10),(15,11)))}
    out=i.place_annotations(base(),specs,pad=0)
    assert Rect(*out.notes['annotations']['placements']['a']['box']).center.x==45
    specs['a']=i.FigureAnnotation(i.tag('A'),at=(15,10));specs['b']=i.FigureAnnotation(i.tag('B'),at=(15,10))
    with pytest.raises(DiagramError,match='joint'):i.place_annotations(base(),specs,pad=0)


def test_transformed_targets_obstacles_and_unchanged_inputs():
    mark=i.circle(width=4,height=4,pad=0,fill='red').translated(15,20)
    art=i.Diagram(children=(mark,),envelope_override=Envelope.from_rect(Rect(0,0,60,40)))
    label=i.tag('callout')
    result=i.place_annotations(art,{'a':i.FigureAnnotation(label,target=mark.at('e'),positions=((40,20),))})
    row=result.notes['annotations']['placements']['a']
    assert row['leader'][0]==(17,20)
    assert not art.notes and 'annotations' not in label.notes
    assert '<text' in i.to_svg(result,text='embed')
    with pytest.raises(DiagramError,match='clear candidate'):
        i.place_annotations(art,{'a':i.FigureAnnotation(label,at=(15,20))})


def test_default_themed_path_blocks_annotations():
    art=i.Diagram(children=(i.as_drawn(i.polyline([(0,0),(20,20)])),),envelope_override=Envelope.from_rect(Rect(0,0,30,30)))
    with pytest.raises(DiagramError,match='clear candidate'):
        i.place_annotations(art,{'label':i.FigureAnnotation(i.tag('X'),at=(10,10))})
