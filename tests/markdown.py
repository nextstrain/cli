import pytest
import re
from nextstrain.cli.markdown import parse, generate, embed_images
from pathlib import Path

testsdir = Path(__file__).resolve(strict = True).parent
topdir = testsdir.parent
datadir = testsdir / "data/markdown/"

def cases(pattern):
    for case in datadir.glob(pattern):
        yield pytest.param(
            case,
            id = str(case.relative_to(topdir)))


@pytest.mark.parametrize("case", cases("roundtrip-*.md"))
def pytest_markdown_roundtrip(case):
    markdown = case.read_text()
    assert generate(parse(markdown)) == markdown


@pytest.mark.parametrize("case", cases("embed-images-*.md"))
def pytest_markdown_embed_images(case):
    markdown, expected = split_input_expected(case.read_text())
    result = generate(embed_images(parse(markdown), case.parent))
    assert result == expected


def split_input_expected(markdown):
    return re.split(r'(?m)^---+8<---+$\n', markdown, maxsplit=1)
