from typing import Optional

from .wrappers import BaseModel


class File(BaseModel):
    path: str # work_dir/fname
    content: str | bytes
    work_dir: Optional[str]
    fname: Optional[str]