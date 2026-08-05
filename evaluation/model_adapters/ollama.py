"""Ollama / OpenAI-compatible adapter with a content-addressed generation cache.

Lead-Architect-owned. Isolated from `evaluation/harness.py` (the HML-EVAL-001 harness,
frozen with its results) and from every agent-owned V1 module.

Design commitments, each earned from something that went wrong earlier in this project:

* **Raw generations are never overwritten.** A cache entry is written once. A re-run
  replays it and never re-queries, so repeating a study costs nothing for calls already
  made and cannot silently yield different data for identical inputs.
* **Reasoning is separated from final content.** `gemma4:31b` bills its reasoning trace to
  `completion_tokens` while returning it in a distinct field, so 43 completion tokens can
  produce 2 characters of content. Any token comparison that ignores this is measuring the
  wrong thing (see `docs/evaluation/LOCAL_MODEL_MANIFEST.md` §3).
* **The cache key includes the model digest.** A model updated in place under the same tag
  must not silently reuse another build's generations.
* **Retries are narrow.** Transport failure or empty content only — never a
  content-dependent condition, which would bias the sample toward outputs the caller likes.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
DEFAULT_CACHE = REPO / "evaluation" / "results" / "generation_cache"

__all__ = ["OllamaConfig", "Generation", "OllamaAdapter", "probe_model"]


@dataclass(frozen=True)
class OllamaConfig:
    base_url: str = "http://localhost:11434/v1"
    native_url: str = "http://localhost:11434"
    model: str = "gemma4:31b"
    temperature: float = 0.0
    top_p: float = 1.0
    max_tokens: int = 2400
    seed: int | None = None
    timeout_s: int = 900
    retries: int = 2
    backoff_s: float = 2.0

    def sampling(self) -> dict[str, Any]:
        return {
            "model": self.model,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "max_tokens": self.max_tokens,
            "seed": self.seed,
        }


@dataclass
class Generation:
    """One model call. `content` and `reasoning` are kept apart deliberately."""

    content: str = ""
    reasoning: str = ""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_s: float = 0.0
    finish_reason: str = ""
    attempts: int = 1
    from_cache: bool = False
    error: str | None = None
    cache_key: str = ""
    model_digest: str = ""
    sampling: dict = field(default_factory=dict)
    captured_utc: str = ""

    @property
    def ok(self) -> bool:
        return self.error is None

    @property
    def empty(self) -> bool:
        """True when the call succeeded but produced no content.

        Usually means the reasoning trace consumed the whole `max_tokens` budget. It is a
        distinct outcome from an error and must be counted separately, not as a failure of
        the representation under test.
        """
        return self.ok and not (self.content or "").strip()

    @property
    def reasoning_share(self) -> float | None:
        """Rough share of completion tokens spent on reasoning, by character proportion.

        Approximate by construction — the API does not report a reasoning token count —
        and labelled as such wherever it is reported.
        """
        total_chars = len(self.content or "") + len(self.reasoning or "")
        if not total_chars or not self.completion_tokens:
            return None
        return round(len(self.reasoning or "") / total_chars, 4)


def probe_model(cfg: OllamaConfig) -> dict[str, Any]:
    """Identity and capabilities, read from Ollama rather than assumed."""
    out: dict[str, Any] = {"model": cfg.model, "digest": None}
    try:
        with urllib.request.urlopen(f"{cfg.native_url}/api/tags", timeout=30) as r:
            for m in json.loads(r.read())["models"]:
                if m["name"] == cfg.model:
                    d = m.get("details", {})
                    out.update(
                        digest=m.get("digest"),
                        size_bytes=m.get("size"),
                        parameter_size=d.get("parameter_size"),
                        quantization=d.get("quantization_level"),
                        format=d.get("format"),
                        capabilities=m.get("capabilities"),
                    )
    except Exception as e:  # noqa: BLE001 — absence is data
        out["probe_error"] = f"{type(e).__name__}: {e}"
    return out


class OllamaAdapter:
    def __init__(
        self, cfg: OllamaConfig | None = None, cache_dir: Path | None = None
    ) -> None:
        self.cfg = cfg or OllamaConfig()
        self.cache_dir = Path(cache_dir or DEFAULT_CACHE)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        info = probe_model(self.cfg)
        self.digest: str = info.get("digest") or "unknown"
        self.model_info = info
        self.stats = {"calls": 0, "cache_hits": 0, "errors": 0, "empty": 0, "retries": 0}

    # -- cache -----------------------------------------------------------
    def cache_key(self, system: str, user: str) -> str:
        payload = json.dumps(
            {
                "model": self.cfg.model,
                "digest": self.digest,
                "temperature": self.cfg.temperature,
                "top_p": self.cfg.top_p,
                "max_tokens": self.cfg.max_tokens,
                "seed": self.cfg.seed,
                "system": system,
                "user": user,
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()

    def _cache_path(self, key: str) -> Path:
        return self.cache_dir / key[:2] / f"{key}.json"

    def _read_cache(self, key: str) -> Generation | None:
        p = self._cache_path(key)
        if not p.exists():
            return None
        try:
            g = Generation(**json.loads(p.read_text()))
            g.from_cache = True
            return g
        except Exception:  # noqa: BLE001 — a corrupt entry is a miss, never a crash
            return None

    def _write_cache(self, key: str, gen: Generation) -> None:
        p = self._cache_path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists():
            return  # written once; raw generations are never overwritten
        record = asdict(gen)
        record["from_cache"] = False
        p.write_text(json.dumps(record, indent=2, ensure_ascii=False))

    # -- generation ------------------------------------------------------
    def generate(self, system: str, user: str, *, force: bool = False) -> Generation:
        key = self.cache_key(system, user)
        if not force:
            hit = self._read_cache(key)
            if hit is not None:
                self.stats["cache_hits"] += 1
                return hit

        payload: dict[str, Any] = {
            "model": self.cfg.model,
            "messages": (
                ([{"role": "system", "content": system}] if system else [])
                + [{"role": "user", "content": user}]
            ),
            "temperature": self.cfg.temperature,
            "top_p": self.cfg.top_p,
            "max_tokens": self.cfg.max_tokens,
        }
        if self.cfg.seed is not None:
            payload["seed"] = self.cfg.seed

        last_error: str | None = None
        for attempt in range(1, self.cfg.retries + 2):
            t0 = time.time()
            try:
                req = urllib.request.Request(
                    f"{self.cfg.base_url}/chat/completions",
                    data=json.dumps(payload).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(req, timeout=self.cfg.timeout_s) as r:
                    body = json.loads(r.read())
            except urllib.error.HTTPError as e:
                last_error = f"HTTP {e.code}: {e.read()[:200]!r}"
            except Exception as e:  # noqa: BLE001
                last_error = f"{type(e).__name__}: {e}"
            else:
                choice = (body.get("choices") or [{}])[0]
                msg = choice.get("message") or {}
                usage = body.get("usage") or {}
                gen = Generation(
                    content=msg.get("content") or "",
                    reasoning=msg.get("reasoning") or "",
                    prompt_tokens=usage.get("prompt_tokens", 0),
                    completion_tokens=usage.get("completion_tokens", 0),
                    total_tokens=usage.get("total_tokens", 0),
                    latency_s=round(time.time() - t0, 3),
                    finish_reason=choice.get("finish_reason", ""),
                    attempts=attempt,
                    cache_key=key,
                    model_digest=self.digest,
                    sampling=self.cfg.sampling(),
                    captured_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                )
                # Retry an empty completion once: it means the reasoning trace ate the
                # budget, not that the representation failed. Never retry on content.
                if gen.empty and attempt <= self.cfg.retries:
                    self.stats["retries"] += 1
                    last_error = "empty content"
                    time.sleep(self.cfg.backoff_s * attempt)
                    continue
                self.stats["calls"] += 1
                if gen.empty:
                    self.stats["empty"] += 1
                self._write_cache(key, gen)
                return gen

            if attempt <= self.cfg.retries:
                self.stats["retries"] += 1
                time.sleep(self.cfg.backoff_s * attempt)

        self.stats["errors"] += 1
        gen = Generation(
            error=last_error, attempts=self.cfg.retries + 1, cache_key=key,
            model_digest=self.digest, sampling=self.cfg.sampling(),
            captured_utc=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )
        # Errors are NOT cached: a transport failure is a property of the moment, not of
        # the prompt, and caching one would poison every later run.
        return gen

    def summary(self) -> dict:
        return {
            "model": self.cfg.model,
            "digest": self.digest,
            "sampling": self.cfg.sampling(),
            "cache_dir": str(self.cache_dir),
            **self.stats,
        }
