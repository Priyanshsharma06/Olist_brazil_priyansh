from __future__ import annotations

import hmac
from typing import Dict, Tuple

import os
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

try:
    import pyodbc
except ImportError:  # CSV mode on Streamlit Community Cloud does not require SQL Server.
    pyodbc = None

st.set_page_config(
    page_title="Olist | E-Commerce Insights",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

# A restrained theme that mirrors the project's navy / teal presentation palette.
NAVY = "#172536"
TEAL = "#19A7A1"
MINT = "#D9F3EF"
SLATE = "#657786"
PALETTE = ["#19A7A1", "#416788", "#7BAE9D", "#E3A857", "#9B8AC4", "#D17A70", "#7D8B99"]

st.markdown(
    """
    <style>
    .stApp { background: #F5F7FA; color: #172536; }
    [data-testid="stSidebar"] { background: #172536; }
      [data-testid="stSidebar"] * { color: #F4F7FA !important; }
    [data-testid="stMetric"] { background: white; padding: 14px 16px; border: 1px solid #E5EAF0; border-radius: 12px; }
    [data-testid="stMetricLabel"] { color: #657786; }
    [data-testid="stMetricValue"] { color: #172536; }
    .hero { background: linear-gradient(110deg, #172536 0%, #25465A 62%, #19A7A1 100%); padding: 26px 30px; border-radius: 16px; color: white; margin-bottom: 18px; }
    .hero h1 { color: white; margin: 0 0 6px 0; font-size: 2rem; }
    .hero p { color: #E8F4F4; margin: 0; font-size: 1rem; }
    .section-note { color: #657786; font-size: 0.9rem; }
    .insight { background: #E9F6F4; border-left: 4px solid #19A7A1; padding: 12px 16px; border-radius: 8px; margin: 8px 0 16px; }
    .warning { background: #FFF6E8; border-left: 4px solid #E3A857; padding: 12px 16px; border-radius: 8px; margin: 8px 0 16px; }
    h1, h2, h3 { color: #172536; }
    div[data-testid="stDataFrame"] { background: white; border-radius: 10px; }
    </style>
    """,
    unsafe_allow_html=True,
)

REQUIRED_TABLES = {
    "customers": "customers",
    "orders": "orders",
    "order_items": "order_items",
    "order_payments": "order_payments",
    "order_reviews": "order_reviews",
    "products": "products",
    "sellers": "sellers",
    "category_translation": "product_category_name_translation",
}


def _sqlserver_settings() -> Dict[str, object]:
    """Read SQL Server settings from Streamlit secrets or deployment environment variables."""
    try:
        settings = dict(st.secrets.get("sqlserver", {}))
    except Exception:
        settings = {}

    env_settings = {
        "server": os.getenv("SQLSERVER_SERVER"),
        "database": os.getenv("SQLSERVER_DATABASE"),
        "driver": os.getenv("SQLSERVER_DRIVER"),
        "username": os.getenv("SQLSERVER_USERNAME"),
        "password": os.getenv("SQLSERVER_PASSWORD"),
        "trusted_connection": os.getenv("SQLSERVER_TRUSTED_CONNECTION"),
    }
    for key, value in env_settings.items():
        if value is not None and key not in settings:
            settings[key] = value
    return settings


def _data_source_settings() -> Dict[str, object]:
    """Read the selected data source and optional hosted CSV URLs."""
    try:
        settings = dict(st.secrets.get("data_source", {}))
    except Exception:
        settings = {}
    return settings


def _odbc_value(value: object) -> str:
    """Brace-quote an ODBC connection-string value safely."""
    return "{" + str(value).replace("}", "}}") + "}"


def _sqlserver_connection_string() -> str:
    settings = _sqlserver_settings()
    server = settings.get("server")
    database = settings.get("database")
    driver = settings.get("driver", "ODBC Driver 17 for SQL Server")
    if not server or not database:
        raise RuntimeError(
            "SQL Server is not configured. Set server and database in .streamlit/secrets.toml."
        )

    parts = [
        f"DRIVER={_odbc_value(driver)}",
        f"SERVER={_odbc_value(server)}",
        f"DATABASE={_odbc_value(database)}",
        "Encrypt=yes",
        "TrustServerCertificate=yes",
    ]
    trusted_value = settings.get("trusted_connection", True)
    trusted = str(trusted_value).strip().lower() in {"1", "true", "yes"}
    username = settings.get("username")
    password = settings.get("password")

    if trusted:
        parts.append("Trusted_Connection=yes")
    elif username and password:
        parts.extend([f"UID={_odbc_value(username)}", f"PWD={_odbc_value(password)}"])
    else:
        raise RuntimeError(
            "SQL Server authentication is incomplete. Use Windows authentication locally, "
            "or provide username and password through deployment secrets."
        )
    return ";".join(parts) + ";"


def _read_sql_tables() -> Dict[str, pd.DataFrame]:
    """Load the required source tables directly from SQL Server."""
    if pyodbc is None:
        raise RuntimeError("Install pyodbc to use the SQL Server data source.")
    connection_string = _sqlserver_connection_string()
    with pyodbc.connect(connection_string, timeout=15) as connection:
        return {
            key: pd.read_sql_query(f"SELECT * FROM [dbo].[{table}]", connection)
            for key, table in REQUIRED_TABLES.items()
        }


@st.cache_data(show_spinner="Loading hosted CSV tables and preparing the analysis tables...")
def _read_csv_tables() -> Dict[str, pd.DataFrame]:
    """Load the required tables from hosted CSV URLs or local CSV files."""
    try:
        urls = dict(st.secrets.get("dataset_urls", {}))
    except Exception:
        urls = {}

    project_root = Path(__file__).resolve().parent
    local_data_dir = project_root / "data"
    raw: Dict[str, pd.DataFrame] = {}
    for key, table in REQUIRED_TABLES.items():
        filename = f"{table}.csv"
        url = urls.get(key) or urls.get(table)
        path = local_data_dir / filename
        source = url or (str(path) if path.exists() else None)
        if not source:
            raise RuntimeError(
                f"No CSV source configured for '{table}'. Add its URL under "
                f"[dataset_urls] in Streamlit Secrets, or place {filename} in data/."
            )
        try:
            raw[key] = pd.read_csv(source, low_memory=False)
        except Exception as exc:
            raise RuntimeError(f"Could not read CSV data for '{table}'. Check the URL and access.") from exc
    return raw


@st.cache_data(show_spinner="Loading SQL Server tables and preparing the analysis tables...")
def load_project_data() -> Dict[str, pd.DataFrame]:
    """Load the configured source tables and apply the project's cleaning logic."""
    mode = str(_data_source_settings().get("mode", "sql")).strip().lower()
    if mode == "csv":
        raw = _read_csv_tables()
    elif mode == "sql":
        raw = _read_sql_tables()
    else:
        raise RuntimeError("Invalid data_source.mode. Choose 'sql' or 'csv'.")

    orders = raw["orders"].copy()
    customers = raw["customers"].copy()
    items = raw["order_items"].copy()
    payments = raw["order_payments"].copy()
    reviews = raw["order_reviews"].copy()
    products = raw["products"].copy()
    sellers = raw["sellers"].copy()
    translation = raw["category_translation"].copy()

    # Align the key timestamps with the analysis notebook.
    date_cols = [
        "order_purchase_timestamp", "order_approved_at", "order_delivered_carrier_date",
        "order_delivered_customer_date", "order_estimated_delivery_date",
    ]
    for col in date_cols:
        if col in orders.columns:
            orders[col] = pd.to_datetime(orders[col], errors="coerce")

    for col in ["review_creation_date", "review_answer_timestamp"]:
        if col in reviews.columns:
            reviews[col] = pd.to_datetime(reviews[col], errors="coerce")

    # Mirror the SQL product-cleaning logic: English label where available, otherwise original label.
    products = products.merge(translation, on="product_category_name", how="left")
    products["product_category_name_english"] = products[
        "product_category_name_english"
    ].fillna(products["product_category_name"])
    products["product_category_name_english"] = products[
        "product_category_name_english"
    ].fillna("Unclassified")

    # Keep the latest record per review_id, matching the SQL ROW_NUMBER cleaning step.
    if "review_id" in reviews.columns:
        sort_cols = [c for c in ["review_creation_date", "review_answer_timestamp"] if c in reviews.columns]
        reviews = reviews.sort_values(sort_cols) if sort_cols else reviews
        reviews = reviews.drop_duplicates(subset=["review_id"], keep="last")

    # Build the order-item fact table. Each row represents one product line in an order.
    sales = items.merge(orders, on="order_id", how="left", validate="many_to_one")
    sales = sales.merge(
        products[["product_id", "product_category_name_english"]],
        on="product_id", how="left", validate="many_to_one",
    )
    sales = sales.merge(
        customers[["customer_id", "customer_unique_id", "customer_city", "customer_state"]],
        on="customer_id", how="left", validate="many_to_one",
    )
    sales = sales.merge(
        sellers[["seller_id", "seller_city", "seller_state"]],
        on="seller_id", how="left", validate="many_to_one",
    )

    sales["total_revenue"] = sales["price"].fillna(0) + sales["freight_value"].fillna(0)
    sales["year_month"] = sales["order_purchase_timestamp"].dt.to_period("M").astype(str)
    sales["weekday"] = sales["order_purchase_timestamp"].dt.day_name()
    sales["purchase_hour"] = sales["order_purchase_timestamp"].dt.hour
    sales["freight_percentage"] = np.where(
        sales["price"].gt(0), sales["freight_value"] / sales["price"] * 100, np.nan
    )

    # Order-level delivery calculations prevent multi-item orders from being counted repeatedly.
    delivery = orders[[
        "order_id", "customer_id", "order_status", "order_purchase_timestamp",
        "order_delivered_customer_date", "order_estimated_delivery_date",
    ]].copy()
    delivery["delivery_days"] = (
        delivery["order_delivered_customer_date"] - delivery["order_purchase_timestamp"]
    ).dt.total_seconds() / 86400
    has_delivery_dates = (
        delivery["order_delivered_customer_date"].notna()
        & delivery["order_estimated_delivery_date"].notna()
    )
    is_late = delivery["order_delivered_customer_date"] > delivery["order_estimated_delivery_date"]
    delivery["delivery_status"] = np.select(
        [~has_delivery_dates, is_late], ["Unknown", "Late"], default="On Time"
    )
    delivery.loc[delivery["order_status"] != "delivered", "delivery_status"] = "Not delivered"
    delivery = delivery.merge(
        customers[["customer_id", "customer_unique_id", "customer_state", "customer_city"]],
        on="customer_id", how="left", validate="many_to_one",
    )

    # Recreate the order-level model inputs used in the notebook.
    model_rows = raw["order_reviews"].drop_duplicates("order_id").merge(
        orders[[
            "order_id", "order_purchase_timestamp", "order_approved_at",
            "order_delivered_carrier_date", "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ]], on="order_id", how="inner",
    )
    seller_agg = items.groupby("order_id", as_index=False).agg(
        unique_sellers=("seller_id", "nunique"),
        total_items=("order_item_id", "count"),
    )
    model_rows = model_rows.merge(seller_agg, on="order_id", how="left")
    model_rows["review_score"] = pd.to_numeric(model_rows["review_score"], errors="coerce")
    model_rows = model_rows[model_rows["review_score"].notna()].copy()
    model_rows["review_creation_date"] = pd.to_datetime(
        model_rows["review_creation_date"], errors="coerce"
    )
    model_rows["delivery_days"] = (
        model_rows["order_delivered_customer_date"] - model_rows["order_purchase_timestamp"]
    ).dt.days.fillna(0)
    model_rows["delay_days"] = (
        model_rows["order_delivered_customer_date"] - model_rows["order_estimated_delivery_date"]
    ).dt.days.fillna(0)
    model_rows["transit_days"] = (
        model_rows["order_delivered_customer_date"] - model_rows["order_delivered_carrier_date"]
    ).dt.days.fillna(0)
    model_rows["carrier_handoff_days"] = (
        model_rows["order_delivered_carrier_date"] - model_rows["order_approved_at"]
    ).dt.days.fillna(0)
    model_rows["survey_before_delivery"] = (
        model_rows["order_delivered_customer_date"] > model_rows["review_creation_date"]
    ).astype(int)
    model_rows["is_late"] = (model_rows["delay_days"] > 0).astype(int)
    model_rows["unique_sellers"] = model_rows["unique_sellers"].fillna(1)
    model_rows["total_items"] = model_rows["total_items"].fillna(1)
    model_feature_names = [
        "delay_days", "is_late", "delivery_days", "transit_days",
        "carrier_handoff_days", "survey_before_delivery", "unique_sellers", "total_items",
    ]

    return {
        **raw,
        "model_features": model_rows[model_feature_names],
        "model_targets": np.where(
            model_rows["review_score"] <= 2,
            "Negative [1-2]",
            np.where(model_rows["review_score"] == 3, "Neutral [3]", "Positive [4-5]"),
        ),
        "orders_clean": orders,
        "products_clean": products,
        "reviews_clean": reviews,
        "sales": sales,
        "delivery": delivery,
    }


@st.cache_resource(show_spinner="Training the review-score prediction model...")
def fit_review_model(features: pd.DataFrame, targets: pd.Series):
    """Train the notebook's balanced multinomial model once per app process."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import train_test_split

    x_train, _, y_train, _ = train_test_split(
        features, targets, test_size=0.20, random_state=42
    )
    model = LogisticRegression(
        class_weight="balanced",
        max_iter=1000,
        random_state=42,
    )
    model.fit(x_train, y_train)
    return model


def money(value: float) -> str:
    if pd.isna(value):
        return "R$ 0"
    if abs(value) >= 1_000_000:
        return f"R$ {value / 1_000_000:,.2f}M"
    if abs(value) >= 1_000:
        return f"R$ {value / 1_000:,.1f}K"
    return f"R$ {value:,.2f}"


def metric_row(items: list[Tuple[str, str, str]]) -> None:
    cols = st.columns(len(items))
    for col, (label, value, help_text) in zip(cols, items):
        col.metric(label, value, help=help_text)


def make_bar(data: pd.DataFrame, x: str, y: str, title: str, horizontal: bool = False):
    if data.empty:
        st.info("No data available for the selected filters.")
        return
    if horizontal:
        fig = px.bar(data, x=x, y=y, orientation="h", color_discrete_sequence=[TEAL])
        fig.update_layout(yaxis={"categoryorder": "total ascending"})
    else:
        fig = px.bar(data, x=x, y=y, color_discrete_sequence=[TEAL])
    fig.update_layout(title=title, template="plotly_white", margin=dict(l=12, r=12, t=55, b=12), height=360)
    st.plotly_chart(fig, use_container_width=True)


def show_table(df: pd.DataFrame, height: int = 300) -> None:
    st.dataframe(df, use_container_width=True, height=height, hide_index=True)


def require_login() -> None:
    """Require app credentials stored in Streamlit Secrets before showing project data."""
    try:
        auth = dict(st.secrets.get("auth", {}))
    except Exception:
        auth = {}
    expected_username = str(auth.get("username", ""))
    expected_password = str(auth.get("password", ""))
    if not expected_username or not expected_password:
        mode = str(_data_source_settings().get("mode", "sql")).strip().lower()
        if mode == "csv":
            st.error("App login is not configured. Add username and password in Streamlit Secrets.")
            st.stop()
        return

    if st.session_state.get("authenticated", False):
        with st.sidebar:
            if st.button("Log out"):
                st.session_state["authenticated"] = False
                st.rerun()
        return

    st.title("Olist E-Commerce Insights")
    st.subheader("Sign in")
    with st.form("login_form"):
        username = st.text_input("User ID")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log in", use_container_width=True)
    if submitted:
        username_ok = hmac.compare_digest(username, expected_username)
        password_ok = hmac.compare_digest(password, expected_password)
        if username_ok and password_ok:
            st.session_state["authenticated"] = True
            st.rerun()
        st.error("Incorrect User ID or password.")
    st.stop()


require_login()


try:
    data = load_project_data()
except Exception as exc:
    st.error("The app could not load the data.")
    st.exception(exc)
    st.stop()

orders = data["orders_clean"]
customers = data["customers"]
sales = data["sales"]
payments = data["order_payments"]
reviews = data["reviews_clean"]
delivery = data["delivery"]
sellers = data["sellers"]

# -----------------------------------------------------------------------------
# Navigation and shared filters
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("# 🛒 OLIST")
    st.caption("Brazilian E-Commerce Analytics")
    page = st.radio(
        "NAVIGATION",
        [
            "Executive Overview", "Sales & Products", "Customers & Regions",
            "Delivery & Satisfaction", "Sellers & Payments", "Data Explorer",
            "Predictive Model Lab",
        ],
    )
    st.divider()
    st.markdown("### Global filters")
    valid_dates = orders["order_purchase_timestamp"].dropna()
    years = sorted(valid_dates.dt.year.unique().tolist())
    year_options = ["All years"] + [str(y) for y in years]
    selected_year = st.selectbox("Order year", year_options, index=0)
    states = sorted(customers["customer_state"].dropna().astype(str).unique().tolist())
    state_options = ["All states"] + states
    selected_state = st.selectbox("Customer state", state_options, index=0)
    status_options = ["All statuses"] + sorted(orders["order_status"].dropna().astype(str).unique().tolist())
    selected_status = st.selectbox("Order status", status_options, index=0)
    st.divider()
    st.caption("Source: supplied Olist Brazilian E-Commerce CSV extracts.")

orders_f = orders.copy()
if selected_year != "All years":
    orders_f = orders_f[orders_f["order_purchase_timestamp"].dt.year == int(selected_year)]
if selected_status != "All statuses":
    orders_f = orders_f[orders_f["order_status"] == selected_status]
if selected_state != "All states":
    state_customer_ids = set(customers.loc[customers["customer_state"] == selected_state, "customer_id"])
    orders_f = orders_f[orders_f["customer_id"].isin(state_customer_ids)]

order_ids = set(orders_f["order_id"].dropna())
sales_f = sales[sales["order_id"].isin(order_ids)].copy()
payments_f = payments[payments["order_id"].isin(order_ids)].copy()
reviews_f = reviews[reviews["order_id"].isin(order_ids)].copy()
delivery_f = delivery[delivery["order_id"].isin(order_ids)].copy()

# -----------------------------------------------------------------------------
# Header
# -----------------------------------------------------------------------------
page_subtitles = {
    "Executive Overview": "A quick view of marketplace activity, order value, payments and customer experience.",
    "Sales & Products": "Understand when orders happen, which categories generate value and how products perform.",
    "Customers & Regions": "Explore customer reach, repeat buying and geographic concentration.",
    "Delivery & Satisfaction": "Connect delivery performance with the experience reported by customers.",
    "Sellers & Payments": "Review seller contribution and the ways customers pay for their orders.",
    "Data Explorer": "Inspect the source tables and review core data-quality checks.",
    "Predictive Model Lab": "Review-score model performance, class-level results and business interpretation.",
}
st.markdown(
    f'<div class="hero"><h1>Olist | {page}</h1><p>{page_subtitles[page]}</p></div>',
    unsafe_allow_html=True,
)
st.caption(
    f"Current view: {selected_year} · {selected_state} · {selected_status} · "
    f"{len(order_ids):,} orders in the filtered order set"
)

# -----------------------------------------------------------------------------
# Page: Executive Overview
# -----------------------------------------------------------------------------
if page == "Executive Overview":
    item_value = float(sales_f["total_revenue"].sum())
    payment_value = float(payments_f["payment_value"].sum())
    order_count = int(orders_f["order_id"].nunique())
    customer_count = int(customers[customers["customer_id"].isin(orders_f["customer_id"])]["customer_unique_id"].nunique())
    aov = item_value / sales_f["order_id"].nunique() if sales_f["order_id"].nunique() else 0
    delivered = orders_f[orders_f["order_status"] == "delivered"]
    delivered_count = int(delivered["order_id"].nunique())
    review_avg = reviews_f["review_score"].mean() if not reviews_f.empty else np.nan
    metric_row([
        ("Total orders", f"{order_count:,}", "Unique order IDs after applying filters."),
        ("Order-item value", money(item_value), "Product price + freight; this is not profit."),
        ("Payment value", money(payment_value), "Sum of payment records. Kept separate from order-item value."),
        ("Customers", f"{customer_count:,}", "Distinct customer_unique_id in the filtered order set."),
        ("Delivered orders", f"{delivered_count:,}", "Orders whose status is delivered."),
        ("Average order value", money(aov), "Order-item value divided by orders with order items."),
        ("Average review", f"{review_avg:.2f}/5" if pd.notna(review_avg) else "N/A", "Mean of available review scores."),
    ])
    st.markdown(
        '<div class="warning"><b>Metric note:</b> Order-item value = product price + freight. '
        'It is not profit. Payment value comes from the separate payment table and is shown independently.</div>',
        unsafe_allow_html=True,
    )
    c1, c2 = st.columns([1.25, 1])
    with c1:
        monthly = sales_f.dropna(subset=["order_purchase_timestamp"]).groupby("year_month", as_index=False).agg(
            order_item_value=("total_revenue", "sum"), orders=("order_id", "nunique")
        ).sort_values("year_month")
        if not monthly.empty:
            fig = px.line(monthly, x="year_month", y="order_item_value", markers=True, title="Monthly order-item value")
            fig.update_traces(line_color=TEAL)
            fig.update_layout(template="plotly_white", height=350, xaxis_title="Order month", yaxis_title="Order-item value (R$)")
            st.plotly_chart(fig, use_container_width=True)
    with c2:
        status = orders_f["order_status"].value_counts().rename_axis("Order status").reset_index(name="Orders")
        fig = px.bar(status, x="Orders", y="Order status", orientation="h", title="Order status distribution", color_discrete_sequence=[SLATE])
        fig.update_layout(template="plotly_white", height=350, yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, use_container_width=True)
    c3, c4 = st.columns(2)
    with c3:
        method = payments_f.groupby("payment_type", as_index=False)["payment_value"].sum().sort_values("payment_value", ascending=False)
        fig = px.pie(method, names="payment_type", values="payment_value", hole=0.55, title="Payment value by payment method", color_discrete_sequence=PALETTE)
        fig.update_layout(height=350, margin=dict(t=55, b=10))
        st.plotly_chart(fig, use_container_width=True)
    with c4:
        score = reviews_f["review_score"].value_counts().sort_index().rename_axis("Review score").reset_index(name="Reviews")
        fig = px.bar(score, x="Review score", y="Reviews", title="Customer review distribution", color_discrete_sequence=[TEAL])
        fig.update_layout(template="plotly_white", height=350, xaxis=dict(dtick=1))
        st.plotly_chart(fig, use_container_width=True)
    st.markdown('<div class="insight"><b>How to read this page:</b> Start with order volume and order-item value, then compare order status, payment methods and customer reviews. The filters on the left update all visuals together.</div>', unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Page: Sales & Products
# -----------------------------------------------------------------------------
elif page == "Sales & Products":
    category_options = sorted(sales_f["product_category_name_english"].dropna().astype(str).unique().tolist())
    selected_categories = st.multiselect("Product categories", category_options, default=[], help="Empty selection means all categories.")
    view = sales_f[sales_f["product_category_name_english"].isin(selected_categories)].copy() if selected_categories else sales_f.copy()
    order_value = view.groupby("order_id", as_index=False)["total_revenue"].sum()
    metric_row([
        ("Items sold", f"{len(view):,}", "Rows in the order-item table after filters."),
        ("Categories", f"{view['product_category_name_english'].nunique():,}", "Distinct product category labels."),
        ("Products", f"{view['product_id'].nunique():,}", "Distinct product IDs represented in filtered orders."),
        ("Order-item value", money(view["total_revenue"].sum()), "Product price + freight; not profit."),
        ("Average order value", money(order_value["total_revenue"].mean() if not order_value.empty else 0), "Average value per order with items."),
        ("Average freight", money(view["freight_value"].mean() if not view.empty else 0), "Average freight per order item."),
    ])
    c1, c2 = st.columns(2)
    with c1:
        category = view.groupby("product_category_name_english", as_index=False).agg(
            order_item_value=("total_revenue", "sum"), items=("order_item_id", "count")
        ).nlargest(10, "order_item_value")
        make_bar(category.sort_values("order_item_value"), "order_item_value", "product_category_name_english", "Top categories by order-item value", horizontal=True)
    with c2:
        items_cat = view.groupby("product_category_name_english", as_index=False).agg(items=("order_item_id", "count")).nlargest(10, "items")
        make_bar(items_cat.sort_values("items"), "items", "product_category_name_english", "Top categories by items sold", horizontal=True)
    c3, c4 = st.columns(2)
    with c3:
        monthly = view.groupby("year_month", as_index=False).agg(orders=("order_id", "nunique"), order_item_value=("total_revenue", "sum")).sort_values("year_month")
        fig = px.line(monthly, x="year_month", y="orders", markers=True, title="Orders by month")
        fig.update_traces(line_color=TEAL)
        fig.update_layout(template="plotly_white", height=340, xaxis_title="Order month", yaxis_title="Unique orders")
        st.plotly_chart(fig, use_container_width=True)
    with c4:
        weekday_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        weekday = view.groupby("weekday")["order_id"].nunique().reindex(weekday_order).dropna().rename_axis("Weekday").reset_index(name="Orders")
        fig = px.bar(weekday, x="Weekday", y="Orders", title="Orders by day of week", color_discrete_sequence=[SLATE])
        fig.update_layout(template="plotly_white", height=340)
        st.plotly_chart(fig, use_container_width=True)
    c5, c6 = st.columns(2)
    with c5:
        hourly = view.groupby("purchase_hour")["order_id"].nunique().reindex(range(24), fill_value=0).rename_axis("Purchase hour").reset_index(name="Orders")
        fig = px.line(hourly, x="Purchase hour", y="Orders", markers=True, title="Orders by hour of day")
        fig.update_traces(line_color=TEAL)
        fig.update_layout(template="plotly_white", height=340, xaxis=dict(dtick=2))
        st.plotly_chart(fig, use_container_width=True)
    with c6:
        scatter_data = view[["price", "freight_value"]].dropna()
        if len(scatter_data) > 7000:
            scatter_data = scatter_data.sample(7000, random_state=42)
        fig = px.scatter(scatter_data, x="price", y="freight_value", opacity=0.45, title="Product price vs freight value", color_discrete_sequence=[TEAL])
        fig.update_layout(template="plotly_white", height=340, xaxis_title="Product price (R$)", yaxis_title="Freight value (R$)")
        st.plotly_chart(fig, use_container_width=True)
    st.markdown('<div class="insight"><b>Business meaning:</b> Category charts show where order-item value and volume are concentrated. Day/hour charts help identify shopping patterns. The price-versus-freight chart helps spot items where shipping cost may be comparatively high.</div>', unsafe_allow_html=True)
    st.download_button("Download filtered sales rows (CSV)", view.to_csv(index=False).encode("utf-8"), "olist_filtered_sales.csv", "text/csv")

# -----------------------------------------------------------------------------
# Page: Customers & Regions
# -----------------------------------------------------------------------------
elif page == "Customers & Regions":
    customers_in_scope = customers[customers["customer_id"].isin(orders_f["customer_id"])].copy()
    delivered_orders = orders_f[orders_f["order_status"] == "delivered"]
    cust_order_counts = delivered_orders.merge(
        customers[["customer_id", "customer_unique_id"]], on="customer_id", how="left", validate="many_to_one"
    ).groupby("customer_unique_id", as_index=False).agg(delivered_orders=("order_id", "nunique"))
    unique_buyers = cust_order_counts["customer_unique_id"].nunique()
    repeat_buyers = int((cust_order_counts["delivered_orders"] > 1).sum())
    repeat_rate = repeat_buyers / unique_buyers * 100 if unique_buyers else 0
    customer_value = sales_f.groupby("customer_unique_id")["total_revenue"].sum()
    avg_customer_value = customer_value.mean() if not customer_value.empty else 0
    metric_row([
        ("Unique customers", f"{customers_in_scope['customer_unique_id'].nunique():,}", "Distinct customer_unique_id values in the filtered orders."),
        ("States", f"{customers_in_scope['customer_state'].nunique():,}", "States represented among filtered customers."),
        ("Cities", f"{customers_in_scope['customer_city'].nunique():,}", "Cities represented among filtered customers."),
        ("Repeat buyer rate", f"{repeat_rate:.1f}%", "Share of delivered customers with more than one delivered order."),
        ("Average customer order-item value", money(avg_customer_value), "Average sum of item price + freight by customer in this filtered view."),
    ])
    c1, c2 = st.columns(2)
    with c1:
        city = customers_in_scope.groupby("customer_city", as_index=False)["customer_unique_id"].nunique().nlargest(10, "customer_unique_id")
        make_bar(city.sort_values("customer_unique_id"), "customer_unique_id", "customer_city", "Top cities by unique customers", horizontal=True)
    with c2:
        state = sales_f.groupby("customer_state", as_index=False).agg(order_item_value=("total_revenue", "sum"), orders=("order_id", "nunique")).nlargest(12, "order_item_value")
        make_bar(state.sort_values("order_item_value"), "order_item_value", "customer_state", "Top states by order-item value", horizontal=True)
    c3, c4 = st.columns(2)
    with c3:
        state_orders = orders_f.merge(customers[["customer_id", "customer_state"]], on="customer_id", how="left", validate="many_to_one").groupby("customer_state", as_index=False)["order_id"].nunique().nlargest(12, "order_id")
        make_bar(state_orders.sort_values("order_id"), "order_id", "customer_state", "Top states by order volume", horizontal=True)
    with c4:
        purchase_mix = pd.DataFrame({"Customer type": ["One-time", "Repeat"], "Customers": [unique_buyers - repeat_buyers, repeat_buyers]})
        fig = px.pie(purchase_mix, names="Customer type", values="Customers", hole=0.55, title="One-time vs repeat buyers", color_discrete_sequence=[SLATE, TEAL])
        fig.update_layout(height=360)
        st.plotly_chart(fig, use_container_width=True)
    st.markdown('<div class="insight"><b>Business meaning:</b> Regional views show where customers and order value are concentrated. Repeat buyer rate indicates how many delivered customers purchased more than once in the available order history.</div>', unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Page: Delivery & Satisfaction
# -----------------------------------------------------------------------------
elif page == "Delivery & Satisfaction":
    delivered = delivery_f[delivery_f["order_status"] == "delivered"].copy()
    delivered = delivered[delivered["delivery_days"].notna()]
    valid_delivery = delivered[delivered["delivery_status"].isin(["Late", "On Time"])]
    late = valid_delivery[valid_delivery["delivery_status"] == "Late"]
    late_rate = len(late) / len(valid_delivery) * 100 if len(valid_delivery) else 0
    mean_delivery = delivered["delivery_days"].mean() if len(delivered) else np.nan
    review_mean = reviews_f["review_score"].mean() if not reviews_f.empty else np.nan
    metric_row([
        ("Delivered orders", f"{delivered['order_id'].nunique():,}", "Delivered orders with usable delivery timestamps."),
        ("Late delivery rate", f"{late_rate:.2f}%", "Delivered orders arriving after the estimated delivery date."),
        ("Average delivery days", f"{mean_delivery:.1f}" if pd.notna(mean_delivery) else "N/A", "Purchase timestamp to customer delivery timestamp."),
        ("Average review score", f"{review_mean:.2f}/5" if pd.notna(review_mean) else "N/A", "Mean review score after review de-duplication."),
        ("Reviews", f"{len(reviews_f):,}", "Latest retained row per review_id."),
    ])
    c1, c2 = st.columns(2)
    with c1:
        delivery_mix = valid_delivery["delivery_status"].value_counts().rename_axis("Delivery status").reset_index(name="Orders")
        fig = px.pie(delivery_mix, names="Delivery status", values="Orders", hole=0.55, title="On-time vs late delivered orders", color_discrete_sequence=[TEAL, "#D17A70"])
        fig.update_layout(height=350)
        st.plotly_chart(fig, use_container_width=True)
    with c2:
        review_dist = reviews_f["review_score"].value_counts().sort_index().rename_axis("Review score").reset_index(name="Reviews")
        fig = px.bar(review_dist, x="Review score", y="Reviews", title="Review score distribution", color_discrete_sequence=[SLATE])
        fig.update_layout(template="plotly_white", height=350, xaxis=dict(dtick=1))
        st.plotly_chart(fig, use_container_width=True)
    c3, c4 = st.columns(2)
    with c3:
        state_delivery = delivered.groupby("customer_state", as_index=False).agg(avg_delivery_days=("delivery_days", "mean"), delivered_orders=("order_id", "nunique")).nlargest(15, "avg_delivery_days")
        make_bar(state_delivery.sort_values("avg_delivery_days"), "avg_delivery_days", "customer_state", "States with highest average delivery time", horizontal=True)
    with c4:
        review_delivery = valid_delivery[["order_id", "delivery_status"]].merge(reviews_f[["order_id", "review_score"]], on="order_id", how="inner")
        if not review_delivery.empty:
            group = review_delivery.groupby("delivery_status", as_index=False).agg(avg_review_score=("review_score", "mean"), reviews=("review_score", "count"))
            fig = px.bar(group, x="delivery_status", y="avg_review_score", text="avg_review_score", title="Average review score by delivery status", color="delivery_status", color_discrete_map={"Late": "#D17A70", "On Time": TEAL})
            fig.update_traces(texttemplate="%{text:.2f}", textposition="outside")
            fig.update_layout(template="plotly_white", height=350, yaxis=dict(range=[0, 5]))
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No reviews linked to delivered orders match the selected filters.")
    st.markdown('<div class="warning"><b>Interpretation note:</b> Late-delivery rate uses only delivered orders with both actual and estimated delivery timestamps. Average delivery days uses delivered orders with a valid actual delivery timestamp. Review scores are customer feedback, not a direct measure of delivery performance alone.</div>', unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Page: Sellers & Payments
# -----------------------------------------------------------------------------
elif page == "Sellers & Payments":
    paid_value = payments_f["payment_value"].sum()
    avg_installment = payments_f["payment_installments"].mean() if not payments_f.empty else np.nan
    seller_items = sales_f[sales_f["order_status"] == "delivered"].groupby(["seller_id", "seller_state"], as_index=False).agg(
        order_item_value=("total_revenue", "sum"), items_sold=("order_item_id", "count"), orders=("order_id", "nunique")
    )
    metric_row([
        ("Sellers with sales", f"{seller_items['seller_id'].nunique():,}", "Distinct sellers with delivered order items in the filtered view."),
        ("Payment value", money(paid_value), "Sum of payment_value from payment records."),
        ("Average installments", f"{avg_installment:.2f}" if pd.notna(avg_installment) else "N/A", "Mean installment count across payment records."),
        ("Payment methods", f"{payments_f['payment_type'].nunique():,}", "Distinct payment types in the filtered view."),
    ])
    c1, c2 = st.columns(2)
    with c1:
        seller_state = seller_items.groupby("seller_state", as_index=False)["order_item_value"].sum().nlargest(12, "order_item_value")
        make_bar(seller_state.sort_values("order_item_value"), "order_item_value", "seller_state", "Delivered order-item value by seller state", horizontal=True)
    with c2:
        top_sellers = seller_items.nlargest(10, "order_item_value").copy()
        top_sellers["seller_label"] = top_sellers["seller_id"].astype(str).str.slice(0, 12) + "…"
        make_bar(top_sellers.sort_values("order_item_value"), "order_item_value", "seller_label", "Top sellers by delivered order-item value", horizontal=True)
    c3, c4 = st.columns(2)
    with c3:
        payment_method = payments_f.groupby("payment_type", as_index=False).agg(payment_value=("payment_value", "sum"), orders=("order_id", "nunique")).sort_values("payment_value", ascending=False)
        make_bar(payment_method, "payment_value", "payment_type", "Payment value by payment method", horizontal=True)
    with c4:
        installment = payments_f.groupby("payment_type", as_index=False)["payment_installments"].mean().sort_values("payment_installments", ascending=False)
        fig = px.bar(installment, x="payment_type", y="payment_installments", title="Average installments by payment method", color_discrete_sequence=[TEAL])
        fig.update_layout(template="plotly_white", height=350, yaxis_title="Average installments")
        st.plotly_chart(fig, use_container_width=True)
    st.markdown('<div class="insight"><b>Business meaning:</b> Seller-state and seller-level charts help compare marketplace supply-side contribution. Payment charts show how customers pay and how installment use differs by payment method.</div>', unsafe_allow_html=True)
    if not seller_items.empty:
        st.download_button("Download seller performance table (CSV)", seller_items.to_csv(index=False).encode("utf-8"), "olist_seller_performance.csv", "text/csv")

# -----------------------------------------------------------------------------
# Page: Data Explorer
# -----------------------------------------------------------------------------
elif page == "Data Explorer":
    st.write("Explore the source tables used by the application. Geolocation is provided in the project package but is not loaded into the main dashboard because it is a high-volume ZIP-prefix lookup table and the current dashboard views use customer and seller state fields.")
    table_map = {
        "customers": data["customers"],
        "orders": data["orders_clean"],
        "order_items": data["order_items"],
        "order_payments": data["order_payments"],
        "order_reviews (cleaned by review_id)": data["reviews_clean"],
        "products (English category applied)": data["products_clean"],
        "sellers": data["sellers"],
        "category translation": data["category_translation"],
    }
    quality_rows = []
    for name, frame in table_map.items():
        missing_cells = int(frame.isna().sum().sum())
        total_cells = int(frame.shape[0] * frame.shape[1])
        quality_rows.append({
            "Table": name,
            "Rows": len(frame),
            "Columns": frame.shape[1],
            "Duplicate rows": int(frame.duplicated().sum()),
            "Missing cells": missing_cells,
            "Missing cell %": round(missing_cells / total_cells * 100, 3) if total_cells else 0,
        })
    quality = pd.DataFrame(quality_rows)
    st.subheader("Dataset inventory and quality overview")
    show_table(quality, 340)
    selected_table = st.selectbox("Choose a table to preview", list(table_map.keys()))
    preview = table_map[selected_table]
    st.caption(f"Showing up to 500 rows from {len(preview):,} available rows.")
    show_table(preview.head(500), 420)
    st.download_button("Download selected table preview (CSV)", preview.head(500).to_csv(index=False).encode("utf-8"), "olist_table_preview.csv", "text/csv")
    st.markdown('<div class="warning"><b>Data quality note:</b> Missing values and duplicate rows are reported, not silently deleted. Whether a missing value should be removed, retained or imputed depends on the field and the business question.</div>', unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Page: Predictive Model Lab
# -----------------------------------------------------------------------------
elif page == "Predictive Model Lab":
    st.subheader("Customer review-score prediction")
    st.markdown(
        "The model classifies reviews as Negative (1–2), Neutral (3), or Positive (4–5)."
    )

    # Evaluation results copied from MODEL-internship.ipynb (20% test split, random_state=42).
    labels = ["Negative [1-2]", "Neutral [3]", "Positive [4-5]"]
    short_labels = ["Negative", "Neutral", "Positive"]
    support = [2906, 1619, 15102]
    confusion = np.array([[1600, 485, 821], [331, 439, 849], [1530, 3118, 10454]])
    report = pd.DataFrame({
        "Review class": labels,
        "Precision": [0.4623, 0.1086, 0.8623],
        "Recall": [0.5506, 0.2712, 0.6922],
        "F1 score": [0.5026, 0.1551, 0.7679],
        "Test examples": support,
    })
    test_n = sum(support)
    majority_baseline = max(support) / test_n

    metric_cols = st.columns(5)
    metric_cols[0].metric("Accuracy", "63.65%")
    metric_cols[1].metric("Macro F1", "0.4752")
    metric_cols[2].metric("Weighted F1", "0.6781")
    metric_cols[3].metric("Balanced accuracy", "50.47%")
    metric_cols[4].metric("Majority baseline", f"{majority_baseline:.2%}")

    st.caption(
        f"Held-out test set: {test_n:,} examples · 80/20 split."
    )

    st.markdown("#### Try a live review-score prediction")
    st.caption(
        "Enter delivery and order characteristics to estimate the review class. "
        "The prediction is an estimate based on historical Olist data."
    )
    st.caption(
        "Use a delivered order. Dates come from the orders table; seller and item counts come from order_items. "
        "Hover over each field's info icon for its definition."
    )
    with st.form("live_review_prediction"):
        input_col1, input_col2, input_col3 = st.columns(3)
        with input_col1:
            st.markdown("**Days early or late vs. estimate**")
            delay_days = st.number_input(
                "Days early or late vs. estimate",
                min_value=-60,
                max_value=365,
                value=0,
                help="Use actual delivery date minus estimated delivery date from the orders table. Negative = early; 0 = on time; positive = late.",,
                label_visibility="collapsed"
            )
            st.markdown("**Total delivery time (days)**")
            delivery_days = st.number_input(
                "Total delivery time (days)", min_value=0, max_value=365, value=12,
                help="Actual customer delivery date minus purchase timestamp from the orders table.",,
                label_visibility="collapsed"
            )
            st.markdown("**Carrier-to-customer transit (days)**")
            transit_days = st.number_input(
                "Carrier-to-customer transit (days)", min_value=0, max_value=365, value=7,
                help="Actual delivery date minus the date the order was handed to the carrier.",,
                label_visibility="collapsed"
            )
        with input_col2:
            st.markdown("**Approval-to-carrier handoff (days)**")
            carrier_handoff_days = st.number_input(
                "Approval-to-carrier handoff (days)",
                min_value=0,
                max_value=180,
                value=2,
                help="Carrier handoff date minus order approval date, in whole days.",,
                label_visibility="collapsed"
            )
            st.markdown("**Sellers in the order**")
            unique_sellers = st.number_input(
                "Sellers in the order", min_value=1, max_value=50, value=1,
                help="Count of distinct seller IDs in the order's item lines.",,
                label_visibility="collapsed"
            )
        with input_col3:
            st.markdown("**Items in the order**")
            total_items = st.number_input(
                "Items in the order", min_value=1, max_value=100, value=1,
                help="Number of order-item lines for this order.",,
                label_visibility="collapsed"
            )
            st.markdown("**Review survey timing**")
            survey_timing = st.radio(
                "Review survey timing",
                ["After delivery", "Before delivery"],
                help="Choose Before delivery if review_creation_date is earlier than order_delivered_customer_date; otherwise choose After delivery.",
                label_visibility="collapsed",
            )
        predict_clicked = st.form_submit_button(
            "Predict review class", type="primary", use_container_width=True
        )

    if predict_clicked:
        prediction_features = pd.DataFrame([{
            "delay_days": float(delay_days),
            "is_late": int(delay_days > 0),
            "delivery_days": float(delivery_days),
            "transit_days": float(transit_days),
            "carrier_handoff_days": float(carrier_handoff_days),
            "survey_before_delivery": int(survey_timing == "Before delivery"),
            "unique_sellers": float(unique_sellers),
            "total_items": float(total_items),
        }], columns=data["model_features"].columns)
        prediction_targets = pd.Series(data["model_targets"], name="review_class")
        try:
            review_model = fit_review_model(data["model_features"], prediction_targets)
            predicted_class = review_model.predict(prediction_features)[0]
            class_probabilities = pd.DataFrame({
                "Review class": review_model.classes_,
                "Probability": review_model.predict_proba(prediction_features)[0],
            }).sort_values("Probability", ascending=False)
            result_col, confidence_col = st.columns(2)
            result_col.metric("Predicted review class", predicted_class)
            confidence_col.metric(
                "Highest class probability",
                f"{class_probabilities.iloc[0]['Probability']:.1%}",
            )
            probability_chart = px.bar(
                class_probabilities,
                x="Review class",
                y="Probability",
                color="Review class",
                color_discrete_map={
                    "Negative [1-2]": "#D17A70",
                    "Neutral [3]": "#E3A857",
                    "Positive [4-5]": TEAL,
                },
                range_y=[0, 1],
                text_auto=".1%",
            )
            probability_chart.update_layout(
                template="plotly_white",
                yaxis_tickformat=".0%",
                yaxis_title="Estimated probability",
                xaxis_title="",
                showlegend=False,
                height=300,
                margin=dict(l=10, r=10, t=15, b=10),
            )
            st.plotly_chart(probability_chart, use_container_width=True)
            st.caption(
                "Class probabilities are model estimates, not guarantees. "
                "The model is trained on the project's historical review and delivery data."
            )
        except Exception as exc:
            st.error("The live prediction could not be generated.")
            st.exception(exc)

    left, right = st.columns([1, 1.2], gap="large")
    with left:
        st.markdown("#### Confusion matrix")
        heatmap = go.Figure(data=go.Heatmap(
            z=confusion,
            x=short_labels,
            y=short_labels,
            colorscale=[[0, "#E9F6F4"], [1, TEAL]],
            text=confusion,
            texttemplate="%{text:,}",
            hovertemplate="Actual: %{y}<br>Predicted: %{x}<br>Orders: %{z:,}<extra></extra>",
            colorbar_title="Examples",
        ))
        heatmap.update_layout(
            xaxis_title="Predicted class",
            yaxis_title="Actual class",
            margin=dict(l=10, r=10, t=10, b=10),
            height=390,
        )
        st.plotly_chart(heatmap, use_container_width=True)
        st.caption("Rows are actual classes; columns are model predictions. Diagonal cells are correct predictions.")

    with right:
        st.markdown("#### Precision, recall and F1 by class")
        score_long = report.melt(
            id_vars="Review class", value_vars=["Precision", "Recall", "F1 score"],
            var_name="Metric", value_name="Score",
        )
        score_chart = px.bar(
            score_long, x="Review class", y="Score", color="Metric", barmode="group",
            range_y=[0, 1], text_auto=".0%",
            color_discrete_sequence=[TEAL, "#416788", "#E3A857"],
        )
        score_chart.update_layout(
            yaxis_tickformat=".0%", yaxis_title="Score", xaxis_title="",
            legend_title="", margin=dict(l=10, r=10, t=10, b=10), height=390,
        )
        st.plotly_chart(score_chart, use_container_width=True)

    st.markdown("#### Test-set class report")
    display_report = report.copy()
    for col in ["Precision", "Recall", "F1 score"]:
        display_report[col] = display_report[col].map(lambda value: f"{value:.2%}")
    display_report["Test share"] = [f"{n / test_n:.2%}" for n in support]
    show_table(display_report, 190)

    st.markdown("#### Feature correlation")
    feature_corr = data["model_features"].corr(numeric_only=True)
    corr_fig = go.Figure(go.Heatmap(
        z=feature_corr.values,
        x=feature_corr.columns.tolist(),
        y=feature_corr.index.tolist(),
        zmin=-1,
        zmax=1,
        zmid=0,
        colorscale="RdBu",
        text=np.round(feature_corr.values, 2),
        texttemplate="%{text:.2f}",
        hovertemplate="Feature A: %{x}<br>Feature B: %{y}<br>Correlation: %{z:.2f}<extra></extra>",
        colorbar_title="Pearson r",
    ))
    corr_fig.update_layout(
        xaxis_title="",
        yaxis_title="",
        xaxis_tickangle=45,
        height=650,
        margin=dict(l=190, r=20, t=20, b=170),
    )
    st.plotly_chart(corr_fig, use_container_width=True)
    st.caption("Pearson correlation across the eight numeric model inputs. The review class is excluded.")

    st.markdown("#### Key findings")
    st.markdown(
        '<div class="insight"><b>Class imbalance:</b> Positive reviews make up '
        f'{majority_baseline:.2%} of the test set. Accuracy (63.65%) is below the majority-class '
        'baseline (76.95%); use class-level recall alongside accuracy.</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<div class="warning"><b>Neutral reviews are hardest to identify:</b> Neutral precision is '
        '10.86%, recall is 27.12%, and F1 is 15.51%.</div>',
        unsafe_allow_html=True,
    )
    st.markdown(
        "**Model:** Balanced multinomial Logistic Regression · **Features:** delivery timing, "
        "late-delivery status, survey timing, seller count, and item count."
    )
    st.info(
        "Notebook test results; filters do not change these scores. The form above trains the same "
        "balanced Logistic Regression model from the project data and returns a live prediction."
    )

st.divider()
st.caption("Olist Brazilian E-Commerce Analytics · Built with Streamlit, pandas and Plotly · Values are calculated from the supplied project CSV files.")

