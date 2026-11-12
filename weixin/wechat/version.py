"""The version of the conversion pipeline.

Bump it whenever a change alters what ends up in the draft: a new
style, a different split, a different cover.  The drafts in the box
were made by an older version, and only the ledger knows that -- the
article itself did not change, so its content hash stayed the same and
the draft would have been reused as it is.

    PIPELINE_VERSION = 2   # tables are no longer cut row by row

The ledger stores the version next to the fingerprint, so a bump makes
every draft look changed and the next run brings them up to date.
"""

PIPELINE_VERSION = 1
