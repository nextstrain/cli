from nextstrain.cli import make_parser


def pytest_build_download_options():
    parser = make_parser()

    opts = parser.parse_args(["build", "."])
    assert opts.download is True

    opts = parser.parse_args(["build", "--no-download", "."])
    assert opts.download is False

    opts = parser.parse_args(["build", "--download", "x", "."])
    assert opts.download == ["x"]

    opts = parser.parse_args(["build", "--download", "x", "--download", "y", "."])
    assert opts.download == ["x", "y"]

    opts = parser.parse_args(["build", "--exclude-from-download", "z", "."])
    assert opts.download == ["!z"]

    opts = parser.parse_args(["build", "--exclude-from-download", "z", "--exclude-from-download", "a", "."])
    assert opts.download == ["!z", "!a"]

    opts = parser.parse_args(["build", "--download", "y", "--exclude-from-download", "z", "."])
    assert opts.download == ["y", "!z"]

    opts = parser.parse_args(["build", "--download", "y", "--download", "!z", "."])
    assert opts.download == ["y", "!z"]
