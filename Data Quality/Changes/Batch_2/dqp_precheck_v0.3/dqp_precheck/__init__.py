"""dqp_precheck: checks on an index's input files before the Data Quality Profile matching (country codes,
KPI traceability, scale and units). See checks.py for the contract."""
from .checks import run, Result, PARAMS, ESCWA, clean_kpi_id
__version__ = "0.1"
