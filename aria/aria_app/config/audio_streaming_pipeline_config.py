from gappler_common import config

_cfg = config("aria", "audio_streaming_pipeline")  # aria/aria_config.yaml


class AudioStreamingPipelineConfig:
    TRANSCRIPTION_MODEL: str = _cfg["transcription_model"]
    LLM_MODEL: str = _cfg["llm_model"]
    ITERATION_INTERVAL_SECONDS: int = _cfg["iteration_interval_s"]
    WHISPER_SAMPLE_RATE: int = 16_000  # what Whisper expects, not a setting
    MAX_BUFFER_SECONDS = _cfg["max_buffer_s"]
    STOP_KEYWORD = _cfg["stop_keyword"]
