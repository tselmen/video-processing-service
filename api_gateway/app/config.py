from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    UPLOAD_DIR: str = "/uploads"
    ENCODED_DIR: str = "/encoded"
    THUMBNAIL_DIR: str = "/thumbnails"
    DATABASE_URL: str = "mysql+aiomysql://user:password@localhost/video_db"
    RABBITMQ_HOST: str = "localhost"
    MYSQL_HOST: str = "localhost"
    MYSQL_USER: str = "user"
    MYSQL_PASSWORD: str = "password"
    MYSQL_DATABASE: str = "video_db"

    class Config:
        env_file = ".env"


settings = Settings()
