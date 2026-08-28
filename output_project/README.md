# output_project/

**Every artifact produced by this project lands here.** Nothing generated is written to the project root or beside source code.

| Folder     | Holds                                                            |
| ---------- | ---------------------------------------------------------------- |
| `data/`    | Processed/cleaned datasets, train-test splits, vocab files        |
| `models/`  | Trained models, checkpoints, tokenizers, vectorizers              |
| `results/` | Metrics, evaluation tables, predictions, CSV/JSON output          |
| `figures/` | Plots, charts, confusion matrices, images used in the report      |
| `web/`     | The web deliverable — open `web/index.html` directly in a browser |
| `reports/` | Report drafts, slides, exported documentation                     |
| `logs/`    | Training logs, run logs, error output                            |

## Rules

- Source code stays in `src/` and `notebooks/`. Never here.
- Raw untouched data stays in `data_raw/`. Anything derived from it goes to `data/`.
- Everything in this folder is **reproducible** — it must be regenerable by re-running the pipeline. Safe to delete and rebuild.
- Scripts hardcode the `output_project/` prefix rather than depending on the working directory.

See [CLAUDE.md](../CLAUDE.md) for the full project configuration.
