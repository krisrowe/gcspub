import json
import os
from pathlib import Path

# Use standard XDG config home or fallback
XDG_CONFIG_HOME = os.getenv("XDG_CONFIG_HOME", os.path.join(os.path.expanduser("~"), ".config"))
CONFIG_DIR = Path(XDG_CONFIG_HOME) / "gcspub"
CONFIG_FILE = CONFIG_DIR / "config.json"

class ConfigManager:
    @staticmethod
    def load():
        if not CONFIG_FILE.exists():
            return {}
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def save(config_data):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config_data, f, indent=4)

    @staticmethod
    def get_email():
        return ConfigManager.load().get('email')

    @staticmethod
    def set_email(email):
        config = ConfigManager.load()
        config['email'] = email
        ConfigManager.save(config)

    @staticmethod
    def get_bucket():
        return ConfigManager.load().get('bucket')

    @staticmethod
    def set_bucket(bucket):
        config = ConfigManager.load()
        config['bucket'] = bucket
        ConfigManager.save(config)

    @staticmethod
    def get_project():
        return ConfigManager.load().get('project')

    @staticmethod
    def set_project(project):
        config = ConfigManager.load()
        config['project'] = project
        ConfigManager.save(config)
