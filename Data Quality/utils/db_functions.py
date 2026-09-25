import pandas as pd
import mssql_python


def get_latest_sim_data(connection_string: str, kpi_list: list) -> pd.DataFrame:
    """Return the most recent year of simulator data per ISO and KPI ID."""
    if not kpi_list:
        return pd.DataFrame(
            columns=["Country", "ISO", "Series Name", "KPI ID",
                     "data_report", "data_report_year"]
        )

    placeholders = ",".join("?" for _ in kpi_list)
    query = f"""
        WITH ranked AS (
            SELECT
                c.Name AS Country,
                c.ISO,
                k.Name AS [Series Name],
                d.KPIID AS [KPI ID],
                d.Value AS data_report,
                d.[year] AS data_report_year,
                RANK() OVER (
                    PARTITION BY c.ISO, d.KPIID
                    ORDER BY d.[year] DESC
                ) AS rn
            FROM KPIData AS d
            LEFT JOIN Countries AS c ON d.CountryID = c.keyID
            LEFT JOIN KPIs AS k ON d.KPIID = k.KeyID
            WHERE d.KPIID IN ({placeholders})
        )
        SELECT Country, ISO, [Series Name], [KPI ID], data_report, data_report_year
        FROM ranked
        WHERE rn = 1;
    """

    with mssql_python.connect(connection_string) as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, list(kpi_list))
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()

    return pd.DataFrame.from_records(rows, columns=columns)


sim_data = get_latest_sim_data(connection_string, kpi_list)