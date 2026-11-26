"""Typed process settings. Thresholds and endpoints live here, not in call sites."""

from functools import lru_cache
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_LOG_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})


class Settings(BaseSettings):
    """Environment-backed settings for one Turnwise process.

    ``TURNWISE_`` is the env prefix. An empty ``TURNWISE_PII_HASH_KEY`` is treated
    as unset so a blank ``.env`` line does not become a shared hash salt.
    """

    model_config = SettingsConfigDict(
        env_prefix="TURNWISE_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        frozen=True,
    )

    service_name: str = "turnwise"
    log_level: str = "INFO"
    log_json: bool = False
    http_host: str = "127.0.0.1"
    http_port: int = 8000
    stage_queue_maxsize: int = 32
    stage_put_timeout_s: float = 0.25
    otel_enabled: bool = True
    otel_endpoint: str = "http://localhost:4317"
    otel_insecure: bool = True
    otel_export_timeout_s: float = 5.0
    otel_max_queue_size: int = 2048
    metrics_enabled: bool = True
    pii_hash_key: SecretStr | None = None
    pii_fields: str = "patient_name,name,dob,date_of_birth,phone"
    ws_path: str = "/v1/audio"
    ws_sample_rate_hz: int = 16000
    ws_frame_ms: int = 20
    ws_max_sessions: int = 8
    bench_warmup: int = 5
    bench_samples: int = 20
    bench_timeout_s: float = 30.0
    bench_results_dir: str = "docs/results/bench"
    bench_markdown_path: str = "docs/benchmarks.md"
    bench_adr_path: str = "docs/adr/ADR-004-hardware-tier.md"
    bench_sherpa_model_dir: str = ""
    bench_whisper_model: str = ""
    bench_llm_command: str = ""
    bench_tts_command: str = ""
    ws_allowed_sample_rates: str = "8000,16000,48000"
    vad_window_samples: int = 512
    vad_speech_threshold: float = 0.5
    vad_speech_start_ms: int = 200
    vad_preroll_ms: int = 500
    vad_max_utterance_ms: int = 15000
    vad_timeout_ms: int = 30
    vad_onnx_path: str = "models/weights/silero_vad.onnx"
    audio_silence_rms: float = 0.005
    audio_silence_window_s: float = 3.0
    audio_clip_fraction: float = 0.01
    audio_clip_peak: int = 32760
    headphones_pcm_path: str = "client/prompts/headphones.pcm"
    asr_backend: str = ""
    asr_pool_slots: int = 1
    asr_finish_timeout_ms: int = 200
    asr_stub_transcript: str = "book tuesday at two thirty"
    hotword_score: float = 1.5
    clinic_timezone: str = "America/New_York"
    clinic_name: str = "Turnwise Clinic"
    doctor_roster_path: str = "data/doctors.txt"
    itn_timeout_s: float = 0.5

    @field_validator("service_name", "otel_endpoint")
    @classmethod
    def non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must be non-empty")
        return stripped

    @field_validator("log_level")
    @classmethod
    def normalize_log_level(cls, value: str) -> str:
        normalized = value.upper()
        if normalized not in _LOG_LEVELS:
            raise ValueError("log_level must be DEBUG, INFO, WARNING, ERROR, or CRITICAL")
        return normalized

    @field_validator("pii_hash_key", mode="before")
    @classmethod
    def blank_pii_key_is_unset(cls, value: object) -> object:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @field_validator("http_port")
    @classmethod
    def port_in_range(cls, value: int) -> int:
        if not 1 <= value <= 65535:
            raise ValueError("http_port must be between 1 and 65535")
        return value

    @field_validator(
        "stage_queue_maxsize",
        "otel_max_queue_size",
        "ws_max_sessions",
        "bench_warmup",
        "bench_samples",
        "vad_window_samples",
        "vad_speech_start_ms",
        "vad_preroll_ms",
        "vad_max_utterance_ms",
        "vad_timeout_ms",
        "audio_clip_peak",
        "asr_pool_slots",
        "asr_finish_timeout_ms",
    )
    @classmethod
    def at_least_one(cls, value: int) -> int:
        if value < 1:
            raise ValueError("queue sizes must be >= 1")
        return value

    @field_validator("ws_path")
    @classmethod
    def ws_path_absolute(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped.startswith("/"):
            raise ValueError("ws_path must start with /")
        return stripped

    @field_validator("ws_sample_rate_hz")
    @classmethod
    def pcm16k(cls, value: int) -> int:
        if value != 16000:
            raise ValueError("ws_sample_rate_hz must be 16000 in this milestone")
        return value

    @field_validator("ws_frame_ms")
    @classmethod
    def twenty_or_forty(cls, value: int) -> int:
        if value not in {20, 40}:
            raise ValueError("ws_frame_ms must be 20 or 40")
        return value

    @field_validator(
        "stage_put_timeout_s",
        "otel_export_timeout_s",
        "bench_timeout_s",
        "audio_silence_window_s",
        "itn_timeout_s",
    )
    @classmethod
    def positive_timeout(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("timeouts must be > 0")
        return value

    @field_validator("vad_speech_threshold", "audio_clip_fraction")
    @classmethod
    def unit_interval(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError("value must be in [0, 1]")
        return value

    @field_validator("audio_silence_rms", "hotword_score")
    @classmethod
    def non_negative(cls, value: float) -> float:
        if value < 0:
            raise ValueError("value must be >= 0")
        return value

    @field_validator("clinic_timezone")
    @classmethod
    def known_timezone(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("clinic_timezone must be non-empty")
        try:
            ZoneInfo(stripped)
        except ZoneInfoNotFoundError as exc:
            raise ValueError("unknown timezone") from exc
        return stripped

    @field_validator("clinic_name", "doctor_roster_path", "asr_stub_transcript")
    @classmethod
    def named_non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("value must be non-empty")
        return stripped

    @field_validator("asr_backend")
    @classmethod
    def known_asr_backend(cls, value: str) -> str:
        stripped = value.strip()
        if stripped not in {"", "stub", "zipformer", "whisper_la2"}:
            raise ValueError("asr_backend must be empty, stub, zipformer, or whisper_la2")
        return stripped

    @field_validator("ws_allowed_sample_rates")
    @classmethod
    def parse_rates(cls, value: str) -> str:
        parts = [part.strip() for part in value.split(",") if part.strip()]
        if not parts:
            raise ValueError("ws_allowed_sample_rates must list at least one rate")
        for part in parts:
            if not part.isdigit() or int(part) < 1:
                raise ValueError("sample rates must be positive integers")
        return ",".join(parts)

    @property
    def pii_field_names(self) -> frozenset[str]:
        return frozenset(part.strip() for part in self.pii_fields.split(",") if part.strip())

    @property
    def ws_frame_samples(self) -> int:
        return self.ws_sample_rate_hz * self.ws_frame_ms // 1000

    @property
    def ws_pcm_bytes(self) -> int:
        return self.ws_frame_samples * 2

    @property
    def allowed_sample_rates(self) -> frozenset[int]:
        return frozenset(int(part) for part in self.ws_allowed_sample_rates.split(",") if part)

    @property
    def vad_preroll_frames(self) -> int:
        return max(1, self.vad_preroll_ms // self.ws_frame_ms)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process settings, cached so the ASGI app and ``python -m server`` share one object."""
    return Settings()
