"""
HTTP requests and responses with consistent defaults for us.
"""
import requests

# Import these for re-export for better drop-in compatibility
# with existing callers.
import requests.auth as auth                                        # noqa: F401
import requests.exceptions as exceptions                            # noqa: F401
import requests.utils as utils                                      # noqa: F401
from requests import PreparedRequest, RequestException, Response    # noqa: F401


class Session(requests.Session):
    def __init__(self):
        super().__init__()

        # XXX TODO: Set our own defaults here.


def get(*args, **kwargs) -> Response:
    with Session() as session:
        return session.get(*args, **kwargs)

def post(*args, **kwargs) -> Response:
    with Session() as session:
        return session.post(*args, **kwargs)
