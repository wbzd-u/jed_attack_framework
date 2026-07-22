"""Development entry point; Kaggle notebooks can copy this package to working/."""

from jedfw.entrypoint import build_algorithm_class

AttackAlgorithm = build_algorithm_class()

__all__ = ["AttackAlgorithm"]
