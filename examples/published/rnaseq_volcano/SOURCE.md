# Source: airway smooth muscle dexamethasone RNA-seq (Himes et al. 2014)

## Publication

Himes BE, Jiang X, Wagner P, Hu R, Wang Q, Klanderman B, Whitaker RM, Duan Q,
Lasky-Su J, Nikolos C, Jester W, Johnson M, Panettieri RA Jr, Tantisira KG,
Weiss ST, Lu Q (2014). RNA-Seq transcriptome profiling identifies CRISPLD2 as
a glucocorticoid responsive gene that modulates cytokine function in airway
smooth muscle cells. *PLoS ONE* 9(6): e99625.
doi:[10.1371/journal.pone.0099625](https://doi.org/10.1371/journal.pone.0099625),
PMCID PMC4057123.

Figure recreated: **Figure 1A**, "Volcano plot of overall gene-based
differential expression results for four cell lines treated with DEX vs. left
untreated … There were 316 differentially expressed genes according to an
adjusted p-value <0.05 (blue dots)."
Original image (viewed for comparison only, not in the repository):
<https://journals.plos.org/plosone/article/figure/image?size=large&id=10.1371/journal.pone.0099625.g001>

## Data

- GEO series **GSE52778**, supplementary file
  `GSE52778_Dex_vs_Untreated_gene_exp.diff.gz` (830 KB, dated 2013-11-26),
  the Cuffdiff v2.0.2 gene-level output for DEX vs untreated that the paper's
  methods and the GEO processing protocol describe ("gene-based differential
  expression results for Dex vs. Untreated condition").
- URL: <https://ftp.ncbi.nlm.nih.gov/geo/series/GSE52nnn/GSE52778/suppl/GSE52778_Dex_vs_Untreated_gene_exp.diff.gz>
- Retrieved: 2026-10-07. SHA-256 of the downloaded `.gz`:
  `6c6ca5ce509e98ea9d5fb9aef698b2a0fbf4c778997c7ceaf95a42cbf15eb63f`
- Committed file: `data/dex_vs_untreated_gene_exp.tsv` (1.19 MB, 23,273 genes,
  SHA-256 `335ca71851551b256ec74a61c40216e8064a410c6a95ab4ded684b95854ec8ce`).

## Licence

- The article is open access under the Creative Commons Attribution License
  (CC BY), © 2014 Himes et al.
- GEO: NCBI places no restrictions on the use or distribution of GEO data
  (NCBI data-use policy); the submitters attached no additional terms to
  GSE52778. Attribution: Himes et al. 2014, GEO GSE52778.

## Processing

`data/dex_vs_untreated_gene_exp.tsv` is the Cuffdiff table with columns
dropped and renamed, every value copied verbatim as text (no rounding):

| committed column | Cuffdiff column | meaning |
|---|---|---|
| `gene` | `gene` | gene symbol (`test_id`/`gene_id` are identical to it) |
| `status` | `status` | OK / NOTEST / LOWDATA / HIDATA / FAIL |
| `fpkm_dex` | `value_1` | FPKM, sample_1 = Dex |
| `fpkm_untreated` | `value_2` | FPKM, sample_2 = Untreated |
| `log2_fold_change` | `log2(fold_change)` | log2(value_2 / value_1) = log2(untreated / DEX) |
| `p_value`, `q_value`, `significant` | same | Cuffdiff test p, BH q, q < 0.05 flag |

Dropped: `test_id`, `gene_id`, `locus`, `sample_1`, `sample_2`, `test_stat`.

In `figure.py`: the 1,431 genes Cuffdiff reports with an infinite fold change
(written as ±1.79769e+308, expression 0 in one condition) are excluded, as they
cannot be placed on the x axis; 21,842 genes are drawn. Ten genes have
`p_value = 0` (below double precision, including DUSP1, FKBP5 and KLF15);
they are drawn at the smallest positive p in the table (2.2 × 10⁻¹⁶).
316 genes are flagged `significant = yes`, matching the paper's count.
