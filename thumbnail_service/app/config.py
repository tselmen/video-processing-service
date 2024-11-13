from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    RABBITMQ_HOST: str = "localhost"
    ENCODED_DIR: str = "/encoded"
    THUMBNAIL_DIR: str = "/thumbnails"
    THUMBNAIL_SIZE: tuple = (320, 180)  # 16:9 aspect ratio

    class Config:
        env_file = ".env"


settings = Settings()
