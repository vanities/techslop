from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    openai_api_key: str = ""
    tts_provider: str = "edge"
    elevenlabs_api_key: str = ""
    youtube_client_id: str = ""
    youtube_client_secret: str = ""
    youtube_refresh_token: str = ""
    database_path: str = "techslop.db"
    output_dir: str = "output"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
