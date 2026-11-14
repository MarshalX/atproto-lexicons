import httpx

_API_URL = 'https://api.github.com/repos/{repository}'
_TIMEOUT_SECONDS = 30
_HEADERS = {'Accept': 'application/vnd.github+json', 'User-Agent': 'atproto-lexicons'}


def fetch_stars(repository: str, token: str = '', client: httpx.Client | None = None) -> int:
    """Ask GitHub how many stars a repository has.

    Without a token GitHub allows 60 requests an hour from one address, which shared CI runners run out of.

    Raises:
        httpx.HTTPError: GitHub could not be reached or refused the request.
    """
    headers = {**_HEADERS, 'Authorization': f'Bearer {token}'} if token else _HEADERS
    url = _API_URL.format(repository=repository)

    response = (client or httpx).get(url, headers=headers, timeout=_TIMEOUT_SECONDS, follow_redirects=True)
    response.raise_for_status()

    return int(response.json()['stargazers_count'])
