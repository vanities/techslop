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

    # Configurable Reddit subreddits (comma-separated)
    reddit_subreddits: str = "technology,programming,machinelearning,artificial,LocalLLaMA"

    # 4chan keyword filters (comma-separated)
    fourchan_keywords: str = "AI,LLM,GPU,linux,rust,python,open source,self-hosted,homelab,programming"

    # X/Twitter search keywords (comma-separated)
    x_keywords: str = "AI breakthrough,new programming language,open source release,tech layoffs,GPU,LLM"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
