
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
import io
from openpyxl.drawing.image import Image as XLImage
import matplotlib.pyplot as plt
import pandas as pd
from pathlib import Path

#############################################
####### Metadata Automation Output ##########
#############################################

def plot_series_with_outliers(g: pd.DataFrame, title: str = None):
    if len(g) == 0:
        raise ValueError("No rows matched for this group.")
    g = g.sort_values("year_historical_automated")
    outliers = g[g["outlier_total"] >= 1]

    # fitted-trend method used for this group, e.g. "exponential" or "rolling_median"
    trend_method = g["trend_method"].dropna().iloc[0] if g["trend_method"].notna().any() else "n/a"
    
    fig, ax = plt.subplots(figsize=(11, 6))
    ax.plot(g["year_historical_automated"], g["data_historical_automated"],
            marker="o", markersize=4, linewidth=1.5, color="#2563eb",
            label="Actual value", zorder=2)
    ax.plot(g["year_historical_automated"], g["fitted_trend"],
            linestyle="--", linewidth=1.5, color="#6b7280",
            label="Fitted trend", zorder=1)
    ax.scatter(outliers["year_historical_automated"], outliers["data_historical_automated"],
               s=(60 + outliers["outlier_total"] * 40), color="#dc2626",
               edgecolor="black", linewidth=0.7, zorder=3,
               label="Outlier (outlier_total ≥ 1)")
    for _, row in outliers.iterrows():
        ax.annotate(f"{int(row['outlier_total'])}",
                    (row["year_historical_automated"], row["data_historical_automated"]),
                    textcoords="offset points", xytext=(0, 10),
                    ha="center", fontsize=8, color="#dc2626", fontweight="bold")

    ax.set_title(title or 
                 f"{g['KPI ID'].iloc[0]} {g['Series Name'].iloc[0]} — {g['ISO'].iloc[0]}" 
                 f"[trend: {trend_method}]")
    ax.set_xlabel("Year")
    ax.set_ylabel(g["Series Name"].iloc[0])
    ax.legend(loc="best")
    ax.grid(alpha=0.3)
    fig.tight_layout()
    #plt.show()
    return fig
    
def write_dataframes_to_excel(
    dataframes: dict,
    output_path: str = "output.xlsx",
    freeze_header: bool = True,
    autofit_columns: bool = True,
    max_col_width: int = 50,
    header_bg_color: str = None,#"4472C4",   # Excel-blue; set None for no fill
    header_font_color: str = "FFFFFF",
    header_bold: bool = True,
    add_borders: bool = False,
    add_autofilter: bool = True,
    index: bool = False,

    plot_df: pd.DataFrame = None,
    plot_sheet_name: str = "outliers",
    plot_group_cols=("KPI ID", "ISO"),
    plot_n_cols: int = 2,
    plot_scale: float = 0.5,
    plot_only_flagged: bool = True,
):
    """
    Write a dict of DataFrames to one Excel file, one sheet per DataFrame.
 
    Parameters
    ----------
    dataframes : dict
        Mapping of {sheet_name: dataframe}. Sheet names are what you control
        naming for — just use whatever keys you want.
        Example: {"Sales": df_sales, "Inventory": df_inv}
    output_path : str
        Path to save the .xlsx file.
    freeze_header : bool
        If True, freezes the header row so it stays visible when scrolling.
    autofit_columns : bool
        If True, resizes each column to fit its longest value.
    max_col_width : int
        Cap on auto-fit column width (prevents huge columns from long text).
    header_bg_color : str or None
        Hex color (no '#') for header cell background fill.
    header_font_color : str
        Hex color (no '#') for header font color.
    header_bold : bool
        Whether header text is bold.
    add_borders : bool
        If True, adds thin borders around all cells.
    add_autofilter : bool
        If True, adds filter dropdowns to the header row.
    index : bool
        Whether to write the DataFrame index as a column.
    """
 
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        for sheet_name, df in dataframes.items():
            # Excel sheet names max 31 chars, no : \ / ? * [ ]
            safe_name = _sanitize_sheet_name(sheet_name)
            df.to_excel(writer, sheet_name=safe_name, index=index)
 
            worksheet = writer.sheets[safe_name]
            _format_worksheet(
                worksheet,
                df,
                freeze_header=freeze_header,
                autofit_columns=autofit_columns,
                max_col_width=max_col_width,
                header_bg_color=header_bg_color,
                header_font_color=header_font_color,
                header_bold=header_bold,
                add_borders=add_borders,
                add_autofilter=add_autofilter,
                index=index,
            )

        # --- append the plots sheet ---
        _plot_buffers = None        # keep alive until save() fires on __exit__
        if plot_df is not None:
            ws_plots = writer.book.create_sheet(_sanitize_sheet_name(plot_sheet_name))
            _plot_buffers = _add_plots_sheet(
                ws_plots, plot_df,
                group_cols=plot_group_cols,
                #n_cols=plot_n_cols,
                scale=plot_scale,
                only_flagged=plot_only_flagged,
            )
 
    print(f"Saved: {output_path}")
 
 
