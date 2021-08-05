from pathlib import Path
from nextstrain.cli.remote.nextstrain_dot_org import organize_files


def pytest_organize_files():
    assert (
        organize_files({
            Path("ncov_open_global.json"),
            Path("ncov_open_global_root-sequence.json"),
            Path("ncov_open_global_tip-frequencies.json"),
            Path("ncov_open_north-america.json"),
            Path("ncov_open_north-america_root-sequence.json"),
            Path("ncov_open_north-america_tip-frequencies.json"),
            Path("ncov_gisaid_global.json"),
        })
        ==
        (
            {
                "ncov/open/global": {
                    "application/vnd.nextstrain.dataset.main+json": Path("ncov_open_global.json"),
                    "application/vnd.nextstrain.dataset.root-sequence+json": Path("ncov_open_global_root-sequence.json"),
                    "application/vnd.nextstrain.dataset.tip-frequencies+json": Path("ncov_open_global_tip-frequencies.json"),
                },
                "ncov/open/north-america": {
                    "application/vnd.nextstrain.dataset.main+json": Path("ncov_open_north-america.json"),
                    "application/vnd.nextstrain.dataset.root-sequence+json": Path("ncov_open_north-america_root-sequence.json"),
                    "application/vnd.nextstrain.dataset.tip-frequencies+json": Path("ncov_open_north-america_tip-frequencies.json"),
                },
                "ncov/gisaid/global": {
                    "application/vnd.nextstrain.dataset.main+json": Path("ncov_gisaid_global.json"),
                },
            },
            {},
            [],
        )
    )

    assert (
        organize_files({
            Path("auspice/A.json"),
            Path("auspice/A_root-sequence.json"),
            Path("auspice/A_tip-frequencies.json"),
            Path("auspice/A_B.json"),
            Path("auspice/A_B_root-sequence.json"),
            Path("narratives/hello_world.md"),
            Path("narratives/hello_universe.md"),
            Path("group-overview.md"),
            Path("group-logo.png"),
        })
        ==
        (
            {
                "A": {
                    "application/vnd.nextstrain.dataset.main+json": Path("auspice/A.json"),
                    "application/vnd.nextstrain.dataset.root-sequence+json": Path("auspice/A_root-sequence.json"),
                    "application/vnd.nextstrain.dataset.tip-frequencies+json": Path("auspice/A_tip-frequencies.json"),
                },
                "A/B": {
                    "application/vnd.nextstrain.dataset.main+json": Path("auspice/A_B.json"),
                    "application/vnd.nextstrain.dataset.root-sequence+json": Path("auspice/A_B_root-sequence.json"),
                },
            },
            {
                "hello/world": {
                    "text/vnd.nextstrain.narrative+markdown": Path("narratives/hello_world.md"),
                },
                "hello/universe": {
                    "text/vnd.nextstrain.narrative+markdown": Path("narratives/hello_universe.md"),
                },
            },
            [
                Path("group-logo.png"),
                Path("group-overview.md"),
            ],
        )
    )

    assert (
        organize_files({
            Path("A_tree.json"),
            Path("A_meta.json"),
            Path("A_tip-frequencies.json"),
            Path("A_B.md"),
            Path("A_C.md"),
        })
        ==
        (
            {
                "A": {
                    "application/vnd.nextstrain.dataset.tip-frequencies+json": Path("A_tip-frequencies.json"),
                },
            },
            {
                "A/B": {
                    "text/vnd.nextstrain.narrative+markdown": Path("A_B.md"),
                },
                "A/C": {
                    "text/vnd.nextstrain.narrative+markdown": Path("A_C.md"),
                },
            },
            [
                Path("A_meta.json"),
                Path("A_tree.json"),
            ],
        )
    )
