from logging import currentframe
from pathlib import Path

import pytest

from sbumed_predictions_to_graph import State


def test_min(tmpdir: Path):
    out_path = tmpdir / "test.ttl"
    state = State(
        path=out_path,
        creator="Me",
        name="test-output",
        creator_orcid_id="https://orcid.org/0000-0000-0000-0000",
        description="This is just a test.",
        slide_path=__file__,
        github_url="foobar.com",
    )
    state.add(cell_type="lymphocyte", probability=0.80, polygon_coords=[(1, 1)])
    state.write()
    assert out_path.exists()


def test_add_point(tmpdir: Path):
    out_path = tmpdir / "test.ttl"
    state = State(
        path=out_path,
        creator="Me",
        name="test-output",
        description="This is just a test.",
        slide_path=__file__,
        github_url="foobar.com",
    )
    with pytest.raises(ValueError):
        state.add(
            cell_type="lymphocyte",
            probability=0.80,
            polygon_coords=[(1, 1)],
            point=[1, 2],
        )
    with pytest.raises(ValueError):
        state.add(
            cell_type="lymphocyte",
            probability=0.80,
            point=[1, 2, 3],
        )
    with pytest.raises(ValueError):
        state.add(
            cell_type="lymphocyte",
            probability=0.80,
            point=[1],
        )
