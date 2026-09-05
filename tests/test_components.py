import pytest
import inklet
from inklet.core import DiagramError, Vec2


def test_sequence_copies_repeated_symbols_and_aligns_ports():
    symbol=inklet.marker('triangle',2,fill='red')
    node=inklet.sequence([symbol,symbol,symbol],pitch=4,stem=1,baseline=True)
    assert node.anchor_point('item-0')==Vec2(-4,0)
    assert node.anchor_point('item-2')==Vec2(4,0)
    inklet.resolve(node)  # No duplicate node ids.


def test_feature_matrix_headers_follow_cells_and_survive_layout():
    glyph=inklet.marker('circle',2)
    node=inklet.feature_matrix([[0,1,2],[2,1,0]],cell=5,
                              row_labels=['a','long label'],column_labels=[glyph]*3,
                              highlight_rows=[0])
    a,b=node.anchor_point('matrix-nw'),node.anchor_point('matrix-se')
    assert b-a==Vec2(15,10)
    assert node.anchor_point('row-0').y==-2.5
    assert node.anchor_point('column-2').x==5
    db=inklet.database('Features')
    fig=inklet.figure(width=100)
    fig.add(inklet.hstack([db,node],gap=12))
    fig.link(db.at('output'),node.at('row-0'))
    assert '<svg' in fig.to_svg()
    assert fig.to_pdf().startswith(b'%PDF')


def test_components_reject_inconsistent_dimensions():
    with pytest.raises(DiagramError):inklet.sequence([])
    with pytest.raises(ValueError):inklet.sequence(['a'],pitch=0)
    with pytest.raises(DiagramError):inklet.feature_matrix([[1],[1,2]])
    with pytest.raises(DiagramError):inklet.feature_matrix([[1]],row_labels=[])
    with pytest.raises(DiagramError):inklet.feature_matrix([[1]],highlight_rows=[1])
    with pytest.raises(ValueError):inklet.database('a',height=1)
