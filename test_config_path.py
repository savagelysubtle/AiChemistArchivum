"""Test script to verify config path changes."""
from backend.src.aichemist_archivum.config.loader.config_loader import get_codex_config

cfg = get_codex_config()
print(f'Config sources: {cfg.get_loaded_sources()}')
print(f'Data dir from config: {cfg.get("data_dir")}')
print(f'Database path: {cfg.get("database.path")}')
print(f'\n✅ Config loading successful!')


