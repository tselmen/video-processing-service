from pydantic_settings import BaseSettings
from typing import Dict


class VideoPreset:
    def __init__(self, width: int, height: int, bitrate: str):
        self.width = width
        self.height = height
        self.bitrate = bitrate


class Settings(BaseSettings):
    RABBITMQ_HOST: str = "localhost"
    MYSQL_HOST: str = "localhost"
    MYSQL_USER: str = "user"
    MYSQL_PASSWORD: str = "password"
    MYSQL_DATABASE: str = "video_db"
    UPLOAD_DIR: str = "/uploads"
    ENCODED_DIR: str = "/encoded"

    # Video processing presets
    VIDEO_PRESETS: Dict[str, VideoPreset] = {
        "360p": VideoPreset(640, 360, "800k"),
        "480p": VideoPreset(854, 480, "1500k"),
        "720p": VideoPreset(1280, 720, "2500k"),
        "1080p": VideoPreset(1920, 1080, "4000k"),
    }

    class Config:
        env_file = ".env"


settings = Settings()
