from pydantic import BaseModel
from typing import List

class ProjectSummaryInput(BaseModel):
    proj_name: str
    mentor_name: List[str]
    linkedin: List[str]
    github: List[str]
