"""Fast preflight for optional local GPT-OSS/Gemma evaluation."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path


def status(label: str, value: str | None) -> None:
    if not value:
        print(f"{label}: not configured")
        return
    path = Path(value)
    print(f"{label}: {path} ({'found' if path.exists() else 'missing'})")


def main() -> None:
    print("Python backends")
    for package in ("torch", "transformers", "llama_cpp"):
        print(f"  {package}: {'available' if importlib.util.find_spec(package) else 'missing'}")

    try:
        import torch

        print(f"  cuda_available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"  cuda_device: {torch.cuda.get_device_name(0)}")
            props = torch.cuda.get_device_properties(0)
            print(f"  cuda_vram_gb: {props.total_memory / (1024 ** 3):.1f}")
    except Exception as err:
        print(f"  torch_check: unavailable ({type(err).__name__})")

    print("Model paths")
    status("  GPT_OSS_MODEL_PATH", os.getenv("GPT_OSS_MODEL_PATH"))
    status("  GEMMA_MODEL_PATH", os.getenv("GEMMA_MODEL_PATH"))
    status("  GEMMA4_MODEL_PATH", os.getenv("GEMMA4_MODEL_PATH"))

    print("Result")
    if os.getenv("GPT_OSS_MODEL_PATH"):
        print("  GPT-OSS local evaluation can be attempted with run_local_eval.ps1.")
    else:
        print("  Deterministic evaluation is ready; a local LLM needs a model directory first.")


if __name__ == "__main__":
    main()
