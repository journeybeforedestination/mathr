"""mathr — a rocket you build out of math facts."""

import random

import pygame

from .shell import audio
from .shell.app import App
from .storage import default_path


def main() -> None:
    audio.pre_init()  # before pygame.init(), or the mixer format is already fixed
    pygame.init()
    try:
        App(default_path(), random.Random()).run()
    finally:
        pygame.quit()
