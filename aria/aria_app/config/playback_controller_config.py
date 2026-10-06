from gappler_common import config

_cfg = config("aria", "playback_controller")  # aria/aria_config.yaml


class PlaybackControllerConfig:
    PLAYBACK_SPEED: float = _cfg["playback_speed"]
