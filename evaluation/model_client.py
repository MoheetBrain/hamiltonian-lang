"""Minimal OpenAI-compatible chat client.

Standard library only — `urllib`. Adding `openai` would pull a dependency tree into a
project whose core has none, for one POST.

Works against any OpenAI-compatible endpoint: Ollama, vLLM, llama.cpp server, or a remote
API. The endpoint and model are configuration, never hard-coded into an experiment.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

__all__ = ["ModelConfig", "Completion", "ModelClient"]


@dataclass(frozen=True)
class ModelConfig:
    base_url: str = "http://localhost:11434/v1"
    model: str = "gemma4:31b"
    temperature: float = 0.7
    max_tokens: int = 2400
    top_p: float = 1.0
    seed: int | None = None
    timeout_s: int = 900
    api_key: str = "not-required-for-local"

    def sampling_fingerprint(self) -> dict:
        """Everything that must be identical across matched arms."""
        return {
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "top_p": self.top_p,
            "seed": self.seed,
        }


@dataclass
class Completion:
    content: str
    reasoning: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_s: float = 0.0
    finish_reason: str = ""
    model_reported: str = ""
    error: str | None = None
    raw: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.error is None


class ModelClient:
    def __init__(self, cfg: ModelConfig) -> None:
        self.cfg = cfg

    def describe(self) -> dict:
        """Identity of the model under test, recorded once per run.

        Ollama exposes a content digest, which is the closest thing to a checksum
        available for a local weight file. Absence is recorded rather than guessed at.
        """
        info: dict = {"base_url": self.cfg.base_url, "model": self.cfg.model,
                      "digest": None, "parameter_size": None, "quantization": None}
        try:
            root = self.cfg.base_url.rsplit("/v1", 1)[0]
            with urllib.request.urlopen(f"{root}/api/tags", timeout=20) as r:
                for m in json.loads(r.read())["models"]:
                    if m["name"] == self.cfg.model:
                        info["digest"] = m.get("digest")
                        d = m.get("details", {})
                        info["parameter_size"] = d.get("parameter_size")
                        info["quantization"] = d.get("quantization_level")
                        info["size_bytes"] = m.get("size")
        except Exception as e:  # noqa: BLE001 - absence is data, not a failure
            info["digest_error"] = f"{type(e).__name__}: {e}"
        return info

    def complete(self, system: str, user: str, *, attempt: int = 0) -> Completion:
        payload = {
            "model": self.cfg.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.cfg.temperature,
            "max_tokens": self.cfg.max_tokens,
            "top_p": self.cfg.top_p,
        }
        if self.cfg.seed is not None:
            payload["seed"] = self.cfg.seed + attempt

        req = urllib.request.Request(
            f"{self.cfg.base_url}/chat/completions",
            data=json.dumps(payload).encode(),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.cfg.api_key}",
            },
            method="POST",
        )
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=self.cfg.timeout_s) as r:
                body = json.loads(r.read())
        except urllib.error.HTTPError as e:
            return Completion(
                "", error=f"HTTP {e.code}: {e.read()[:300]!r}", latency_s=time.time() - t0
            )
        except Exception as e:  # noqa: BLE001
            return Completion(
                "", error=f"{type(e).__name__}: {e}", latency_s=time.time() - t0
            )

        dt = time.time() - t0
        choice = body.get("choices", [{}])[0]
        msg = choice.get("message", {}) or {}
        usage = body.get("usage", {}) or {}
        return Completion(
            content=msg.get("content") or "",
            reasoning=msg.get("reasoning") or "",
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
            latency_s=dt,
            finish_reason=choice.get("finish_reason", ""),
            model_reported=body.get("model", ""),
            raw={"usage": usage, "finish_reason": choice.get("finish_reason")},
        )
