from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    RABBITMQ_HOST: str = "localhost"
    UPLOAD_DIR: str = "/uploads"
    ENCODED_DIR: str = "/encoded"

    class Config:
        env_file = ".env"


settings = Settings()
