import os
import sys
import asyncio

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.worker.logistics_optimizer import run_logistics_optimization_async

if __name__ == "__main__":
    print("Running logistics optimization synchronously...")
    asyncio.run(run_logistics_optimization_async())
    print("Done! Listings should now be routed.")
