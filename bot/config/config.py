from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_ignore_empty=True)

    API_ID: int
    API_HASH: str

    MIN_AVAILABLE_COINS: int = 150
    SLEEP_BY_MIN_COINS_TIME: int = 300

    AUTO_BUY_ENERGY_BOOST: bool = False
    MAX_ENERGY_BOOST: int = 10
    AUTO_BUY_SPEED_BOOST: bool = False
    MAX_SPEED_BOOST: int = 10
    AUTO_BUY_CLICK_BOOST: bool = False
    MAX_CLICK_BOOST: int = 10

    ACTIVATE_DAILY_ENERGY: bool = True
    ACTIVATE_DAILY_TURBO: bool = True

    SLEEP_BY_MIN_COINS: bool = True

    RANDOM_CLICKS_COUNT: list[int] = [50, 200]
    SLEEP_BETWEEN_CLICK: list[int] = [10, 25]


settings = Settings()
