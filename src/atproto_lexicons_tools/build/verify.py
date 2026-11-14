import importlib
import inspect
import json
import subprocess
import sys
import typing as t

from atproto_client.models.models_loader import load_models
from pydantic import BaseModel

from atproto_lexicons_tools.paths import PACKAGE, PACKAGE_DIR, PACKAGE_PROJECT_DIR


def compile_sources() -> int:
    paths = sorted(PACKAGE_DIR.rglob('*.py'))
    for path in paths:
        compile(path.read_text(encoding='utf-8'), str(path), 'exec')
    return len(paths)


def load_all_models() -> int:
    models_package = f'{PACKAGE}.models'
    load_models(models_package)

    models = importlib.import_module(models_package)
    aliases = [alias for alias in vars(type(models.ids)) if not alias.startswith('_')]

    count = 0
    for alias in aliases:
        module = getattr(models, alias)
        for _, cls in inspect.getmembers(module, inspect.isclass):
            if cls.__module__ != module.__name__ or not issubclass(cls, BaseModel):
                continue
            if not cls.__pydantic_complete__:
                message = f'Model {cls.__module__}.{cls.__qualname__} is not fully defined'
                raise RuntimeError(message)
            count += 1
    return count


def check_clients() -> None:
    for module_name, class_name in (
        ('client', 'AtprotoLexiconsClient'),
        ('async_client', 'AsyncAtprotoLexiconsClient'),
    ):
        client: t.Any = getattr(importlib.import_module(f'{PACKAGE}.{module_name}'), class_name)()
        sdk_methods = (client.app.bsky.feed.post.create, client.com.atproto.repo.create_record)
        if not all(callable(method) for method in sdk_methods):
            message = f'{class_name} lost a namespace of the SDK'
            raise RuntimeError(message)


class VerifyResult(t.NamedTuple):
    files: int
    models: int


def run() -> VerifyResult:
    sys.path.insert(0, str(PACKAGE_PROJECT_DIR))

    files = compile_sources()
    models = load_all_models()
    check_clients()

    return VerifyResult(files, models)


# Importing the package registers its records for the rest of the process,
# so the command line checks it in an interpreter of its own.
def run_isolated() -> VerifyResult:
    completed = subprocess.run(
        [sys.executable, '-m', 'atproto_lexicons_tools.build.verify'],
        check=True,
        capture_output=True,
        text=True,
        encoding='utf-8',
    )
    return VerifyResult(**json.loads(completed.stdout))


if __name__ == '__main__':
    print(json.dumps(run()._asdict()))  # noqa: T201
