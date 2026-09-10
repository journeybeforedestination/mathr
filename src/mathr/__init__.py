"""mathr — a rocket you build out of math facts."""

import random
import sys

import pygame

from .shell import audio
from .shell.app import App
from .storage import default_path


def main() -> None:
    # A flag rather than an environment variable: the point of test mode is that
    # you can see you are in it, and an exported variable that outlives the
    # session is exactly how a real round gets written to the wrong file.
    testing = "--test" in sys.argv[1:]
    audio.pre_init()  # before pygame.init(), or the mixer format is already fixed
    pygame.init()
    try:
        App(default_path(testing), random.Random(), testing=testing).run()
    finally:
        pygame.quit()
