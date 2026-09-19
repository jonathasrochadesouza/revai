"""Packaged static assets.

``agent-report.html`` is the standalone template behind the RevAI review
agent: the agent copies it into the review directory and injects the review
JSON at the ``__REVAI_DATA__`` placeholder. Kept as a package resource
(loaded with ``importlib.resources``) rather than a source-code string so the
template can be read, edited, and shipped verbatim.
"""
