"""
Config Manager - Quản lý cấu hình ứng dụng
"""

import json
import os
from pathlib import Path
from typing import Any, Optional


class ConfigManager:
    """Quản lý cấu hình từ file JSON"""

    def __init__(self, config_path: str = "config/config.json"):
        self.config_path = Path(config_path)
        self.config = self._load_config()

    def _load_config(self) -> dict:
        """Load config từ file JSON"""
        if not self.config_path.exists():
            # Tạo config mặc định nếu chưa có
            example_path = self.config_path.parent / "config.example.json"
            if example_path.exists():
                print(f"⚠️  Chưa có file config. Copy từ {example_path}")
                print(f"   Chạy: cp {example_path} {self.config_path}")
            return self._default_config()

        with open(self.config_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _default_config(self) -> dict:
        """Config mặc định"""
        return {
            "google_sheets": {
                "spreadsheet_id": "",
                "sheet_name": "Products",
                "credentials_file": "config/credentials.json"
            },
            "grok": {
                "base_url": "https://grok.com",
                "imagine_url": "https://grok.com/imagine",
                "tokens_file": "config/grok_tokens.json"
            },
            "chrome": {
                "profile_path": "",
                "profile_name": "Default"
            },
            "video": {
                "output_dir": "outputs",
                "format": "mp4",
                "resolution": {"width": 1080, "height": 1920},
                "fps": 30,
                "duration_per_image": 3,
                "transition_duration": 0.5
            },
            "products": {
                "images_dir": "products",
                "supported_formats": [".jpg", ".jpeg", ".png", ".webp"]
            }
        }

    def get(self, key: str, default: Any = None) -> Any:
        """Lấy giá trị config theo key (hỗ trợ dot notation)"""
        keys = key.split(".")
        value = self.config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default

        return value

    def set(self, key: str, value: Any) -> None:
        """Set giá trị config"""
        keys = key.split(".")
        config = self.config

        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]

        config[keys[-1]] = value

    def save(self) -> None:
        """Lưu config ra file"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2, ensure_ascii=False)
        print(f"✅ Đã lưu config: {self.config_path}")


# Singleton instance
_config_instance: Optional[ConfigManager] = None


def get_config(config_path: str = "config/config.json") -> ConfigManager:
    """Lấy config instance (singleton)"""
    global _config_instance
    if _config_instance is None:
        _config_instance = ConfigManager(config_path)
    return _config_instance
