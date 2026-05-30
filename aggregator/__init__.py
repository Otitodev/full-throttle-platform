"""Full Throttle dashboard aggregator.

Read-only FastAPI service that exposes a REST API over all Hermes profiles
under FT_PROFILES_ROOT. Binds to 127.0.0.1 only; Caddy fronts public access.
"""

__version__ = "0.1.0"
