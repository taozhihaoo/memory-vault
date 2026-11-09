"""Allow ``python -m memoryvault`` as an alias for the CLI."""

from memoryvault.cli import main

raise SystemExit(main())
