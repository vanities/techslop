"""Tests for techslop.config."""

from techslop.config import Settings


def test_defaults():
    s = Settings(openai_api_key="test")
    assert s.tts_provider == "edge"
    assert s.database_path == "techslop.db"
    assert s.output_dir == "output"


def test_reddit_subreddits_parsing():
    s = Settings(reddit_subreddits="foo,bar,baz")
    subs = [x.strip() for x in s.reddit_subreddits.split(",")]
    assert subs == ["foo", "bar", "baz"]


def test_fourchan_keywords_parsing():
    s = Settings(fourchan_keywords="AI,LLM,GPU")
    kw = [x.strip() for x in s.fourchan_keywords.split(",")]
    assert kw == ["AI", "LLM", "GPU"]
