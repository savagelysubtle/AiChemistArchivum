"""
Quick fix to properly initialize AIchemist Archivum with correct paths.
"""

import yaml

# Get the correct paths
from aichemist_archivum.config import CONFIG_DIR, DATA_DIR

# Create the proper config
config_content = {
    "data_dir": str(DATA_DIR),
    "database": {"type": "sqlite", "path": str(DATA_DIR / "archivum.db")},
    "logging": {"level": "INFO", "file": str(DATA_DIR / "logs" / "archivum.log")},
    "cache": {"enabled": True, "size_limit": "1GB"},
    "search": {
        "providers": ["regex", "similarity", "semantic"],
        "default_provider": "semantic",
    },
    "ingestion": {"batch_size": 50, "max_workers": 5},
    "versioning": {"auto_version": True, "change_threshold": 5.0},
}

# Create directories
print("📁 Creating directories...")
DATA_DIR.mkdir(parents=True, exist_ok=True)
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
(DATA_DIR / "versions").mkdir(exist_ok=True)
(DATA_DIR / "cache").mkdir(exist_ok=True)
(DATA_DIR / "temp").mkdir(exist_ok=True)
(DATA_DIR / "logs").mkdir(exist_ok=True)
(DATA_DIR / "search_index").mkdir(exist_ok=True)

print("✅ Directories created")

# Write config file
config_file = CONFIG_DIR / "config.yaml"
with open(config_file, "w") as f:
    yaml.dump(config_content, f, default_flow_style=False, sort_keys=False)

print(f"✅ Configuration file created: {config_file}")

# Initialize database
print("🗄️ Initializing database...")
import asyncio

from aichemist_archivum.services.database_service import DatabaseService


async def init_db():
    database_service = DatabaseService(db_path=DATA_DIR / "archivum.db")
    await database_service.initialize_schema()
    print("✅ Database initialized")


asyncio.run(init_db())

print("\n" + "=" * 60)
print("🎉 AIchemist Archivum initialized successfully!")
print("=" * 60)
print(f"\n📁 Data directory: {DATA_DIR}")
print(f"📁 Config directory: {CONFIG_DIR}")
print(f"🗄️ Database: {DATA_DIR / 'archivum.db'}")
print(f"⚙️  Config file: {config_file}")
print("\n📚 Try: python start.py config show")
