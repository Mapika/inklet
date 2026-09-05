"""Complete journal, 16:9 teaching slide and A4 worksheet examples.

Unlike the comparison gallery, these retain their intended page dimensions.
All measurements below are simulated.
"""
import inklet as i


def trend(height=None):
    return (i.plot_spec(height=height, x=(0, 5), y=(0, 8))
            .line([(0, 1), (1, 1.8), (2, 2.9), (3, 4.1), (4, 5.5), (5, 6.2)])
            .axes(x='Time / s', y='Signal / a.u.'))


def notes(*lines):
    return i.vstack([i.text(line) for line in lines], gap=i.current_theme().gap('m'))


def make_slide():
    doc = i.preset('educational.classroom', format='slide').document(
        columns=(3, 2), margin=8, gap=8)
    doc.add('title', i.component(i.title, 'How does the signal change?'), colspan=2, min_height=12)
    doc.add('chart', trend(height=77), row=1, column=0, min_height=85)
    doc.add('discussion', i.component(notes, 'Observe the graph',
        '1. Read the axes.', '2. Compare changes.', '3. Predict at 6 s.'), row=1, column=1)
    doc.add('caption', i.component(i.text, 'Simulated measurements · discuss your reasoning'), colspan=2, min_height=10)
    return doc


def make_worksheet():
    doc = i.preset('educational.worksheet', format='a4').document(margin=12, gap=9)
    doc.add('title', i.component(i.title, 'Reading and interpreting a graph'), min_height=10)
    doc.add('name', i.component(i.text, 'Name: ____________________    Date: ____________________'), min_height=6)
    doc.add('instructions', i.component(i.text, 'Use the simulated measurements to answer the questions.'), min_height=6)
    doc.add('chart', trend(height=90), min_height=110)
    doc.add('questions', i.component(notes,
        '1. What does each axis measure?', '____________________________________________________',
        '2. Estimate the signal at 2.5 seconds.', '____________________________________________________',
        '3. Describe how the rate of change varies.', '____________________________________________________',
        '4. What extra measurement would help test your prediction?',
        '____________________________________________________'), min_height=100)
    return doc


def make_journal():
    doc = i.preset('scientific.nature', format='double-column').document()
    panels = i.subfigure(columns=2, margin=0).letters()
    panels.add('response', trend(height=65), row=0, column=0)
    bars = (i.plot_spec(height=65, x=i.band(['A', 'B', 'C']), y=(0, 8))
            .bars(['A', 'B', 'C'], [3.1, 4.8, 6.2])
            .axes(x='Condition', y='Outcome / a.u.'))
    panels.add('conditions', bars, row=0, column=1)
    doc.add('panels', panels)
    doc.add('caption', i.component(i.text, 'Simulated data. A single response trace and outcomes for three conditions.'))
    return doc


def documents():
    return {'journal': make_journal(), 'slide': make_slide(), 'worksheet': make_worksheet()}


if __name__ == '__main__':
    from pathlib import Path
    for name, doc in documents().items():
        doc.export(Path('out/preset-formats')/name)
