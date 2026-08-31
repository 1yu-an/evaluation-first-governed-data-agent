"""Backward-compatible catalog view backed by the default Domain Profile."""

from enum import Enum

from .profile import (
    CompositionPattern,
    MetricDefinition,
    ResolverMetadata,
    load_default_profile,
)


COUNT_INTENT = "__count_intent__"
NET_OF = "__net_of__"


class CompilerStrategy(str, Enum):
    """Finite Core compiler operations; profiles cannot add executable code."""

    AGGREGATE = "aggregate"
    DIFFERENCE_OF_SUMS = "difference_of_sums"


_DEFAULT_PROFILE = load_default_profile()
METRIC_DEFINITIONS = _DEFAULT_PROFILE.metric_definitions
METRIC_CATALOG = _DEFAULT_PROFILE.metric_catalog
