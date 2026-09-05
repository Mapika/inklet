import pytest
import inklet
from inklet.core import DiagramError


def definition():
    return inklet.categories({'a':'#246', 'b':'#975', 'c':'#579'},
                             labels={'a':'Alpha','b':'Beta','c':'Gamma'},
                             groups={'First':['a','b'], 'Second':['c']})


def test_subset_preserves_order_colors_labels_and_groups():
    full=definition();sub=full.subset(['c','a'])
    assert list(sub)==['a','c']
    assert sub['c']==full['c']
    assert sub.groups=={'First':('a',),'Second':('c',)}
    assert sub.legend_entries==(('Alpha','#246'),('Gamma','#579'))
    scale=sub.scale(reverse=True).with_range(40,0)
    assert scale.map('a')<scale.map('c')
    assert scale.tick_labels(scale.ticks())==('Gamma','Alpha')
    assert scale.group_breaks==(1,)


def test_bars_record_only_selected_categories_and_export_group_labels():
    cats=definition().subset(['c','a'])
    p=inklet.panel(40,30,x=(0,10),y=cats.scale(reverse=True))
    p.bars(['c','a'],[3,6],orient='h',bar_colors=cats)
    assert [(key.name,key.fill) for key in p.keys]==list(cats.legend_entries)
    p.axes();cats.group_labels(p,side='left');p.legend(side='right',markup=False)
    f=inklet.figure(width=120);f.add(p.build())
    assert 'Alpha' in f.to_svg()
    assert f.to_pdf().startswith(b'%PDF')


def test_invalid_categories_and_failed_marks_do_not_add_legend_entries():
    with pytest.raises(DiagramError):inklet.categories({})
    with pytest.raises(DiagramError):inklet.categories({'a':'red'},labels={'b':'B'})
    with pytest.raises(DiagramError):inklet.categories({'a':'red','b':'blue'},groups={'X':['b','a']})
    with pytest.raises(DiagramError):definition().subset(['missing'])
    with pytest.raises(DiagramError):definition().subset([])
    p=inklet.panel(20,20,x=['a'])
    with pytest.raises(DiagramError):p.bars(['a'],[0],bar_colors=definition())
    assert not p.keys
    with pytest.raises(DiagramError):definition().group_labels(p)
