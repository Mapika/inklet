import inklet as i

data = i.dataset(
    {'time': [0, 1, 2, 3], 'signal': [1, 4, 3, 5]},
    name='response', units={'time': 's', 'signal': 'mV'},
)
response = i.plot_spec(x=(0, 3), y=(0, 6))
response.line(data.points('time', 'signal'),
              name='Signal', stroke='#176b9b')
response.axes(x='Elapsed time / s', y='Signal / mV')
response.legend(side='bottom')

groups = ['Control', 'Treatment']
summary = i.plot_spec(x=groups, y=(0, 8))
summary.bars(groups, [3, 6], bar_colors=['#176b9b', '#198c83'])
summary.axes(y='Outcome / a.u.')

page = i.publication('double-column').document(columns=2, gap=8)
page.add('response', response, row=0, column=0, min_height=60)
page.add('summary', summary, row=0, column=1, min_height=60)
page.letters()
page.compile().save('two-panels.svg', 'two-panels.pdf')
