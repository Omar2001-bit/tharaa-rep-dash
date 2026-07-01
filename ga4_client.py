import pandas as pd
import streamlit as st
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    RunReportRequest, Dimension, Metric, DateRange,
    FilterExpression, Filter, FilterExpressionList, OrderBy,
)
import google.analytics.data_v1alpha as data_v1alpha
import config


def _build_client() -> BetaAnalyticsDataClient:
    creds = config.get_credentials()
    if creds:
        return BetaAnalyticsDataClient(credentials=creds)
    return BetaAnalyticsDataClient()  # falls back to ADC


@st.cache_resource
def get_client() -> BetaAnalyticsDataClient:
    return _build_client()


def _build_alpha_client() -> data_v1alpha.AlphaAnalyticsDataClient:
    creds = config.get_credentials()
    if creds:
        return data_v1alpha.AlphaAnalyticsDataClient(credentials=creds)
    return data_v1alpha.AlphaAnalyticsDataClient()


@st.cache_resource
def get_alpha_client() -> data_v1alpha.AlphaAnalyticsDataClient:
    return _build_alpha_client()


@st.cache_data(ttl=3600, show_spinner=False)
def run_funnel_report(steps: tuple, period: tuple, is_open: bool = False) -> pd.DataFrame:
    """
    True GA4 closed (or open) funnel via the Funnel Reporting API — sequential,
    same-user step completion. Not independent per-event counts like run_report.

    steps:  ordered tuple of GA4 event names defining the funnel
    period: (start_date_str, end_date_str)
    is_open: False = closed funnel (must complete steps in order), True = open funnel

    Returns DataFrame: step (e.g. "1. view_item"), activeUsers, completionRate,
    abandonments, abandonmentRate.
    """
    # Funnel Explorations can't filter on 'pagePath' directly (GA4 rejects it), so a
    # page_view used as step 1 is constrained via the raw page_location event param instead —
    # otherwise page_view is too general (matches every page) to anchor a funnel's start.
    _HOMEPAGE_REGEXP = r"^https://(www\.)?tharaa\.shop/(\?.*)?$"

    def _event_filter(step, is_first_step):
        if is_first_step and step == "page_view":
            return data_v1alpha.FunnelEventFilter(
                event_name=step,
                funnel_parameter_filter_expression=data_v1alpha.FunnelParameterFilterExpression(
                    funnel_parameter_filter=data_v1alpha.FunnelParameterFilter(
                        event_parameter_name="page_location",
                        string_filter=data_v1alpha.StringFilter(
                            match_type=data_v1alpha.StringFilter.MatchType.FULL_REGEXP,
                            value=_HOMEPAGE_REGEXP,
                        ),
                    )
                ),
            )
        return data_v1alpha.FunnelEventFilter(event_name=step)

    funnel_steps = [
        data_v1alpha.FunnelStep(
            name=step,
            filter_expression=data_v1alpha.FunnelFilterExpression(
                funnel_event_filter=_event_filter(step, i == 0)
            ),
        )
        for i, step in enumerate(steps)
    ]
    request = data_v1alpha.RunFunnelReportRequest(
        property=config.PROPERTY_ID,
        date_ranges=[data_v1alpha.DateRange(start_date=period[0], end_date=period[1])],
        funnel=data_v1alpha.Funnel(is_open_funnel=is_open, steps=funnel_steps),
    )
    response = get_alpha_client().run_funnel_report(request)

    met_names = [h.name for h in response.funnel_table.metric_headers]
    rows = []
    for row in response.funnel_table.rows:
        vals = [v.value for v in row.metric_values]
        rec = dict(zip(met_names, vals))
        rows.append({
            "step":            row.dimension_values[0].value,
            "activeUsers":     int(float(rec.get("activeUsers", 0))),
            "completionRate":  float(rec.get("funnelStepCompletionRate", 0)),
            "abandonments":    int(float(rec.get("funnelStepAbandonments", 0))),
            "abandonmentRate": float(rec.get("funnelStepAbandonmentRate", 0)),
        })
    return pd.DataFrame(rows)


