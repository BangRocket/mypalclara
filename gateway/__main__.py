"""Entry point for running gateway as a module.

Usage:
    python -m gateway
"""

from gateway.main import main, parse_args

if __name__ == "__main__":
    import asyncio

    args = parse_args()
    try:
        asyncio.run(main(args.host, args.port, args.hooks_dir, args.scheduler_dir))
    except KeyboardInterrupt:
        pass
