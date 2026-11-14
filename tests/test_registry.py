import pytest

from atproto_lexicons_tools.core.registry import Service, find_owner, load_services, parse_services
from atproto_lexicons_tools.core.sdk import get_sdk_nsids


def test_service_owns_the_nsids_under_its_reversed_domain() -> None:
    service = Service('teal.fm', ())

    assert service.nsid_prefix == 'fm.teal.'
    assert service.owns('fm.teal.feed.play')
    assert not service.owns('fm.tealish.feed.play')


def test_owner_is_the_most_specific_service() -> None:
    services = [Service('example.com', ()), Service('labs.example.com', ())]

    owner = find_owner('com.example.labs.thing', services)

    assert owner is not None
    assert owner.domain == 'labs.example.com'
    assert find_owner('org.other.thing', services) is None


def test_duplicate_services_are_rejected() -> None:
    with pytest.raises(ValueError, match=r'teal\.fm'):
        parse_services({'services': [{'domain': 'teal.fm'}, {'domain': 'teal.fm', 'dids': []}]})


def test_registry_file_is_valid() -> None:
    services = load_services()

    assert services
    assert all(service.domain == service.domain.lower() for service in services)


def test_sdk_nsids_are_read_from_the_installed_sdk() -> None:
    assert 'app.bsky.feed.post' in get_sdk_nsids()
