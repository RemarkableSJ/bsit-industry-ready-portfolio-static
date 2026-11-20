"""Buo application entry point."""

from .legacy_ui import BuoApp


def main() -> None:
    BuoApp().run()
