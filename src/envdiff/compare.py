"""Compare the keys of env files against a reference (example) file. Keys only."""

from dataclasses import dataclass, field
from typing import List

from .parser import EnvFile


@dataclass
class Diff:
    path: str
    missing: List[str] = field(default_factory=list)  # in the env file, not in the example
    extra: List[str] = field(default_factory=list)    # in the example, not in the env file
    common: List[str] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not self.missing and not self.extra


def compare(env: EnvFile, example: EnvFile) -> Diff:
    env_keys = env.keys
    ex_keys = example.keys
    ex_set, env_set = set(ex_keys), set(env_keys)
    return Diff(
        path=env.path,
        missing=[k for k in env_keys if k not in ex_set],
        extra=[k for k in ex_keys if k not in env_set],
        common=[k for k in env_keys if k in ex_set],
    )


def all_missing(diffs: List[Diff]) -> List[str]:
    """Union of missing keys across diffs, first-seen order."""
    out: List[str] = []
    for d in diffs:
        for k in d.missing:
            if k not in out:
                out.append(k)
    return out
