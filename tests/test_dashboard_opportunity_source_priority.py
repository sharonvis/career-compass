"""Dashboard source preference preserves the service's relative ranking."""
from unittest.mock import Mock

import pytest

from services import opportunity_service
from test_opportunity_application_ui import store, page, ranked


@pytest.mark.parametrize("sources,expected", [
    ([False, False, True, False, True], [0, 1, 3]),
    ([True, False, True, False, True], [1, 3, 0]),
    ([True, True, True, True], [0, 1, 2]),
    ([True, False, False, True, False, False], [1, 2, 4]),
    ([True, False], [1, 0]),
    ([], []),
])
def test_dashboard_live_first_selection(store, monkeypatch, sources, expected):
    template = ranked(store)[0]
    candidates = [dict(template, opportunity_id=100 + i,
                       title=f"Source priority listing {i}",
                       is_seeded=seeded, source="seed" if seeded else "serpapi")
                  for i, seeded in enumerate(sources)]
    original = [dict(row) for row in candidates]
    read = Mock(return_value=candidates)
    monkeypatch.setattr(opportunity_service, "get_ranked_opportunities", read)
    at = page(store, "Dashboard")
    assert not at.exception
    read.assert_called_once()
    assert read.call_args.args[1:] == (store["uid"], store["cid"])
    assert not read.call_args.kwargs  # Read all rankable candidates before selecting three.
    cards = next(element.value for element in at.markdown
                 if 'class="cc-opps-grid"' in element.value or 'class="cc-opps-empty"' in element.value)
    for i in range(len(candidates)):
        assert (f"Source priority listing {i}" in cards) == (i in expected)
    positions = [cards.index(f"Source priority listing {i}") for i in expected]
    assert positions == sorted(positions)
    assert candidates == original
