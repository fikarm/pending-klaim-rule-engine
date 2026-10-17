"""Pending Klaim rule engine package."""

def main():
	from .klaim_engine import main as engine_main

	return engine_main()

__all__ = ["main"]