@st.cache_data(ttl=3600, show_spinner=False,
               hash_funcs={FilterExpression: lambda x: str(x)})
def run_report(
    dimensions: tuple,
    metrics: tuple,
    before: tuple = None,
    after: tuple = None,
    single: tuple = None,
    dim_filter=None,
    order_by_metric: str = None,
    order_desc: bool = True,
    limit: int = 10000,
) -> tuple[pd.DataFrame, int]:
    """
    before/after: (start_date_str, end_date_str)  — comparison report
    single:       (start_date_str, end_date_str)  — single-period report

    When before+after supplied, GA4 injects 'dateRange' as first dimension in
    the response with values matching the names 'before' / 'after'.

    Returns (DataFrame, row_count).
    """
    date_ranges = []
    if before and after:
        date_ranges = [
            DateRange(start_date=before[0], end_date=before[1], name="before"),
            DateRange(start_date=after[0],  end_date=after[1],  name="after"),
        ]
    elif single:
        date_ranges = [DateRange(start_date=single[0], end_date=single[1])]

    order_bys = []
    if order_by_metric:
        order_bys = [OrderBy(
            metric=OrderBy.MetricOrderBy(metric_name=order_by_metric),
            desc=order_desc,
        )]

    request = RunReportRequest(
        property=config.PROPERTY_ID,
        dimensions=[Dimension(name=d) for d in dimensions],
        metrics=[Metric(name=m) for m in metrics],
        date_ranges=date_ranges,
        dimension_filter=dim_filter,
        order_bys=order_bys,
        limit=limit,
    )

    response = get_client().run_report(request)

    dim_names = [h.name for h in response.dimension_headers]
    met_names = [h.name for h in response.metric_headers]

    rows_data = []
    for row in response.rows:
        d_vals = [v.value for v in row.dimension_values]
        m_vals = [v.value for v in row.metric_values]
        rows_data.append(d_vals + m_vals)

    df = pd.DataFrame(rows_data, columns=dim_names + met_names)
    for col in met_names:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    return df, response.row_count


def split_periods(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split a comparison-report DataFrame on the 'dateRange' dimension."""
    before_df = df[df["dateRange"] == "before"].drop(columns=["dateRange"]).reset_index(drop=True)
    after_df  = df[df["dateRange"] == "after"].drop(columns=["dateRange"]).reset_index(drop=True)
    return before_df, after_df


def merge_periods(df: pd.DataFrame, dim_cols: list, metric_cols: list) -> pd.DataFrame:
    """Merge before/after periods side-by-side on dim_cols."""
    b, a = split_periods(df)
    merged = b[dim_cols + metric_cols].merge(
        a[dim_cols + metric_cols],
        on=dim_cols, how="outer", suffixes=("_before", "_after"),
    ).fillna(0)
    return merged


def in_list_filter(field: str, values: list) -> FilterExpression:
    return FilterExpression(
        filter=Filter(
            field_name=field,
            in_list_filter=Filter.InListFilter(values=values),
        )
    )


def string_filter(field: str, value: str,
                  match_type=Filter.StringFilter.MatchType.EXACT) -> FilterExpression:
    return FilterExpression(
        filter=Filter(
            field_name=field,
            string_filter=Filter.StringFilter(match_type=match_type, value=value),
        )
    )


def contains_filter(field: str, value: str) -> FilterExpression:
    return string_filter(field, value, Filter.StringFilter.MatchType.CONTAINS)


def not_filter(expr: FilterExpression) -> FilterExpression:
    return FilterExpression(not_expression=expr)


def or_filter(*exprs) -> FilterExpression:
    return FilterExpression(
        or_group=FilterExpressionList(expressions=list(exprs))
    )


def and_filter(*exprs) -> FilterExpression:
    return FilterExpression(
        and_group=FilterExpressionList(expressions=list(exprs))
    )
