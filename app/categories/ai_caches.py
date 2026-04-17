"""AI framework & model caches."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable, List

from ..core.safety import register_allowed_prefix
from .base import Category, CleanItem, Risk


class AICachesCategory(Category):
    id = "ai_caches"
    name = "AI / ML caches"
    description = (
        "Downloaded models for Hugging Face, PyTorch hub, TensorFlow, Whisper, Ollama "
        "and similar tools. Typically the biggest folders on a dev machine."
    )

    def build_items(self) -> Iterable[CleanItem]:
        home = Path.home()
        local = Path(os.environ.get("LOCALAPPDATA", str(home / "AppData" / "Local")))
        user_profile = Path(os.environ.get("USERPROFILE", str(home)))

        items: List[CleanItem] = []

        def add(
            iid: str,
            name: str,
            paths: List[Path],
            affects: str,
            *,
            risk: Risk = Risk.LOW,
            default_selected: bool = True,
        ) -> None:
            for path in paths:
                register_allowed_prefix(path)
            items.append(
                CleanItem(
                    id=iid,
                    name=name,
                    paths=paths,
                    risk=risk,
                    affects=affects,
                    reversible=False,
                    default_selected=default_selected,
                )
            )

        add(
            "ai.hf_hub",
            "Hugging Face Hub cache",
            [home / ".cache" / "huggingface" / "hub"],
            "Models / tokenizers / datasets downloaded via transformers & diffusers. "
            "Redownloaded on next use; can reach 10-100+ GB.",
        )
        add(
            "ai.hf_transformers_legacy",
            "Hugging Face legacy transformers cache",
            [home / ".cache" / "huggingface" / "transformers"],
            "Older cache layout of the transformers library.",
            default_selected=False,
        )
        add(
            "ai.hf_datasets",
            "Hugging Face datasets cache",
            [home / ".cache" / "huggingface" / "datasets"],
            "Datasets downloaded via the datasets library. Very large with text corpora.",
        )
        add(
            "ai.torch_hub",
            "PyTorch hub cache",
            [home / ".cache" / "torch" / "hub"],
            "Models downloaded via torch.hub.load.",
        )
        add(
            "ai.torch_kernels",
            "PyTorch kernel cache",
            [home / ".cache" / "torch" / "kernels"],
            "Compiled CUDA kernels. Rebuilt on next run (first run may be slow).",
            default_selected=False,
        )
        add(
            "ai.tf_hub",
            "TensorFlow Hub cache",
            [home / ".tensorflow" / "tf-keras", home / ".keras"],
            "Models / datasets cached by TensorFlow & Keras.",
            default_selected=False,
        )
        add(
            "ai.whisper",
            "OpenAI Whisper model cache",
            [home / ".cache" / "whisper"],
            "Whisper transcription models. Redownloaded on next use.",
        )
        add(
            "ai.openai",
            "OpenAI CLI / SDK cache",
            [home / ".cache" / "openai"],
            "Temporary artifacts from OpenAI Python SDKs.",
        )
        add(
            "ai.llama_cpp",
            "llama.cpp local models",
            [home / ".cache" / "llama.cpp"],
            "Models downloaded via llama.cpp tools.",
            default_selected=False,
        )
        add(
            "ai.ollama",
            "Ollama models",
            [user_profile / ".ollama" / "models"],
            "Local LLMs stored by Ollama. Very large. Will need to be pulled again.",
            risk=Risk.HIGH,
            default_selected=False,
        )
        add(
            "ai.lmstudio_models",
            "LM Studio models",
            [home / ".cache" / "lm-studio" / "models", home / ".lmstudio" / "models"],
            "Local LLMs stored by LM Studio. Large, redownloaded on demand.",
            risk=Risk.HIGH,
            default_selected=False,
        )
        add(
            "ai.ultralytics",
            "Ultralytics (YOLO) cache",
            [home / ".cache" / "ultralytics"],
            "YOLO / Ultralytics model downloads.",
            default_selected=False,
        )
        add(
            "ai.clip",
            "OpenAI CLIP cache",
            [home / ".cache" / "clip"],
            "CLIP models; redownloaded on next use.",
            default_selected=False,
        )
        add(
            "ai.diffusers_cache",
            "diffusers temp",
            [home / ".cache" / "diffusers"],
            "diffusers library temporary files.",
        )
        add(
            "ai.gradio_tmp",
            "Gradio examples / flagged",
            [home / ".cache" / "gradio"],
            "Gradio temp files from local demos.",
        )
        add(
            "ai.modelscope",
            "ModelScope cache",
            [home / ".cache" / "modelscope"],
            "Alibaba ModelScope downloads.",
            default_selected=False,
        )

        return [it for it in items if any(p.exists() for p in it.paths)]
