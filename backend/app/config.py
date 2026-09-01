from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_name: str = "GPUFlow"
    debug: bool = False
    
    class Config:
        env_file = ".env"

settings = Settings()
