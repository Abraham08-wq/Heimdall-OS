#!/usr/bin/env python
import asyncio
import argparse
import sys
from pathlib import Path

# Add project root to the Python path
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root / 'backend'))

from app.services.intelligence.retriever import retriever_engine

async def main():
    """
    Main function to run the deep scan.
    """
    parser = argparse.ArgumentParser(description="Run a deep scan for a target.")
    parser.add_argument("--target", required=True, help="The target to scan (Email, IP, or Alias).")
    args = parser.parse_args()

    results = await retriever_engine.deep_scan(args.target)
    print(results)

if __name__ == "__main__":
    asyncio.run(main())
