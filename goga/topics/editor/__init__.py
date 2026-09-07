"""Editor-access cell for the topics domain.

The interactive multi-line text entry session through the external
editor resolved by the ``editor`` practice — the single interactive
surface of the topics domain. It is environment access, not topic
logic — every decision about when an entry happens belongs to the
caller.
"""

from .entry import edit_text

__all__: list[str] = ["edit_text"]
