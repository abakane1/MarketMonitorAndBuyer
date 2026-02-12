import sys

# [P3-6 Fix] Suppress Streamlit cache warnings in non-Streamlit environments (like when running as a standalone script)
if 'streamlit' not in sys.modules:
    import warnings
    warnings.filterwarnings('ignore', module='streamlit.runtime.caching')