def _sanitize_sheet_name(name: str) -> str:
    invalid_chars = [":", "\\", "/", "?", "*", "[", "]"]
    for ch in invalid_chars:
        name = name.replace(ch, "")
    return name[:31]
 
 
def _format_worksheet(
    ws,
    df,
    freeze_header,
    autofit_columns,
    max_col_width,
    header_bg_color,
    header_font_color,
    header_bold,
    add_borders,
    add_autofilter,
    index,
):
    n_cols = df.shape[1] + (1 if index else 0)
    n_rows = df.shape[0] + 1  # +1 for header row
 
    # --- Header styling ---
    header_font = Font(bold=header_bold, color=header_font_color if header_bg_color else "000000")
    header_fill = PatternFill(
        start_color=header_bg_color, end_color=header_bg_color, fill_type="solid"
    ) if header_bg_color else None
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
 
    for col_idx in range(1, n_cols + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.font = header_font
        if header_fill:
            cell.fill = header_fill
        cell.alignment = header_align
 
    # Slightly taller header row to fit wrapped text
    ws.row_dimensions[1].height = 22
 
    # --- Optional thin borders on all used cells ---
    if add_borders:
        thin = Side(style="thin", color="B7B7B7")
        border = Border(left=thin, right=thin, top=thin, bottom=thin)
        for row in ws.iter_rows(min_row=1, max_row=n_rows, min_col=1, max_col=n_cols):
            for cell in row:
                cell.border = border
 
    # --- Freeze header row (and index column if present) ---
    if freeze_header:
        ws.freeze_panes = "B2" if index else "A2"
 
    # --- Autofilter on header row ---
    if add_autofilter:
        ws.auto_filter.ref = ws.dimensions
 
    # --- Autofit column widths based on longest value ---
    if autofit_columns:
        for col_idx in range(1, n_cols + 1):
            col_letter = get_column_letter(col_idx)
            max_len = 0
            for cell in ws[col_letter]:
                if cell.value is not None:
                    max_len = max(max_len, len(str(cell.value)))
            ws.column_dimensions[col_letter].width = min(max_len + 3, max_col_width)

def _add_plots_sheet(ws, df, group_cols=("KPI ID", "ISO"),
                     dpi=100, scale=0.5, only_flagged=True, label_groups=True,
                     data_cols=None, data_rows="all",
                     block_gap=2, px_per_row=20, px_per_col=64):
    """One block per flagged group: data table on the left, plot to its right,
    blocks stacked vertically. Returns image buffers (keep referenced until save)."""
    if data_cols is None:
        data_cols = ["year_historical_automated", "data_historical_automated",
                     "fitted_trend", "resid", "outlier_total", "flagged_year"]
    data_cols = [c for c in data_cols if c in df.columns]   # keep existing cols, in order

    buffers = []
    bold = Font(bold=True)
    current_row = 1

    for keys, g in df.groupby(list(group_cols), sort=True):
        if only_flagged and not (g["outlier_total"] >= 1).any():
            continue

        g = g.sort_values("year_historical_automated")
        table = g[g["outlier_total"] >= 1] if data_rows == "flagged" else g
        table = table.sort_values("year_historical_automated", ascending=False)  # descending for the table

        # render the plot
        fig = plot_series_with_outliers(g)
        buf = io.BytesIO()
        fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        buffers.append(buf)

        img = XLImage(buf)
        img.width *= scale
        img.height *= scale
        img_rows = int(img.height // px_per_row) + 1

        # optional group label above the block
        table_start = current_row
        if label_groups:
            label = " | ".join(str(k) for k in (keys if isinstance(keys, tuple) else (keys,)))
            ws.cell(row=current_row, column=1, value=label).font = bold
            table_start += 1

        # table header
        for j, col in enumerate(data_cols):
            ws.cell(row=table_start, column=1 + j, value=col).font = bold
        # table body
        for r, (_, row) in enumerate(table.iterrows(), start=1):
            for j, col in enumerate(data_cols):
                val = row[col]
                if pd.isna(val):
                    val = None
                elif hasattr(val, "item"):     # numpy scalar -> python scalar
                    val = val.item()
                ws.cell(row=table_start + r, column=1 + j, value=val)

        table_rows = 1 + len(table)
        img_left_col = len(data_cols) + 2       # one blank gap column between table and plot
        ws.add_image(img, f"{get_column_letter(img_left_col)}{table_start}")

        current_row = table_start + max(table_rows, img_rows) + block_gap

    return buffers


#############################################
############## Country Profile ##############
#############################################

from .formatting_functions import profile_country_kpi_tbl, profile_country_kpi_summary

def _sanitize_sheet_name(name: str) -> str:
    invalid_chars = [":", "\\", "/", "?", "*", "[", "]"]
    for ch in invalid_chars:
        name = name.replace(ch, "")
    return name[:31]
 
 
def _unique_sheet_name(name: str, used: set) -> str:
    """Sanitize and de-duplicate, since Excel rejects repeated sheet names."""
    base = _sanitize_sheet_name(name)
    candidate, i = base, 2
    while candidate in used:
        suffix = f"_{i}"
        candidate = base[:31 - len(suffix)] + suffix
        i += 1
    used.add(candidate)
    return candidate
 
 
# ---------------------------------------------------------------------------
# core layout logic -- writes ONE sheet into an already-open writer
# ---------------------------------------------------------------------------
def _write_tables_to_sheet(
    writer,
    table_dict: dict,
    sheet_name: str = "Summary",
    index_title: str = None,
    title: str = None,
    gap_rows: int = 1,
    autofit_columns: bool = True,
    max_col_width: int = 50,
    title_bg_color: str = "4472C4",
    title_font_color: str = "FFFFFF",
    label_bg_colors: tuple = ("DDEBF7", "F2F2F2"),
    header_bg_color: str = None,
    header_font_color: str = "FFFFFF",
    header_bold: bool = True,
    add_borders: bool = False,
    index: bool = False,
):
    """Write a dict of DataFrames stacked vertically onto a single sheet of an
    open pd.ExcelWriter. Identical layout to the original function -- it just
    no longer owns the writer, so many sheets can share one workbook."""
    safe_name = _sanitize_sheet_name(sheet_name)
 
    header_font = Font(bold=header_bold, color=header_font_color if header_bg_color else "000000")
    header_fill = PatternFill(
        start_color=header_bg_color, end_color=header_bg_color, fill_type="solid"
    ) if header_bg_color else None
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
 
    title_font = Font(bold=True, color=title_font_color if title_bg_color else "000000")
    title_fill = PatternFill(
        start_color=title_bg_color, end_color=title_bg_color, fill_type="solid"
    ) if title_bg_color else None
 
    label_font = Font(bold=True)
    thin = Side(style="thin", color="B7B7B7")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
 
    max_width = max(
        (df.shape[1] + (1 if index else 0)) for df in table_dict.values()
    ) if table_dict else 1
 
    skip_rows = set()
 
    writer.book.create_sheet(safe_name)
    ws = writer.book[safe_name]
    writer.sheets[safe_name] = ws
 
    current_row = 1  # row 1 left blank
 
    # --- title row ----------------------------------------------------------
    if index_title is not None or title is not None:
        current_row += 1
        ws.cell(row=current_row, column=1, value=index_title)
        ws.cell(row=current_row, column=2, value=title)
        for col_idx in range(1, max_width + 1):
            cell = ws.cell(row=current_row, column=col_idx)
            cell.font = title_font
            if title_fill:
                cell.fill = title_fill
        skip_rows.add(current_row)
        current_row += 1  # blank row after the title
 
    # --- each table ---------------------------------------------------------
    for i, (label, df) in enumerate(table_dict.items()):
        current_row += 1
        label_row = current_row
        ws.cell(row=label_row, column=1, value=label).font = label_font
        skip_rows.add(label_row)
 
        n_cols = df.shape[1] + (1 if index else 0)
 
        if label_bg_colors:
            color = label_bg_colors[i % len(label_bg_colors)]
            label_fill = PatternFill(start_color=color, end_color=color, fill_type="solid")
            for col_idx in range(1, n_cols + 1):
                ws.cell(row=label_row, column=col_idx).fill = label_fill
 
        header_row = label_row + 1
        df.to_excel(
            writer,
            sheet_name=safe_name,
            startrow=header_row - 1,  # to_excel is 0-indexed
            index=index,
        )
 
        last_row = header_row + df.shape[0]
 
        for col_idx in range(1, n_cols + 1):
            cell = ws.cell(row=header_row, column=col_idx)
            cell.font = header_font
            if header_fill:
                cell.fill = header_fill
            cell.alignment = header_align
        ws.row_dimensions[header_row].height = 22
 
        if add_borders:
            for row in ws.iter_rows(min_row=header_row, max_row=last_row,
                                    min_col=1, max_col=n_cols):
                for cell in row:
                    cell.border = border
 
        current_row = last_row + gap_rows
 
    # --- autofit across every table -----------------------------------------
    if autofit_columns:
        for col_idx in range(1, ws.max_column + 1):
            col_letter = get_column_letter(col_idx)
            max_len = 0
            for cell in ws[col_letter]:
                if cell.row in skip_rows:
                    continue
                if cell.value is not None:
                    max_len = max(max_len, len(str(cell.value)))
            if max_len:
                ws.column_dimensions[col_letter].width = min(max_len + 3, max_col_width)
 
 
# ---------------------------------------------------------------------------
# single-sheet entry point (same signature/behaviour as before)
# ---------------------------------------------------------------------------
def write_stacked_tables_to_excel(
    table_dict: dict,
    output_path: str = "output.xlsx",
    sheet_name: str = "Summary",
    **kwargs,
):
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        _write_tables_to_sheet(writer, table_dict, sheet_name=sheet_name, **kwargs)
    print(f"Saved: {output_path}")
 
 
# ---------------------------------------------------------------------------
# multi-country entry point -- one sheet per country, one workbook
# ---------------------------------------------------------------------------
def write_country_sheets_to_excel(
    metadata_automated,
    kpi_year,
    diagnosis_assessment_template,
    country_iso_list: list,
    quality_cols: list,
    static_tables: dict,
    output_path: str = "output.xlsx",
    index_title: str = None,
    title: str = None,
    skip_missing: bool = True,
    **kwargs,
):
    """
    Loop over country_list, build the country KPI summary and KPI table for each,
    and write one sheet per country into a single workbook.
 
    Per-sheet stacking order:
        static_tables (in dict order)
        {country} General Overview      <- profile_country_kpi_summary
        Country Level - {country}       <- profile_country_kpi_tbl
 
    Parameters
    ----------
    metadata_automated : DataFrame
        Passed straight through to profile_country_kpi_tbl.
    country_list : list[str]
        Countries to loop over. Each becomes a sheet, named after the country.
    quality_cols : list[str]
        Columns cast to int inside profile_country_kpi_tbl.
    static_tables : dict
        The constant tables that appear on every sheet, in display order, e.g.
        {'All Countries': summary_stats_all, ...}.
    skip_missing : bool
        Skip (with a warning) any country that has no rows in the metadata,
        rather than writing an empty table.
    **kwargs
        Any styling arg accepted by _write_tables_to_sheet (gap_rows,
        add_borders, header_bg_color, index, etc.).
    """
    used_names = set()
    written = 0
 
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        for country_iso in country_iso_list:
            country_kpi_table = profile_country_kpi_tbl(metadata_automated, country_iso, quality_cols, kpi_year)
 
            if country_kpi_table.empty and skip_missing:
                print(f"  ! skipped {country}: no rows in metadata")
                continue
 
            country_kpi_summary_output = profile_country_kpi_summary(country_kpi_table, diagnosis_assessment_template)
 
            table_dict = {**static_tables,
                          f'{country_iso} General Overview'  : country_kpi_summary_output,
                          f'Country Level - {country_iso}'   : country_kpi_table}
 
            sheet_name = _unique_sheet_name(country_iso, used_names)
            _write_tables_to_sheet(
                writer,
                table_dict,
                sheet_name=sheet_name,
                index_title=index_title,
                title=title,
                **kwargs,
            )
            written += 1
 
    print(f"Saved: {output_path} ({written} sheet{'s' if written != 1 else ''})")
 