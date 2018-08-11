from . import docker

all_runners = [
    docker,
]


def replace_ellipsis(items, elided_items):
    """
    Replaces any Ellipsis items (...) in a list, if any, with the items of a
    second list.
    """
    return [
        y for x in items
          for y in (elided_items if x is ... else [x])
    ]
