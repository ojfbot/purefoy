"""
Make deakins_articles runnable as a module.

Usage:
    python -m deakins_articles scrape-all --username ... --password ...
"""

from .cli import main

if __name__ == "__main__":
    main()
