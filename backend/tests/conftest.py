"""Shared pytest configuration: database tests run only when PostgreSQL is configured."""

import os

import pytest

TEST_DATABASE_URL = os.environ.get("AGILESIM_TEST_DATABASE_URL")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if TEST_DATABASE_URL:
        return
    skip = pytest.mark.skip(reason="AGILESIM_TEST_DATABASE_URL is not set")
    for item in items:
        if "db" in item.keywords:
            item.add_marker(skip)
