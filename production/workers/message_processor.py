"""
FlowSync Message Processor - Free Tier Compatible Version
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
import time

logger = logging.getLogger("flowsync.worker")

# PATH SETUP
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for p in [_project_root]:
    if p not in sys.path:
        sys.path.insert(0, p)


async def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )

    logger.info("=== FlowSync Message Processor (Free Tier Mode) ===")
    logger.info("Running in direct mode (no Kafka)")

    while True:
        try:
            logger.info("Worker is alive and ready (direct mode)")
            # Keep the process running
            await asyncio.sleep(30)
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error("Worker error: %s", e)
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())