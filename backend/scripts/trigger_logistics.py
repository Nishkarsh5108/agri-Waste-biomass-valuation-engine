import os
import sys

# Add the backend directory to sys.path so we can import our modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.worker.tasks import run_logistics_optimization

if __name__ == "__main__":
    print("============================================================")
    print("TRIGGERING LOGISTICS OPTIMIZATION (VRP)")
    print("============================================================")
    
    # Send the task to Celery's main-queue
    print("Pushing task to Celery...")
    result = run_logistics_optimization.delay()
    
    print(f"Task ID: {result.id}")
    print("Task successfully queued! Check your Celery worker logs to watch the routes being generated.")
    print("============================================================")
