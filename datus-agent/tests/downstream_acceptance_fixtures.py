import sqlite3
from pathlib import Path

import yaml

TEST_CONF_DIR = Path(__file__).parent / "conf"
_BIRD_DEV_DATABASES = Path("benchmark/bird/dev_20240627/dev_databases")


def _sqlite_path_to_uri(path: Path) -> str:
    return f"sqlite:///{path.resolve().as_posix()}"


def _create_sqlite_db(path: Path, schema_sql: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()


def create_minimal_bird_sqlite_fixture(tmp_root: Path) -> Path:
    """Create the small BIRD-shaped SQLite fixture required by CI acceptance tests."""
    dev_root = Path(tmp_root) / _BIRD_DEV_DATABASES
    california = dev_root / "california_schools" / "california_schools.sqlite"
    cards = dev_root / "card_games" / "card_games.sqlite"

    _create_sqlite_db(
        california,
        """
        CREATE TABLE IF NOT EXISTS schools (
            CDSCode TEXT PRIMARY KEY,
            County TEXT,
            School TEXT,
            City TEXT
        );
        CREATE TABLE IF NOT EXISTS frpm (
            CDSCode TEXT,
            County TEXT,
            School TEXT,
            "Enrollment (K-12)" INTEGER,
            "Free Meal Count (K-12)" INTEGER,
            "Percent (%) Eligible Free (K-12)" REAL
        );
        CREATE TABLE IF NOT EXISTS satscores (
            CDSCode TEXT,
            sname TEXT,
            NumTstTakr INTEGER,
            AvgScrRead INTEGER,
            AvgScrMath INTEGER,
            AvgScrWrite INTEGER
        );
        INSERT OR IGNORE INTO schools (CDSCode, County, School, City)
        VALUES ('0000001', 'Alameda', 'Fixture High', 'Oakland');
        INSERT INTO frpm (
            CDSCode,
            County,
            School,
            "Enrollment (K-12)",
            "Free Meal Count (K-12)",
            "Percent (%) Eligible Free (K-12)"
        )
        SELECT '0000001', 'Alameda', 'Fixture High', 100, 42, 42.0
        WHERE NOT EXISTS (SELECT 1 FROM frpm WHERE CDSCode = '0000001');
        INSERT INTO satscores (CDSCode, sname, NumTstTakr, AvgScrRead, AvgScrMath, AvgScrWrite)
        SELECT '0000001', 'Fixture High', 10, 500, 510, 505
        WHERE NOT EXISTS (SELECT 1 FROM satscores WHERE CDSCode = '0000001');
        """,
    )
    _create_sqlite_db(
        cards,
        """
        CREATE TABLE IF NOT EXISTS cards (id TEXT PRIMARY KEY, name TEXT);
        CREATE TABLE IF NOT EXISTS legalities (card_id TEXT, format TEXT, status TEXT);
        CREATE TABLE IF NOT EXISTS set_translations (set_id TEXT, language TEXT, name TEXT);
        CREATE TABLE IF NOT EXISTS foreign_data (card_id TEXT, language TEXT, name TEXT);
        CREATE TABLE IF NOT EXISTS rulings (card_id TEXT, published_at TEXT, comment TEXT);
        CREATE TABLE IF NOT EXISTS sets (id TEXT PRIMARY KEY, name TEXT);
        INSERT OR IGNORE INTO cards (id, name) VALUES ('card_1', 'Fixture Card');
        INSERT OR IGNORE INTO sets (id, name) VALUES ('set_1', 'Fixture Set');
        """,
    )
    return dev_root


def write_acceptance_config_with_local_bird(tmp_root: Path) -> Path:
    """Write a temp acceptance config whose BIRD datasources point at local fixtures."""
    dev_root = create_minimal_bird_sqlite_fixture(tmp_root)
    config_path = Path(tmp_root) / "agent.yml"
    with open(TEST_CONF_DIR / "agent.yml", "r", encoding="utf-8") as file:
        raw = yaml.safe_load(file)

    agent = raw["agent"]
    agent["home"] = str(Path(tmp_root) / ".datus_home")
    agent["project_root"] = str(Path(tmp_root) / "workspace")
    agent["autocomplete"] = {
        "background_sync_enabled": False,
        "background_sync_on_startup": False,
        "background_sync_include_values": False,
    }
    datasources = agent["services"]["datasources"]
    datasources["bird_sqlite"]["path_pattern"] = str(dev_root / "**/*.sqlite")
    datasources["bird_school"]["uri"] = _sqlite_path_to_uri(
        dev_root / "california_schools" / "california_schools.sqlite"
    )

    config_path.parent.mkdir(parents=True, exist_ok=True)
    with open(config_path, "w", encoding="utf-8") as file:
        yaml.safe_dump(raw, file, allow_unicode=True, sort_keys=False)
    return config_path
