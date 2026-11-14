from pathlib import Path

ROOT = Path(__file__).absolute().parents[2]

SERVICES_PATH = ROOT.joinpath('services.json')
LEXICONS_DIR = ROOT.joinpath('lexicons')
LOCK_PATH = ROOT.joinpath('lexicons.lock.json')
SUPPORT_JSON_PATH = ROOT.joinpath('supported.json')
SUPPORT_MD_PATH = ROOT.joinpath('SUPPORTED.md')

README_PATH = ROOT.joinpath('README.md')

SITE_SOURCE_DIR = ROOT.joinpath('website')
SITE_OUTPUT_DIR = ROOT.joinpath('site')
SITE_DOMAIN = 'lex.atproto.blue'
REPOSITORY_URL = 'https://github.com/MarshalX/atproto-lexicons'
SDK_REPOSITORY = 'MarshalX/atproto'

PACKAGE = 'atproto_lexicons'
PYPI_NAME = 'atproto-lexicons'
PACKAGE_PROJECT_DIR = ROOT.joinpath('package')
PACKAGE_DIR = PACKAGE_PROJECT_DIR.joinpath(PACKAGE)

EXTERNAL_DIR_NAME = '_external'
