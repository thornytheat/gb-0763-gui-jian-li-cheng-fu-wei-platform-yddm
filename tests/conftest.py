import pytest

from app.main import create_app
from app.inputs import published_meters, sample
from app.pipeline import inspect


@pytest.fixture
def archive_app(tmp_path):
    return create_app(tmp_path / 'track.sqlite')


@pytest.fixture
def client(archive_app):
    return archive_app.test_client()


@pytest.fixture(scope='session')
def dirty():
    return inspect(sample('dirty'), meters=published_meters('dirty'))


@pytest.fixture(scope='session')
def meter():
    return inspect(sample('meter'), meters=published_meters('meter'))


@pytest.fixture
def meter_client(client):
    return client
