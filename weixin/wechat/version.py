"""The version of the conversion pipeline.

Bump it whenever a change alters what ends up in the draft: a new
style, a different split, a different cover.  The drafts in the box
were made by an older version, and only the ledger knows that -- the
article itself did not change, so its content hash stayed the same and
the draft would have been reused as is.

The ledger stores the version next to the fingerprint, so a bump makes
every draft look changed and the next run brings them up to date.

    1  the first version
    2  long titles are shortened, and a part without a picture of its
       own gets a cover card drawn for it
    3  the author's own title page becomes a card at the top of the
       first part, every part ends with a signature, and the summary
       is taken from what the author wrote about the article
"""

PIPELINE_VERSION = 3
