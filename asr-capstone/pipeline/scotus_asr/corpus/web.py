"""Fetching pages from the Court's site without being a nuisance.

Building the corpus means roughly 2,200 requests to a government web server that
exists to serve the public, not to feed a research project. Nothing here is
required to make the download work - it is here so the download is a reasonable
thing to do.

Three things:

**A gap between requests.** One per second by default. The whole corpus is about
35 minutes of waiting spread across a job that takes days anyway, so the polite
setting costs effectively nothing.

**An identifier that says who this is.** The Court's site refuses anything that
does not look like a browser, so the identifier has to be browser-shaped, but it
also names the project. An administrator reading the access log can tell what
this is and, if it is a problem, who to tell.

**Backing off rather than hammering.** A server that returns 429 or 503 is asking
for less traffic. Retrying immediately is how a polite client becomes an attack.
"""

from __future__ import annotations

import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field

#: Browser-shaped, because the Court's site serves a short HTML error page to
#: anything else - which then lands on disk named `.mp3` and fails much later
#: somewhere unrelated. The trailing note is so the access log says who this is.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "SCOTUS-ASR-capstone/1.0 (academic research; contact via GitHub)"
)

#: Statuses that mean "try later", as opposed to "this will never work".
RETRY_STATUSES = frozenset({408, 425, 429, 500, 502, 503, 504})


@dataclass
class PoliteSession:
    """An HTTP client that waits between requests and backs off when asked.

    Attributes:
        min_interval: Seconds to leave between the end of one request and the
            start of the next.
        max_attempts: How many times to try before giving up on one address.
        backoff: Seconds to wait after the first failure. Doubles each time.
        timeout: Seconds to wait for the server.
        user_agent: What to identify as.
        requests_made: Counter, so a run can report how much traffic it caused.
    """

    min_interval: float = 1.0
    max_attempts: int = 4
    backoff: float = 2.0
    timeout: float = 60.0
    user_agent: str = USER_AGENT
    requests_made: int = field(default=0, init=False)
    _last_request: float = field(default=0.0, init=False)

    def _wait_turn(self) -> None:
        """Sleep until enough time has passed since the last request."""
        elapsed = time.monotonic() - self._last_request
        if self._last_request and elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)

    def open(self, url: str):
        """Fetch one address, retrying transient failures.

        Args:
            url: What to fetch.

        Returns:
            The open response. The caller is responsible for reading and closing
            it, which is what lets a large file stream to disk rather than into
            memory.

        Raises:
            urllib.error.HTTPError: For a status that will not improve by
                retrying, such as 404, or after the last attempt.
            urllib.error.URLError: If the server could not be reached at all.
        """
        request = urllib.request.Request(url, headers={"User-Agent": self.user_agent})
        delay = self.backoff

        for attempt in range(1, self.max_attempts + 1):
            self._wait_turn()
            try:
                response = urllib.request.urlopen(request, timeout=self.timeout)
                self.requests_made += 1
                self._last_request = time.monotonic()
                return response
            except urllib.error.HTTPError as error:
                self._last_request = time.monotonic()
                if error.code not in RETRY_STATUSES or attempt == self.max_attempts:
                    raise
                # A server that says how long to wait knows better than we do.
                stated = error.headers.get("Retry-After") if error.headers else None
                time.sleep(float(stated) if stated and stated.isdigit() else delay)
                delay *= 2
            except urllib.error.URLError:
                self._last_request = time.monotonic()
                if attempt == self.max_attempts:
                    raise
                time.sleep(delay)
                delay *= 2

        raise RuntimeError("unreachable")

    def text(self, url: str) -> str:
        """Fetch one address and return it as text."""
        with self.open(url) as response:
            return response.read().decode("utf-8", "replace")
