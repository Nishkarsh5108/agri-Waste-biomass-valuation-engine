from pydantic import BaseModel

class TriggerResponse(BaseModel):
    message: str
    task_id: str
