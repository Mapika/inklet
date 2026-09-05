from pathlib import Path
from inklet.cli import main,load_figure,_watch_files


def test_cli_builds_document_script_and_supports_no_preview(tmp_path,capsys):
    script=tmp_path/'author.py'
    script.write_text('''import inklet as i
def make_document():
    d=i.document(width=70)
    d.add('title',i.component(i.text,'CLI figure'))
    return d
''')
    assert main(['build',str(script),'--output',str(tmp_path/'out'),'--vectors-only'])==0
    assert (tmp_path/'out/figure.svg').exists() and (tmp_path/'out/figure.pdf').exists()
    assert 'CLI figure' in load_figure(script).to_svg()


def test_cli_reports_errors_and_checks_dependencies(tmp_path,capsys):
    script=tmp_path/'bad.py';script.write_text('x=1')
    assert main(['build',str(script)])==1
    assert 'make_document' in capsys.readouterr().err
    assert main(['doctor'])==0
    assert 'chromium' in capsys.readouterr().out


def test_watch_tracks_code_and_explicit_data(tmp_path):
    script=tmp_path/'author.py';script.write_text('x=1')
    helper=tmp_path/'helper.py';helper.write_text('x=1')
    data=tmp_path/'values.csv';data.write_text('1')
    before=_watch_files(script,[data])
    data.write_text('100')
    assert _watch_files(script,[data])!=before
    assert str(helper) in [row[0] for row in before]
