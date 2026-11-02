"""Offline tests for realestate_com_au/api.py's page routing (fetch_page is
replaced by a stub that serves fixtures).

    python -m pytest realestate_com_au/test_api.py -q
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from realestate_com_au import api  # noqa: E402
from realestate_com_au.fetch import RealestateNotFound  # noqa: E402

FX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def fixture(name):
    with open(os.path.join(FX, name), encoding="utf-8") as f:
        return f.read()


def test_listing_id_falls_back_to_the_project_page(monkeypatch):
    calls = []

    def fake_fetch(path, label):
        calls.append(path)
        if path == "/project/600045596":
            return fixture("project_600045596.html")
        raise RealestateNotFound(f"{label} not found")

    monkeypatch.setattr(api, "fetch_page", fake_fetch)
    record = api._listing_page("600045596")
    assert calls == ["/property-600045596", "/project/600045596"]
    assert record["is_project"] and record["name"] == "The Manors of Mosman Retirement Village"


def test_listing_id_found_first_try(monkeypatch):
    calls = []

    def fake_fetch(path, label):
        calls.append(path)
        return fixture("listing_buy_152216904.html")

    monkeypatch.setattr(api, "fetch_page", fake_fetch)
    assert api._listing_page("152216904")["id"] == "152216904"
    assert calls == ["/property-152216904"]


def test_unknown_id_is_still_not_found(monkeypatch):
    def fake_fetch(path, label):
        raise RealestateNotFound(f"{label} not found")

    monkeypatch.setattr(api, "fetch_page", fake_fetch)
    with pytest.raises(RealestateNotFound):
        api._listing_page("999999999")
