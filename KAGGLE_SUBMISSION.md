# Kaggle submission notebook

The competition runs with Internet disabled. Publish this repository as a
private Kaggle Dataset (or upload a zip whose root contains `jedfw/`,
`knowledge/`, and `bundle_submission.py`) before using the notebook.

In Kaggle:

1. Create a GPU notebook for `ai-agent-security-multi-step-tool-attacks`.
2. Attach the competition data input and the private framework dataset.
3. Upload `kaggle_submission.ipynb` from this repository.
4. Set the `FRAMEWORK_ROOT` path in the first code cell only if automatic
   discovery cannot find the attached dataset.
5. Keep Internet disabled. The notebook copies the framework to
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
