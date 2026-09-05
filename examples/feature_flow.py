"""Reusable matrix, sequence and database components with named ports."""
import inklet


def make_figure():
    glyphs = [inklet.marker(shape,2,fill=color) for shape,color in
              [('circle','#4285b4'),('triangle','#db8b42'),('square','#559d78')]]
    database = inklet.database('Sequence\ndatabase', width=24, height=20)
    matrix = inklet.feature_matrix([[.2,.8,.4],[.7,.1,.6],[.3,.5,1]],cell=7,
                                  row_labels=['A','B','C'],column_labels=glyphs,
                                  highlight_rows=[1])
    sequence = inklet.sequence(glyphs,pitch=7,stem=2,baseline=True)
    fig = inklet.figure(width=125)
    fig.add(inklet.hstack([database,matrix,sequence],gap=15))
    fig.link(database.at('output'),matrix.at('row-1'))
    fig.link(matrix.at('output'),sequence.at('input'))
    return fig


if __name__=='__main__':
    make_figure().save('out/feature_flow.svg','out/feature_flow.pdf',text='embed')
