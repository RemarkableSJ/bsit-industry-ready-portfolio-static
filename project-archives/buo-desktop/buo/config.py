from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = BASE_DIR / "assets"
DB_PATH = BASE_DIR / "buo.db"
CLOUD_CONFIG_PATH = BASE_DIR / "cloud_config.json"
LOCAL_CLOUD_DIR = BASE_DIR / "buo_cloud_sync"
APP_NAME = "Buo"
