from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Literal
from datetime import datetime



""" 
Domain layer defining the shape of the Source and Job python objects. Just dataclasses with typed fields. 
"""

SourceType = Literal['greenhouse', 'lever', 'ashby', 'workday', 'generic']


@dataclass(slots=True) # slots = lower mem, faster attr access
class Source:
    source_type: SourceType
    root_url: str
    discovered_from: str = 'search'
    active: bool = True
    first_seen: Optional[datetime] = None # timestamps optional, repo layer sets them
    last_seen: Optional[datetime]= None


@dataclass(slots=True)
class Job:
    source_root_url: str # instead of source_id. Domain model doesnt care about DB internals
    job_url: str
    title: str
    company: str
    location_text: str = ''
    description_text: str = ''
    is_remote: bool = False
    department: str = ''
    office: str = ''
    job_updated_at: str | None = None
    matched_keywords: tuple[str, ...] = field(default_factory=tuple) # instead of list, safer and hashable.
    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None