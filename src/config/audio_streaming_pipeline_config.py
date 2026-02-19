class AudioStreamingPipelineConfig:
    TRANSCRIPTION_MODEL: str = "small.en"
    LLM_MODEL: str = "Qwen/Qwen2.5-0.5B-Instruct"
    ITERATION_INTERVAL_SECONDS: int = 1
    WHISPER_SAMPLE_RATE: int = 16_000
    MAX_BUFFER_SECONDS = 100
    STOP_KEYWORD = "end"
