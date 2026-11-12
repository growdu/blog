"""Shorten a title so that WeChat will take it.

Two limits matter, and they are not the same:

* The ``draft/add`` API refuses a title longer than 85 characters with
  ``[45003] title size out of limit``.  That was measured against the
  live API -- 85 goes through, 86 does not.
* The editor behind it lets a person type 64 characters into the
  title field.  A draft with a longer title can be created but not
  published from the editor, and publishing is a human step here.

So the limit this module works to is the smaller of the two: 64.  An
earlier reading of the documentation said 32, and the corpus proved it
wrong -- drafts with 33 to 35 character titles were accepted all
along, and the 105 articles that the 32-character gate had blocked
were blocked for no reason at all.

Shortening is not a blind cut.  A title in this corpus is usually
「主标题：副标题」, and the colon is where the reader expects the title
to end; cutting there keeps the part that says what the article is
about and drops the part that only elaborates.  When there is no such
boundary, the next best one is used, and only as a last resort is the
title cut in the middle.
"""

from __future__ import annotations

import re

__all__ = ["SUFFIX_RESERVE", "TITLE_LIMIT", "effective_title", "flatten",
           "shorten", "topic"]

# The editor's limit, which is the smaller of the two and therefore the
# one that has to be respected: a draft that cannot be published is
# not a draft.
TITLE_LIMIT = 64

# A split article's parts are titled 「标题（一）」, 「标题（二）」……, so the
# title they share has to leave room for the suffix.  Without this the
# last part of a long-titled article would be one character too long.
SUFFIX_RESERVE = 3

# The boundaries a title can be cut at, best first.  A colon separates
# the topic from the elaboration, and the title is usually written
# that way; the rest are weaker boundaries that only come into play
# when the title has no clear topic of its own.
_STRONG = ("：", ":", "——", "—", "---", " - ")
_WEAK = (" ", "｜", "|", "·", "（", "、", "，", ",", "；", ";", "/")

# A cut that leaves less than this is not a title.
_MIN_HEAD = 6

# What a cut leaves hanging at the end of the head.  The brackets are
# not in here: a bracket that lost its partner is dealt with by
# pairing, not by trimming.
_TRAILING = "：:—–-·、，,；;｜|/ \t"


def _clean(text: str) -> str:
    """Trim what a cut leaves behind.

    A cut in the middle of a bracket leaves it open, and a dangling
    separator at the end of a title is noise.  The brackets are paired
    first: a title that still has both halves of a bracket keeps them.
    """
    out = text
    for opener, closer in (("（", "）"), ("(", ")"), ("【", "】")):
        while out.count(opener) > out.count(closer):
            index = out.rfind(opener)
            if index < 0:
                break
            out = out[:index] + out[index + 1:]
        while out.count(closer) > out.count(opener):
            index = out.rfind(closer)
            if index < 0:
                break
            out = out[:index] + out[index + 1:]
    return out.rstrip(_TRAILING)


def _is_url(text: str) -> bool:
    """True when the head ends in a URL scheme rather than in a topic.

    A colon inside ``https://`` is not the boundary between a title
    and its subtitle.
    """
    return text.rstrip().endswith(("http", "https", "ftp", "mailto"))


def shorten(title: str, limit: int) -> str:
    """The title, shortened to ``limit`` characters at the best boundary.

    A title that already fits is returned unchanged.

    The title of this corpus is usually 「主标题：副标题」, and the
    colon is where the reader expects it to end, so that is tried
    first.  When the topic before the colon is itself too long to fit,
    the cut moves to the last boundary that still leaves room -- that
    keeps as much of the title as possible instead of throwing most of
    it away.

    Only a title with no boundary at all is cut in the middle, and then
    it says so: a truncated title that admits it is better than one
    that pretends to be complete.
    """
    if limit <= 0:
        return ""
    if len(title) <= limit:
        return title

    # The topic before the first strong boundary: that is what the
    # title is about, and it is the part worth keeping.
    for separator in _STRONG:
        index = title.find(separator)
        while index > 0:
            head = _clean(title[:index])
            if _MIN_HEAD <= len(head) <= limit and not _is_url(head):
                return head
            index = title.find(separator, index + 1)

    # No strong boundary works: keep as much of the title as fits and
    # cut at the last boundary that leaves room for it.
    best = ""
    for separator in _WEAK:
        index = title.find(separator)
        while index > 0:
            head = _clean(title[:index])
            if _MIN_HEAD <= len(head) <= limit and len(head) > len(best):
                best = head
            index = title.find(separator, index + 1)
    if best:
        return best

    return _clean(title[:limit - 1]) + "…"


def topic(title: str, limit: int = 18) -> str:
    """The topic of a title: the part before its first boundary.

    This is what goes on a cover card -- short enough to read at a
    glance, and about what the article is rather than how far it goes.
    """
    for separator in ("：", ":", "——", "—", "---", " - "):
        index = title.find(separator)
        if index > 0:
            head = _clean(title[:index])
            if len(head) >= _MIN_HEAD:
                return head[:limit]
    return title[:limit]


_LINK_RE = re.compile(r"\[([^\]]*)\]\([^)]*\)")


def flatten(title: str) -> str:
    """The title as plain text.

    A WeChat title is text, not markup: a link in it shows up as the
    whole ``[words](address)``, which is noise on a phone.
    """
    return _LINK_RE.sub(r"\1", title).strip()


def effective_title(title: str, limit: int = TITLE_LIMIT) -> str:
    """The title a draft will carry.

    A split article's parts are titled 「标题（一）」, so the title they
    share leaves room for the suffix.  Everything that ends up in a
    draft -- the title itself, the transition lines, the cover card --
    uses this one, so they never disagree.
    """
    return shorten(flatten(title), limit - SUFFIX_RESERVE)
