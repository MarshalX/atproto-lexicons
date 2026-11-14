# ruff: noqa: INP001
"""Render the images of the website from their sources in this folder, with headless Chrome.

og.html is the link preview, banner.html is the header of the README, icon.html is the mark every icon is drawn from.
Run it after editing either: python design/render.py
"""

import os
import shutil
import struct
import subprocess
import sys
import tempfile
import typing as t
from pathlib import Path
from urllib.parse import urlencode

DESIGN_DIR = Path(__file__).parent
WEBSITE_DIR = DESIGN_DIR.parent.joinpath('website')
IMAGES_DIR = WEBSITE_DIR.joinpath('images')

_CHROME_PATHS = ('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',)
_CHROME_COMMANDS = ('google-chrome', 'chromium', 'chromium-browser')
_TRANSPARENT = '00000000'


class Icon(t.NamedTuple):
    size: int
    # what differs from the mark as icon.html draws it; small sizes need heavier strokes to stay legible
    variant: dict[str, float] = {}  # noqa: RUF012


ICONS = {
    'icon-192.png': Icon(192),
    'icon-512.png': Icon(512),
    # iOS and Android cut the corners themselves, so these fill the square and keep the glyph in the safe area
    'apple-touch-icon.png': Icon(180, {'radius': 0, 'scale': 0.92}),
    'icon-maskable-512.png': Icon(512, {'radius': 0, 'scale': 0.74}),
}
# stays at the root of the website: browsers ask for /favicon.ico on their own
FAVICON = 'favicon.ico'
FAVICON_SIZES = [
    Icon(16, {'radius': 7, 'stroke': 2.6, 'dot': 2.4}),
    Icon(32, {'stroke': 2.1, 'dot': 2.1}),
    Icon(48, {'stroke': 2.1, 'dot': 2.1}),
]
PAGES = [
    ('og.html', 'og.png', 1200, 630),
    ('banner.html', 'banner.png', 1600, 440),
    ('banner.html?theme=dark', 'banner-dark.png', 1600, 440),
]


def find_chrome() -> str:
    candidates = [os.environ.get('CHROME'), *_CHROME_PATHS, *(shutil.which(command) for command in _CHROME_COMMANDS)]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return candidate

    sys.exit('Chrome was not found. Point CHROME at its binary.')


def screenshot(chrome: str, url: str, output: Path, width: int, height: int) -> None:
    command = [
        chrome,
        '--headless=new',
        '--hide-scrollbars',
        '--force-device-scale-factor=1',
        f'--default-background-color={_TRANSPARENT}',
        f'--window-size={width},{height}',
        '--virtual-time-budget=3000',
        f'--screenshot={output}',
        url,
    ]
    subprocess.run(command, check=True, capture_output=True)  # noqa: S603


def render_icon(chrome: str, icon: Icon, output: Path) -> None:
    url = f'{DESIGN_DIR.joinpath("icon.html").as_uri()}?{urlencode({"size": icon.size, **icon.variant})}'
    screenshot(chrome, url, output, icon.size, icon.size)


def pack_ico(images: list[tuple[int, bytes]]) -> bytes:
    """Pack PNG images into one .ico file, which may carry them as they are."""
    header = struct.pack('<HHH', 0, 1, len(images))
    offset = len(header) + 16 * len(images)

    entries = b''
    for size, data in images:
        entries += struct.pack('<BBBBHHII', size, size, 0, 0, 1, 32, len(data), offset)
        offset += len(data)

    return header + entries + b''.join(data for _, data in images)


def main() -> None:
    chrome = find_chrome()

    for source, name, width, height in PAGES:
        screenshot(chrome, f'{DESIGN_DIR.as_uri()}/{source}', IMAGES_DIR.joinpath(name), width, height)

    for name, icon in ICONS.items():
        render_icon(chrome, icon, IMAGES_DIR.joinpath(name))

    with tempfile.TemporaryDirectory() as directory:
        images = []
        for icon in FAVICON_SIZES:
            path = Path(directory, f'{icon.size}.png')
            render_icon(chrome, icon, path)
            images.append((icon.size, path.read_bytes()))

    WEBSITE_DIR.joinpath(FAVICON).write_bytes(pack_ico(images))

    print(f'Wrote {len(PAGES) + len(ICONS) + 1} images to {WEBSITE_DIR.name}/.')  # noqa: T201


if __name__ == '__main__':
    main()
