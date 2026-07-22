from __future__ import annotations

import shutil
from pathlib import Path


def bundle(source_root: str | Path, output_root: str | Path) -> Path:
    """Copy the modular runtime into a Kaggle working directory.

    Kaggle can import local modules from ``/kaggle/working``. The notebook
    should call this before starting the official inference server, then load
    ``attack.py`` from the same directory.
    """
    source = Path(source_root).resolve()
    output = Path(output_root).resolve()
    package_source = source / "jedfw"
    package_target = output / "jedfw"
    package_target.parent.mkdir(parents=True, exist_ok=True)
    if package_target.exists():
        shutil.rmtree(package_target)
    shutil.copytree(package_source, package_target)

    knowledge_source = source / "knowledge" / "jed_actions.jsonl"
    knowledge_target = output / "knowledge" / "jed_actions.jsonl"
    knowledge_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(knowledge_source, knowledge_target)

    (output / "attack.py").write_text(
        "from jedfw.entrypoint import build_algorithm_class\n"
        "AttackAlgorithm = build_algorithm_class()\n",
        encoding="utf-8",
    )
    return output / "attack.py"


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("source_root")
    parser.add_argument("output_root")
    args = parser.parse_args()
    print(bundle(args.source_root, args.output_root))
