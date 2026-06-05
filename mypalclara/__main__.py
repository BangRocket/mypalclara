"""Default entry point — launches the platform adapters (client).

The engine (gateway/runtime) now lives in the separate `mypal-engine` repo.
`python -m mypalclara` brings up the adapters, which connect to a running engine.
"""

from mypalclara.adapters.cli.launch_adapters import main

if __name__ == "__main__":
    main()
