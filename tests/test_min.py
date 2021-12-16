from pathlib import Path

import pytest

from sbumed_predictions_to_graph import State


def is_gzipped(path):
    with open(path, "rb") as f:
        return f.read(3) == b"\x1f\x8b\x08"


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
    assert not is_gzipped(out_path)


def test_min_gz(tmpdir: Path):
    out_path = tmpdir / "test.ttl.gz"
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
    assert is_gzipped(out_path)


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


def test_fail_on_slide_and_slide_md5(tmpdir: Path):
    with pytest.raises(ValueError):
        # No slide path and no slide md5
        State(
            path="f.ttl",
            creator="Me",
            name="test-output",
            description="This is just a test.",
            github_url="foobar.com",
        )

    with pytest.raises(ValueError):
        # both slide path and slide md5
        State(
            path="f.ttl",
            creator="Me",
            name="test-output",
            description="This is just a test.",
            github_url="foobar.com",
            slide_path=__file__,
            slide_md5="m5fds9u155124lfkj",
        )
