import re

from mandalore import __version__
from mandalore.config.ConstantConfig import ConstantConfig


def test_version():
    assert re.fullmatch(r"\d+\.\d+\.\d+([ab]\d+)?", __version__)
    assert ConstantConfig.version == __version__


def test_image_name():
    assert ConstantConfig.IMAGE_NAME == f"{ConstantConfig.DOCKER_REGISTRY}/{ConstantConfig.IMAGE_REPOSITORY}"
