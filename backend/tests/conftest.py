"""Guard destructive integration fixtures against accidental runs."""
import os
import pytest


def pytest_sessionstart(session):
    if os.getenv('TEST_DATABASE_URL') and os.getenv('METRA_TEST_DB') != '1':
        raise pytest.UsageError('La suite recrea tablas. Usa base desechable y METRA_TEST_DB=1.')
