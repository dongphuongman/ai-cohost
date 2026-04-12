"""Insights subpackage — registries and helpers for grounding AI Insights
recommendations in features that actually exist in the dashboard UI.

The main insights service still lives at ``app.services.session_insights``
for backwards compatibility; this package holds the data tables that the
service consults at prompt-build and validation time.
"""
