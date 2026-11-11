"""Convert blog posts into WeChat official account articles.

The package turns the Hexo source tree (``source/_posts/``, produced by
``tools/sync-hexo.py``) into WeChat-ready HTML and pushes it to the
official account draft box.

Modules are layered so each one can be tested on its own:

- ``posts``     discover articles and validate them against WeChat's limits
- ``mdparse``   Markdown -> block AST (pure)
- ``render``    AST -> WeChat HTML (pure)
- ``highlight`` code -> inline-styled HTML
- ``mermaid``   mermaid diagrams -> PNG
- ``assets``    image compression and sizing
- ``publish``   WeChat API client (network)
- ``state``     idempotency bookkeeping
"""
