def get_sdk_nsids() -> frozenset[str]:
    from atproto_client import models  # noqa: PLC0415

    ids = models.ids
    return frozenset(getattr(ids, alias) for alias in vars(type(ids)) if not alias.startswith('_'))
