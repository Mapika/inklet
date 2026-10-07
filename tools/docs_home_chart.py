import inklet as i

df = {'day': [0, 2, 4, 6, 8],
      'treated': [0, 3, 5, 6, 6.5],
      'control': [0, 1, 1.5, 2, 2.2]}
chart = i.line(df, x='day', y=['treated', 'control'], markers=True,
               ylabel='signal (a.u.)')
chart.save('growth.svg')
