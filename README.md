<p align="center">
    <a href="https://lex.atproto.blue">
        <picture>
            <source media="(prefers-color-scheme: dark)" srcset="https://lex.atproto.blue/images/banner-dark.png">
            <img alt="lex.atproto.blue: third-party lexicons, ready to import. Atmosphere lexicons for the atproto Python SDK." src="https://lex.atproto.blue/images/banner.png" width="800">
        </picture>
    </a>
</p>

<p align="center">
    <b>Typed models and client methods for third-party lexicons, rebuilt daily</b>
    <br>
    <a href="https://lex.atproto.blue">
        Catalog
    </a>
    •
    <a href="https://atproto.blue">
        SDK documentation
    </a>
    •
    <a href="https://pypi.org/project/atproto-lexicons/">
        PyPI
    </a>
    •
    <a href="https://discord.gg/PCyVJXU9jN">
        Discord Bluesky API
    </a>
</p>

Python models and clients for third-party AT Protocol lexicons, generated for the [atproto SDK](https://github.com/MarshalX/atproto).

The SDK ships the Bluesky and core atproto lexicons. Everything else on the network is someone's own lexicon: Teal.fm plays, Tangled repos, Leaflet documents, and so on. This package has them generated ahead of time, so you do not have to download schemas and run codegen yourself.

Browse the services and their lexicons at [lex.atproto.blue](https://lex.atproto.blue), or see [SUPPORTED.md](https://github.com/MarshalX/atproto-lexicons/blob/main/SUPPORTED.md) for the plain list.

## Install

```bash
pip install atproto-lexicons
```

It needs Python 3.9 or newer and installs the atproto SDK (0.0.75 or newer) with it.

## Use

`AtprotoLexiconsClient` is the SDK's `Client` with the extra namespaces attached. Everything the SDK client does still works.

```python
from atproto_lexicons import models
from atproto_lexicons.client import AtprotoLexiconsClient

client = AtprotoLexiconsClient()
client.login('handle.example.com', 'app-password')

# a third-party record
play = models.FmTealFeedPlay.Record(track_name='Song', played_time=client.get_current_time_iso())
client.fm.teal.feed.play.create(client.me.did, play)

# the namespaces of the SDK are still there
client.app.bsky.feed.post.create(
    client.me.did, models.AppBskyFeedPost.Record(text='hi', created_at=client.get_current_time_iso())
)
```

To add the namespaces to a client you already have:

```python
from atproto import Client
from atproto_lexicons.client import attach_namespaces

client = Client()
attach_namespaces(client)
```

Async works the same way through `atproto_lexicons.async_client`.

The exact client path and model name of every lexicon are in the [catalog](https://lex.atproto.blue): find the service, open it, and copy them.

## Things to know

- **Versions are dates.** A release is a snapshot of what the services published that day. A service can change its schema at any time, and the next release follows it. Pin the version if you need stability.
- **Not every lexicon is valid.** Invalid ones are skipped, and a reference to something that does not exist becomes an untyped field. [SUPPORTED.md](https://github.com/MarshalX/atproto-lexicons/blob/main/SUPPORTED.md) shows where that happened.
- **Lexicons the SDK already ships are left to the SDK.** They are not generated a second time: import their models from `atproto`, as the catalog shows for each of them.
- **This project is not affiliated with the listed services.** The schemas belong to their authors. If you run one of them and want it removed or fixed, write in the [discussions of the atproto SDK](https://github.com/MarshalX/atproto/discussions).

## Getting help

Questions, bug reports, wrong models and missing services all go to the [discussions of the atproto SDK](https://github.com/MarshalX/atproto/discussions). The SDK itself is documented at [atproto.blue](https://atproto.blue).

## Contributing

Contributions of all sizes are welcome. The most useful one is a new service. [CONTRIBUTING.md](https://github.com/MarshalX/atproto-lexicons/blob/main/CONTRIBUTING.md) explains how to add one, how the package is built and how to work on the tooling and the website.

## License

MIT. See [LICENSE](https://github.com/MarshalX/atproto-lexicons/blob/main/LICENSE).

The license covers the tooling and the generated code. The schemas in `lexicons/` are stored unmodified and belong to the services that publish them.
