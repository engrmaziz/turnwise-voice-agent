"""Typed process settings. Thresholds and endpoints live here, not in call sites."""

from functools import lru_cache
from typing import Self
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import SecretStr, field_validator, model_validator
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
    asr_zipformer_encoder_path: str = (
        "models/weights/zipformer/encoder-epoch-99-avg-1-chunk-16-left-128.int8.onnx"
    )
    asr_zipformer_decoder_path: str = (
        "models/weights/zipformer/decoder-epoch-99-avg-1-chunk-16-left-128.int8.onnx"
    )
    asr_zipformer_joiner_path: str = (
        "models/weights/zipformer/joiner-epoch-99-avg-1-chunk-16-left-128.int8.onnx"
    )
    asr_zipformer_tokens_path: str = "models/weights/zipformer/tokens.txt"
    asr_zipformer_bpe_vocab_path: str = "models/weights/zipformer/bpe.vocab"
    asr_zipformer_bpe_model_path: str = "models/weights/zipformer/bpe.model"
    asr_whisper_model_path: str = "models/weights/whisper/tiny.en"
    asr_pool_slots: int = 1
    asr_finish_timeout_ms: int = 200
    asr_stub_transcript: str = "book tuesday at two thirty"
    hotword_score: float = 2.0
    clinic_timezone: str = "America/New_York"
    clinic_name: str = "Turnwise Clinic"
    doctor_roster_path: str = "data/doctors.txt"
    itn_timeout_s: float = 0.5
    endpoint_digit_patience_ms: int = 1000
    endpoint_digit_hard_ms: int = 2000
    endpoint_hard_silence_ms: int = 1200
    endpoint_high_p: float = 0.85
    endpoint_high_silence_ms: int = 200
    endpoint_mid_p: float = 0.5
    endpoint_mid_silence_ms: int = 500
    endpoint_default_silence_ms: int = 800
    turn_model_enabled: bool = True
    turn_timeout_ms: int = 20
    turn_onnx_path: str = "models/weights/turn_complete.onnx"
    turn_feature_dim: int = 256
    turn_ngram: int = 3
    barge_in_min_speech_ms: int = 250
    backchannel_max_ms: float = 400.0
    backchannel_phrases: str = "mm-hmm,mhm,uh-huh,yeah,ok,okay"
    nlu_model_path: str = ""
    nlu_timeout_ms: int = 40
    nlu_min_intent_confidence: float = 0.6
    nlu_feature_dim: int = 256
    nlu_ngram: int = 3
    phonetic_min_score: float = 0.75
    phonetic_margin: float = 0.03
    repair_markers: str = "no,sorry,i mean,actually"
    repair_modality_after: int = 2
    repair_handoff_after: int = 3
    tool_filler_after_ms: int = 300
    tool_hard_timeout_ms: int = 1500
    tool_retry_limit: int = 1
    confirm_explicit_below: float = 0.8
    urgent_keywords: str = (
        "chest pain,can't breathe,cannot breathe,cant breathe,"
        "shortness of breath,passing out,fainted,stroke,suicidal"
    )
    regex_slots_enabled: bool = False
    paraphrase_max_chars: int = 180
    faq_min_score: float = 0.2
    faq_path: str = "data/faq.md"
    calendar_db_path: str = "data/turnwise.sqlite"
    llm_timeout_ms: int = 2000
    llm_backend: str = ""
    llm_ollama_host: str = "http://127.0.0.1:11434"
    llm_ollama_model: str = "qwen3.5:4b"
    tts_backend: str = ""
    tts_piper_onnx_path: str = "models/weights/piper/en_US-amy-low.onnx"
    tts_piper_config_path: str = "models/weights/piper/en_US-amy-low.onnx.json"
    tts_voice: str = "default"
    tts_speed: float = 1.0
    tts_digit_speed: float = 0.85
    tts_frame_ms: int = 20
    tts_first_chunk_min_words: int = 4
    tts_later_min_words: int = 8
    tts_max_hold_ms: int = 400
    tts_timeout_ms: int = 800
    tts_abbrev: str = "dr.,mr.,mrs.,ms.,st.,e.g.,i.e.,p.m.,a.m."
    tts_warmup_phrases: str = (
        "greeting,one_moment,could_you_repeat,headphones_required,"
        "seek_emergency,cannot_book_now,cannot_speak,goodbye"
    )
    emotion_model_path: str = ""
    emotion_model_enabled: bool = False
    emotion_timeout_ms: int = 80
    sentiment_enabled: bool = True
    sentiment_model_enabled: bool = False
    frustration_threshold: float = 0.65
    frustration_turns: int = 2
    tts_frustrated_speed: float = 0.9
    fuse_w_audio: float = 0.4
    fuse_w_text: float = 0.2
    fuse_w_repair: float = 0.2
    fuse_w_no: float = 0.1
    fuse_w_barge: float = 0.1
    eval_scenario_dir: str = "evals/scenarios"
    eval_time_scale: float = 0.0
    eval_realtime_n: int = 30
    eval_smoke_n: int = 30
    eval_matrix_n: int = 900
    eval_soft_judge: bool = False
    eval_text_inject: bool = False
    llm_health_timeout_ms: int = 2000
    asr_collapse_turns: int = 3
    asr_collapse_conf: float = 0.3
    audio_retain: bool = False
    audio_retain_s: int = 0
    audio_retain_dir: str = "data/retain"
    load_n_max: int = 16
    llm_max_batch: int = 1

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
        "endpoint_digit_patience_ms",
        "endpoint_digit_hard_ms",
        "endpoint_hard_silence_ms",
        "endpoint_high_silence_ms",
        "endpoint_mid_silence_ms",
        "endpoint_default_silence_ms",
        "turn_timeout_ms",
        "turn_feature_dim",
        "turn_ngram",
        "barge_in_min_speech_ms",
        "nlu_timeout_ms",
        "nlu_feature_dim",
        "nlu_ngram",
        "repair_modality_after",
        "repair_handoff_after",
        "tool_filler_after_ms",
        "tool_hard_timeout_ms",
        "tool_retry_limit",
        "paraphrase_max_chars",
        "llm_timeout_ms",
        "tts_first_chunk_min_words",
        "tts_later_min_words",
        "tts_max_hold_ms",
        "tts_timeout_ms",
        "emotion_timeout_ms",
        "frustration_turns",
        "eval_realtime_n",
        "eval_smoke_n",
        "eval_matrix_n",
        "llm_health_timeout_ms",
        "asr_collapse_turns",
        "load_n_max",
        "llm_max_batch",
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

    @field_validator("ws_frame_ms", "tts_frame_ms")
    @classmethod
    def twenty_or_forty(cls, value: int) -> int:
        if value not in {20, 40}:
            raise ValueError("frame_ms must be 20 or 40")
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

    @field_validator(
        "vad_speech_threshold",
        "audio_clip_fraction",
        "endpoint_high_p",
        "endpoint_mid_p",
        "nlu_min_intent_confidence",
        "phonetic_min_score",
        "phonetic_margin",
        "confirm_explicit_below",
        "faq_min_score",
        "frustration_threshold",
        "asr_collapse_conf",
        "fuse_w_audio",
        "fuse_w_text",
        "fuse_w_repair",
        "fuse_w_no",
        "fuse_w_barge",
    )
    @classmethod
    def unit_interval(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError("value must be in [0, 1]")
        return value

    @field_validator("audio_silence_rms", "hotword_score", "backchannel_max_ms")
    @classmethod
    def non_negative(cls, value: float) -> float:
        if value < 0:
            raise ValueError("value must be >= 0")
        return value

    @field_validator("tts_speed", "tts_digit_speed", "tts_frustrated_speed")
    @classmethod
    def positive_speed(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("speed must be > 0")
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

    @field_validator(
        "clinic_name",
        "doctor_roster_path",
        "asr_stub_transcript",
        "faq_path",
        "calendar_db_path",
        "tts_voice",
        "tts_abbrev",
        "tts_warmup_phrases",
        "audio_retain_dir",
    )
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

    @field_validator("llm_backend")
    @classmethod
    def known_llm_backend(cls, value: str) -> str:
        stripped = value.strip()
        if stripped not in {"", "stub", "ollama"}:
            raise ValueError("llm_backend must be empty, stub, or ollama")
        return stripped

    @field_validator("tts_backend")
    @classmethod
    def known_tts_backend(cls, value: str) -> str:
        stripped = value.strip()
        if stripped not in {"", "stub", "piper", "kokoro"}:
            raise ValueError("tts_backend must be empty, stub, piper, or kokoro")
        return stripped

    @field_validator("audio_retain_s")
    @classmethod
    def retain_s_non_negative(cls, value: int) -> int:
        if value < 0:
            raise ValueError("audio_retain_s must be >= 0")
        return value

    @field_validator("eval_time_scale")
    @classmethod
    def virtual_or_realtime(cls, value: float) -> float:
        if value not in {0.0, 1.0}:
            raise ValueError("eval_time_scale must be 0 (virtual) or 1 (realtime)")
        return value

    @field_validator("eval_scenario_dir")
    @classmethod
    def eval_dir_non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("eval_scenario_dir must be non-empty")
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

    @model_validator(mode="after")
    def fuse_weights_sum_to_one(self) -> Self:
        total = (
            self.fuse_w_audio
            + self.fuse_w_text
            + self.fuse_w_repair
            + self.fuse_w_no
            + self.fuse_w_barge
        )
        if abs(total - 1.0) > 1e-6:
            raise ValueError("fuse weights must sum to 1.0")
        return self

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

    @property
    def backchannel_list(self) -> tuple[str, ...]:
        return tuple(part.strip() for part in self.backchannel_phrases.split(",") if part.strip())

    @property
    def tts_abbrev_set(self) -> frozenset[str]:
        return frozenset(
            part.strip().casefold() for part in self.tts_abbrev.split(",") if part.strip()
        )

    @property
    def tts_warmup_list(self) -> tuple[str, ...]:
        return tuple(part.strip() for part in self.tts_warmup_phrases.split(",") if part.strip())

    @property
    def tts_frame_samples(self) -> int:
        return self.ws_sample_rate_hz * self.tts_frame_ms // 1000

    @property
    def tts_pcm_bytes(self) -> int:
        return self.tts_frame_samples * 2


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Process settings, cached so the ASGI app and ``python -m server`` share one object."""
    return Settings()
