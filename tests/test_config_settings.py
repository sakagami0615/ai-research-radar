from pathlib import Path

from ai_research_radar.config.settings import load_runtime_config, load_scoring_config, load_source_configs, load_yaml_config


def test_load_yaml_config_reads_sources():
    config = load_yaml_config(Path("config/sources.yaml"))

    assert "sources" in config
    assert config["sources"]["pypi"]["collection_mode"] == "keyword_limited"


def test_load_source_configs_includes_initial_public_sources():
    configs = load_source_configs(Path("config/sources.yaml"))
    names = {config.name for config in configs if config.enabled}

    assert {"github", "huggingface", "pypi", "npm", "hackernews", "qiita", "zenn", "arxiv", "openalex", "official_blogs"} <= names
    assert all(not config.auth_required for config in configs if config.name in names)


def test_load_scoring_and_runtime_config():
    scoring = load_scoring_config(Path("config/scoring.yaml"))
    runtime = load_runtime_config(Path("config/runtime.yaml"))

    assert scoring["hot_selection"]["max_limit"] == 5
    assert runtime["output"]["data_dir"] == "data"
