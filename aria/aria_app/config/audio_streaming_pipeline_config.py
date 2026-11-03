from gappler_common import config

_cfg = config("aria", "audio_streaming_pipeline")  # aria/aria_config.yaml


class AudioStreamingPipelineConfig:
    TRANSCRIPTION_MODEL: str = _cfg["transcription_model"]
    LLM_MODEL: str = _cfg["llm_model"]
    WHISPER_PRECISION: str = _cfg["whisper_precision"]
    WHISPER_BEAM_SIZE: int = _cfg["whisper_beam_size"]
    LLM_PRECISION: str = _cfg["llm_precision"]
    LLM_MAX_NEW_TOKENS: int = _cfg["llm_max_new_tokens"]
    ITERATION_INTERVAL_SECONDS: float = _cfg["iteration_interval_s"]
    WHISPER_SAMPLE_RATE: int = 16_000  # what Whisper expects, not a setting
    MAX_BUFFER_SECONDS = _cfg["max_buffer_s"]
    END_OF_SPEECH_SILENCE_SECONDS: float = _cfg["end_of_speech_silence_s"]
    STOP_KEYWORD = _cfg["stop_keyword"]
    RELEASE_PHRASES: list = _cfg["release_phrases"]
