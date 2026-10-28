"""
Shared Streamlit session state: one cached RetailIntelligenceOrchestrator
for the whole dashboard, so every page reuses the same RetailDataService
and agent engines rather than reloading the CSVs/rebuilding engines on
every page view or widget interaction.
"""

import streamlit as st

from orchestration.query_orchestrator import RetailIntelligenceOrchestrator


@st.cache_resource
def get_orchestrator():
    return RetailIntelligenceOrchestrator()
