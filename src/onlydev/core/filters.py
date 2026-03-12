from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence
import re

from onlydev.core.config import get



def _norm(s: str) -> str:
    return re.sub(r'\s+', ' ', (s or '')).strip().lower()

def _get_role_tokens() -> tuple[str, ...]:
    return tuple(get("filters")["role_tokens"])

def _get_exclude_title_tokens() -> tuple[str, ...]:
    return tuple(get("filters")["exclude_title_tokens"])

def title_looks_dev(title: str) -> bool:
    t = _norm(title)
    return any(tok in t for tok in _get_role_tokens())

def title_is_excluded(title: str) -> bool:
    t = _norm(title)
    return any(tok in t for tok in _get_exclude_title_tokens())


@dataclass(slots=True)
class FilterConfig:
    keywords: tuple[str, ...] = (
        'python',
        'django',
        'next.js',
        'backend developer',
        'fullstack developer',
    )

    # 'remote only unless near home'
    home_zip: str = ''
    zip_radius_miles: int = 50

    # local heuristics
    local_city_tokens: tuple[str, ...] = ()
    local_state_tokens: tuple[str, ...] = ()

    # remote detection
    remote_tokens: tuple[str, ...] = (
        'remote',
        'work from home',
        'wfh',
        'distributed',
        'anywhere',
        'usa remote',
        'us remote',
        'fully remote',
        '100% remote',
    )

    # exclude hybrid/onsite unless local
    exclude_if_not_local_tokens: tuple[str, ...] = (
        'on-site',
        'onsite',
        'in office',
        'in-office',
        'hybrid',
    )

def match_keywords(text: str, keywords: Sequence[str]) -> tuple[str, ...]:
    """
    Returns matched keywords (as provided) based on case-insensitive containment.
    """
    t = _norm(text)
    hits: list[str] = []
    for k in keywords:
        if _norm(k) in t:
            hits.append(k)
    return tuple(hits)


def is_remote(location_text: str = '', description_text: str = '', title: str = '', cfg: FilterConfig | None = None) -> bool:
    cfg = cfg or FilterConfig()
    blob = _norm(' '.join([title, location_text, description_text]))
    return any(tok in blob for tok in map(_norm, cfg.remote_tokens))


def is_local(location_text: str = '', description_text: str = '', cfg: FilterConfig | None = None) -> bool:
    """
    Best-effort "near ZIP" without external geo data:
    - Exact ZIP appears in location/description -> local
    - Any configured city/state token appears -> local
    """
    cfg = cfg or FilterConfig()
    blob = _norm(' '.join([location_text, description_text]))

    if cfg.home_zip and cfg.home_zip in blob:
        return True

    for city in cfg.local_city_tokens:
        if _norm(city) in blob:
            return True

    for state in cfg.local_state_tokens:
        if _norm(state) in blob:
            return True

    return False


def passes_location_rule(
    title: str,
    location_text: str,
    description_text: str,
    cfg: FilterConfig,
) -> bool:
    """
    Rule: Remote-only unless local.
    """
    if is_remote(location_text, description_text, title, cfg):
        return True
    return is_local(location_text, description_text, cfg)


def should_consider_job(
    title: str,
    location_text: str,
    description_text: str,
    cfg: FilterConfig,
) -> tuple[bool, tuple[str, ...]]:
    
    if not title_looks_dev(title):
        return False, tuple()
    
    if title_is_excluded(title):
        return False, tuple()
    
    hits = match_keywords(f'{title} {description_text}', cfg.keywords)
    if not hits:
        return False, tuple()

    if not passes_location_rule(title, location_text, description_text, cfg):
        return False, hits

    # if it screams onsite/hybrid and not local, reject (already covered by location rule )
    blob = _norm(' '.join([title, location_text, description_text]))
    if any(_norm(tok) in blob for tok in cfg.exclude_if_not_local_tokens):
        if not is_local(location_text, description_text, cfg):
            return False, hits

    return True, hits