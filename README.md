# Olist Brazilian E-Commerce Insights — Streamlit App

An interactive Olist analytics application with local SQL Server support and a hosted CSV mode for deployment.

## Features

- Executive Overview with order, order-item value, payment and review KPIs
- Sales & Products analysis with monthly, category, weekday, hourly and freight views
- Customers & Regions with state/city breakdowns and one-time vs repeat buyer analysis
- Delivery & Satisfaction with delivery-time, late-delivery and review-score views
- Sellers & Payments with seller contribution and payment-method analysis
- Data Explorer with SQL table previews and a missing-value / duplicate-row overview
- Predictive Model Lab with notebook evaluation metrics, class-level scores, and feature correlation heatmap

## Run on Windows

1. Extract the project folder.
2. Install Python 3.10 or newer.
3. Open Command Prompt or PowerShell in this folder.
4. Run:

```powershell
py -3.10 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

The app should open in your browser at the local Streamlit address shown in the terminal.

You can also double-click `run_app.bat`; it uses the Python 3.10 launcher entry, installs the listed dependencies and launches the application. If Python 3.10 is not installed, adjust the `-3.10` selector to a Python version installed on your PC.

## Local SQL Server connection

For local Windows use, create `.streamlit/secrets.toml` with:

```toml
[sqlserver]
server = "YOUR_SQL_SERVER_INSTANCE"
database = "YOUR_DATABASE_NAME"
driver = "ODBC Driver 17 for SQL Server"
trusted_connection = true
```

Install the Microsoft ODBC Driver 17 for SQL Server and the Python `pyodbc` package listed in `requirements.txt`. The Windows account running Streamlit must have access to the database. Do not expose a laptop SQL Server to the public internet.

The app reads these tables from the `dbo` schema: customers, orders, order_items, order_payments, order_reviews, products, sellers, and product_category_name_translation.

The app applies these cleaning steps after loading:

- Product category translations are applied, with original category names retained when translations are unavailable.
- Duplicate `review_id` records are reduced to the latest record.
- Order-item value is calculated as `price + freight_value` and is explicitly **not** treated as profit.
- Payment value is calculated separately from the payment table.
- Delivery performance is calculated at order level, so multi-item orders are not counted multiple times.

The geolocation CSV is included as a source file but is not loaded into the main dashboard. The current regional dashboard uses customer and seller state/city fields, so loading the much larger ZIP-prefix location file is not needed for those views.

## Important metric definitions

- **Order-item value:** Sum of product price plus freight value across order items. It is not profit.
- **Payment value:** Sum of `payment_value` rows from the payments table. This is kept separate from order-item value.
- **Average order value:** Order-item value divided by the number of distinct orders represented by order items in the current filter context. This follows the supplied Python notebook definition. The existing Power BI overview shows a slightly different AOV because its displayed total and denominator use a different basis; keep the definitions separate when comparing the two.
- **Late delivery rate:** Delivered orders with an actual customer delivery timestamp later than the estimated delivery timestamp divided by delivered orders with both actual and estimated delivery timestamps.
- **Repeat buyer rate:** Share of customers with more than one delivered order in the available history.

## Deploy on Streamlit Community Cloud

The hosted app cannot reach SQL Server running on your laptop. For deployment, keep the GitHub repository free of CSV data and host the required CSV files in a public Hugging Face Dataset repository. The data source files are the eight tables listed above; `geolocation.csv` is not needed by the app.

In Streamlit Community Cloud, create the app from your GitHub repository and set these values under **Advanced settings → Secrets**. Replace the Hugging Face account and dataset names with yours:

```toml
[auth]
username = "your-demo-user-id"
password = "choose-a-strong-demo-password"

[data_source]
mode = "csv"

[dataset_urls]
customers = "https://huggingface.co/datasets/YOUR_HF_USERNAME/YOUR_DATASET/resolve/main/customers.csv?download=true"
orders = "https://huggingface.co/datasets/YOUR_HF_USERNAME/YOUR_DATASET/resolve/main/orders.csv?download=true"
order_items = "https://huggingface.co/datasets/YOUR_HF_USERNAME/YOUR_DATASET/resolve/main/order_items.csv?download=true"
order_payments = "https://huggingface.co/datasets/YOUR_HF_USERNAME/YOUR_DATASET/resolve/main/order_payments.csv?download=true"
order_reviews = "https://huggingface.co/datasets/YOUR_HF_USERNAME/YOUR_DATASET/resolve/main/order_reviews.csv?download=true"
products = "https://huggingface.co/datasets/YOUR_HF_USERNAME/YOUR_DATASET/resolve/main/products.csv?download=true"
sellers = "https://huggingface.co/datasets/YOUR_HF_USERNAME/YOUR_DATASET/resolve/main/sellers.csv?download=true"
product_category_name_translation = "https://huggingface.co/datasets/YOUR_HF_USERNAME/YOUR_DATASET/resolve/main/product_category_name_translation.csv?download=true"
```

Use cleaned, non-sensitive project data only. Do not commit the dataset, `.streamlit/secrets.toml`, Hugging Face tokens, or login password to GitHub. Set `mode = "csv"` only in the Community Cloud app's Secrets; local runs continue to use SQL Server by default. The app login uses the `[auth]` values from those Secrets.

Include `app.py`, `requirements.txt`, `README.md`, and `.gitignore` in the app repository. Do not add the local `data/` folder or `.streamlit/secrets.toml`.

## Notes

- The model page reports the notebook's saved test-set metrics; it does not generate live predictions because no serialized model file is included.
- The login is required and must be configured in Streamlit Community Cloud Secrets before the app can show project data.

