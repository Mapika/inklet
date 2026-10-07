# Source: LIGO GW150914, Figure 1

**Paper.** B. P. Abbott *et al.* (LIGO Scientific Collaboration and Virgo
Collaboration), "Observation of Gravitational Waves from a Binary Black Hole
Merger", *Physical Review Letters* **116**, 061102 (2016).
DOI: [10.1103/PhysRevLett.116.061102](https://doi.org/10.1103/PhysRevLett.116.061102),
arXiv:1602.03837. Figure 1.

**Data.** Gravitational Wave Open Science Center (GWOSC), GW150914 event page,
"Figure 1" data release for paper P150914:
<https://gwosc.org/events/GW150914/>, files under
`https://gwosc.org/GW150914data/P150914/`.

**Licence.** GWOSC data are released under the Creative Commons Attribution
4.0 International licence (CC BY 4.0). Attribution: LIGO Scientific
Collaboration and Virgo Collaboration, via GWOSC (https://gwosc.org).

**Retrieved.** 2026-10-07.

## Files in `data/`

All six files are byte-for-byte copies of the GWOSC downloads (no trimming;
each is ~174 KB). Two columns: time in seconds after 2015-09-14 09:50:45 UTC,
and strain × 10²¹. Sampled at 16384 Hz over 0.25–0.46 s, band-passed
35–350 Hz with notches at the instrumental lines, as described in the
Figure 1 caption.

| File | Figure 1 panel |
|---|---|
| `fig1-observed-H.txt` | row 1, left: H1 observed |
| `fig1-observed-L.txt` | row 1, right: L1 observed (L1 only) |
| `fig1-waveform-H.txt` | row 2, left: numerical-relativity waveform projected onto H1 |
| `fig1-waveform-L.txt` | row 2, right: numerical-relativity waveform projected onto L1 |
| `fig1-residual-H.txt` | row 3, left: H1 observed minus the NR waveform |
| `fig1-residual-L.txt` | row 3, right: L1 observed minus the NR waveform |

SHA-256 of the files as downloaded:

```
3ce5475160fd6b39c41205c2055bfaf4e507981721a2eb4c5df0c99e2fa48d94  fig1-observed-H.txt
dc41302512f3e28336680030a255cc1f4fb3ec43ea5267cc044c9015051ecd85  fig1-observed-L.txt
ae379352f21dbdde9c3b1e582fb3614627df169cd6f28ea4508f5b6611c4b50c  fig1-residual-H.txt
59ea4081a678f7c376399d320e1d896afca9797b7a71f8b656452f2fa78e8234  fig1-residual-L.txt
720a2ae7d4d0cfbe3af29ed42d1450ec8f312e4ec15e7fd1df80d5a3ca134c97  fig1-waveform-H.txt
35615f652c9dda90a947ccf2c6e97835dd784b563ded5ebe4d6810de09db6e0c  fig1-waveform-L.txt
```

## Processing done in `figure.py`

* **H1 overlay on the L1 panel.** GWOSC publishes the L1 panel's data as
  "L1 only". The "H1 observed (shifted, inverted)" curve is built from
  `fig1-observed-H.txt` exactly as the caption says: time shifted by
  −6.9 ms and strain multiplied by −1. A cross-correlation check on the
  0.36–0.44 s window peaks at a shift of −7.4 ms (r = 0.89), consistent with
  the paper's 6.9 ms and sign.
* Nothing else is transformed; the strain values are plotted as published.

## Not available as data

* The 90% credible bands of the wavelet (BayesWave) and template
  reconstructions in row 2 are not part of the Figure 1 data release.
  (`P1500229/H1_reconstructions.txt` on the same page belongs to a different
  paper, uses whitened strain and covers only H1, so it was not substituted.)
* Row 4, the time-frequency (Q-transform) maps, is published only as PNG
  images (`fig1-freqtime-H.png`, `fig1-freqtime-L.png`), not as a grid.
