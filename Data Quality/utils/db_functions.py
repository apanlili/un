import pandas as pd
import mssql_python

def get_connection_string(env: str = "dev") -> str:
    prefix = env.upper()
    try:
        server = os.environ[f"{prefix}_DB_SERVER"]
        database = os.environ[f"{prefix}_DB_NAME"]
        user = os.environ[f"{prefix}_DB_USER"]
        password = os.environ[f"{prefix}_DB_PASSWORD"]
    except KeyError as e:
        raise RuntimeError(f"Missing environment variable: {e.args[0]}") from None

    return (
        f"Server={server};"
        f"Database={database};"
        f"UID={user};"
        f"PWD={password};"
        "TrustServerCertificate=Yes"
    )

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

def get_latest_hist_data(connection_string: str, kpi_list: list) -> pd.DataFrame:
    """Return historical data per ISO and KPI ID, with every year between each
    KPI's min and max year present (missing years filled with NaN)."""
    empty_cols = ["KPI ID", "Series Name", "year_historical_automated",
                  "ISO", "data_historical_automated"]
    if not kpi_list:
        return pd.DataFrame(columns=empty_cols)

    placeholders = ",".join("?" for _ in kpi_list)
    query = f"""
        SELECT
            h.KPIID AS [KPI ID],
            k.Name  AS [Series Name],
            h.[Year] AS year_historical_automated,
            c.ISO,
            h.Value AS data_historical_automated
        FROM HistoricalKPI AS h
        LEFT JOIN Countries AS c ON h.CountryID = c.keyID
        LEFT JOIN KPIs AS k ON h.KPIID = k.KeyID
        WHERE h.KPIID IN ({placeholders});
    """

    with mssql_python.connect(connection_string) as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, list(kpi_list))
            columns = [col[0] for col in cursor.description]
            rows = cursor.fetchall()

    hist_data = pd.DataFrame.from_records(rows, columns=columns)
    if hist_data.empty:
        return pd.DataFrame(columns=empty_cols)

    # Drop rows without a year so the int conversion doesn't fail
    hist_data = hist_data.dropna(subset=["year_historical_automated"])
    hist_data["year_historical_automated"] = hist_data["year_historical_automated"].astype(int)

    # Min and max year per KPI
    min_max_year = (
        hist_data.groupby("KPI ID")["year_historical_automated"]
                 .agg(["min", "max"])
                 .reset_index()
    )

    # Every KPI / Series / country combination that appears in the data
    kpi_iso = hist_data[["KPI ID", "Series Name", "ISO"]].drop_duplicates()

    # Attach each KPI's year range and expand it into one row per year
    grid = kpi_iso.merge(min_max_year, on="KPI ID", how="left")
    grid["year_historical_automated"] = [
        np.arange(lo, hi + 1) for lo, hi in zip(grid["min"], grid["max"])
    ]
    grid = grid.explode("year_historical_automated").drop(columns=["min", "max"])
    grid["year_historical_automated"] = grid["year_historical_automated"].astype(int)

    # Bring in the real data; missing years get NaN
    return (
        grid.merge(hist_data,
                   on=["KPI ID", "Series Name", "ISO", "year_historical_automated"],
                   how="left")
            .sort_values(["KPI ID", "ISO", "year_historical_automated"])
            .reset_index(drop=True)
    )

    