# Kaggle submission notebook

The competition runs with Internet disabled. Publish this repository as a
private Kaggle Dataset before using the notebook. The prepared release archive
is `dist/jed_attack_framework.zip`; it contains only Git-tracked source and
documentation, not local traces, artifacts, or credentials.

In Kaggle:

1. Open **Kaggle → Datasets → New Dataset** and set its visibility to
   **Private**.
2. Upload `dist/jed_attack_framework.zip`, create the dataset, and wait for
   processing to finish.
3. Open the competition page, select **Code → New Notebook**, attach both the
   competition data and this private dataset in the right-side **Add Input**
   panel, then select a GPU accelerator if the competition UI offers one.
4. Upload `kaggle_submission.ipynb` from this repository or replace the new
   notebook's contents with it.
5. Set the `FRAMEWORK_ROOT` path in the first code cell only if automatic
   discovery cannot find the attached dataset.
6. Keep Internet disabled. The notebook copies the framework to
   `/kaggle/working`, writes the required `attack.py`, and starts only the
   official JED inference server.

The notebook does not call Qwen, any external API, or any locally hosted
server. Its final result is produced exclusively by the competition gateway.

Before committing a Kaggle run, verify that the cell prints a path like:

```text
Bundled attack: /kaggle/working/attack.py
```

The visible run writes a zero-score `submission.csv` placeholder solely for
Kaggle's submission UI. In the competition rerun, the official gateway writes
the real file.
