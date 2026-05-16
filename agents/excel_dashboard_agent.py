"""Excel Dashboard Agent — openpyxl + plotly dashboards."""

from agents.base import BaseAgent


class ExcelDashboardAgent(BaseAgent):
    role_blurb = (
        "Excel + dashboard builder. Produces formatted .xlsx workbooks and "
        "interactive plotly HTML dashboards from raw data."
    )
