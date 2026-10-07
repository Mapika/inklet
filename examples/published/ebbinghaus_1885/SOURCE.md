# Source: Ebbinghaus's forgetting curve (the savings method, 1885)

## Figure being recreated

The forgetting curve of H. Ebbinghaus: savings (percent of the original
learning effort saved on relearning) against the time since learning, for a
list of 13 nonsense syllables learned to two errorless recitations. The
classic plotted form is the log-time view of Murre & Dros (2015), Figs 2 and
4, whose Ebbinghaus points and error bars are reproduced in the figure
"Ebbinghaus curve" (Murre, CC BY 4.0,
https://commons.wikimedia.org/wiki/File:Ebbinghaus_curve.png). That image was
viewed only and is not stored in the repository. The figure here uses the
same log-time axis, with the seven points joined and each drawn with its
probable error of the mean.

## Primary sources

- Ebbinghaus, H. (1885). *Über das Gedächtnis: Untersuchungen zur
  experimentellen Psychologie*. Leipzig: Duncker & Humblot. Savings summary
  (Murre & Dros cite it as p. 56, Table 3). Scan (public domain):
  https://archive.org/details/berdasgedcht00ebbi
- Ebbinghaus, H. (1913). *Memory: A Contribution to Experimental Psychology*
  (trans. H. A. Ruger & C. E. Bussenius). New York: Teachers College,
  Columbia University. Scan (public domain):
  https://archive.org/details/memorycontributi00ebbiuoft
  The summary table (columns I-V: No., time after learning X in hours,
  savings Q %, P.E.m, forgotten v %) is on printed pp. 76-77, just before
  Section 29, "Discussion of Results".
  Section texts for each interval: I (19 min, Q = 58.2), II (63 min, 44.2),
  III (525 min, 35.8), IV (one day, 33.7), V (two days, 27.8), VI (six days,
  25.4), VII (31 days, 21.1).
- Murre, J. M. J. & Dros, J. (2015). Replication and analysis of Ebbinghaus'
  forgetting curve. *PLoS ONE* 10(7): e0120644.
  https://doi.org/10.1371/journal.pone.0120644 (open access, CC BY 4.0). Used
  for the second-source check (Table 3, "Ebbinghaus" column) and for the
  log-time presentation. Its own replication data are not used here.

## Data

- File: `data/ebbinghaus_savings.csv`, transcribed by hand from the 1913
  summary table (pp. 76-77), and checked against the per-interval averages
  of the 1913 sections and the German 1885 text.
- Retrieved: 2026-10-07 (scans read from archive.org; the German and English
  texts were checked against each other for every value).
- Values (savings Q %, P.E.m in percentage points, time X in hours after learning):

  | no | X (h) | label | Q % | P.E.m | forgotten v % |
  |---|---|---|---|---|---|
  | 1 | 0.33 | 20 min | 58.2 | 1.0 | 41.8 |
  | 2 | 1 | 1 h | 44.2 | 1.0 | 55.8 |
  | 3 | 8.8 | 9 h | 35.8 | 1.0 | 64.2 |
  | 4 | 24 | 1 day | 33.7 | 1.2 | 66.3 |
  | 5 | 48 | 2 days | 27.8 | 1.4 | 72.2 |
  | 6 | 6 x 24 = 144 | 6 days | 25.4 | 1.3 | 74.6 |
  | 7 | 31 x 24 = 744 | 31 days | 21.1 | 0.8 | 78.9 |

- Cross-check with Murre & Dros (2015) Table 3, Ebbinghaus column: 0.582,
  0.442, 0.358, 0.337, 0.278, 0.254, 0.211. All seven agree with the table
  above (their values are the same numbers, as proportions). The German
  section texts give the same averages: Q = 33,7 (1 day), 27,8 (2 days),
  25,4 (6 days). Savings and forgotten columns sum to 100 at every point.
- Licence: Ebbinghaus died in 1909; both the 1885 German text and the 1913
  translation are public domain. Murre & Dros (2015) is CC BY 4.0; only its
  citation and its table check are used.

## Processing (all in `figure.py`)

- Times converted from hours to days (divided by 24) for the log axis.
  Savings are plotted as given (percent), with the P.E.m as symmetric error
  bars. The 1913 text writes the probable error of the mean as "P.E.m"; it is
  not a standard error and is drawn as printed.
- Log time axis from 0.01 to 100 days (20 min is 0.0138 days). The points are
  joined in time order.
- Time is the table's X, not the section headings' exact minutes (19, 63 and
  525 min); see NOTES.md.
