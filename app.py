
import streamlit as st
import pandas as pd
import numpy as np
import math

# ==================================================
# 1. KONFIGURASI HALAMAN
# ==================================================
st.set_page_config(
    page_title="Retail Inventory Agent",
    page_icon="📦",
    layout="wide"
)

st.title("📦 Retail Inventory Agent")
st.write(
    "Dashboard untuk memantau persediaan, memprediksi demand, "
    "dan memberikan rekomendasi pemesanan produk."
)

# Batas awal klasifikasi risiko stok
BATAS_STOK_RENDAH = 0.5
BATAS_STOK_PANTAU = 1.0
BATAS_STOK_AMAN = 1.5


# ==================================================
# 2. MEMUAT DAN MEMBERSIHKAN DATA
# ==================================================
@st.cache_data
def load_data():
    df = pd.read_excel("sales_data.xlsx")

    df.columns = df.columns.str.strip()

    required_columns = [
        "Date",
        "Store ID",
        "Product ID",
        "Category",
        "Region",
        "Inventory Level",
        "Demand"
    ]

    missing_columns = [
        col for col in required_columns
        if col not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            "Kolom tidak ditemukan: "
            + ", ".join(missing_columns)
        )

    df["Date"] = pd.to_datetime(
        df["Date"], errors="coerce"
    )

    numeric_columns = [
        "Inventory Level",
        "Demand",
        "Units Sold",
        "Units Ordered"
    ]

    for col in numeric_columns:
        if col in df.columns:
            df[col] = pd.to_numeric(
                df[col], errors="coerce"
            )

    df = df.dropna(
        subset=[
            "Date",
            "Store ID",
            "Product ID",
            "Inventory Level",
            "Demand"
        ]
    ).copy()

    df = df[
        (df["Inventory Level"] >= 0)
        & (df["Demand"] >= 0)
    ].copy()

    if df.empty:
        raise ValueError("Tidak ada data valid untuk dianalisis.")

    # ----------------------------------------------
    # Rasio stok terhadap demand
    # ----------------------------------------------
    df["Stock Ratio"] = np.where(
        df["Demand"] > 0,
        df["Inventory Level"] / df["Demand"],
        np.nan
    )

    def evaluasi_stok(ratio):
        if pd.isna(ratio):
            return "Demand nol"
        elif ratio <= BATAS_STOK_RENDAH:
            return "Prioritas tinggi"
        elif ratio <= BATAS_STOK_PANTAU:
            return "Perlu dipantau"
        elif ratio <= BATAS_STOK_AMAN:
            return "Stok relatif aman"
        else:
            return "Evaluasi stok berlebih"

    df["Evaluasi Stok"] = df["Stock Ratio"].apply(
        evaluasi_stok
    )

    # ----------------------------------------------
    # Tren demand: 7 data terakhir dibanding 7 data
    # sebelumnya untuk setiap toko dan produk
    # ----------------------------------------------
    trend_rows = []

    for (store_id, product_id), group in df.groupby(
        ["Store ID", "Product ID"]
    ):
        group = group.sort_values("Date")

        recent = group["Demand"].tail(7).mean()
        previous = group["Demand"].iloc[-14:-7].mean()

        if pd.isna(previous) or previous == 0:
            trend = np.nan
        else:
            trend = (recent - previous) / previous * 100

        trend_rows.append({
            "Store ID": store_id,
            "Product ID": product_id,
            "Rata-rata Demand 7 Hari": recent,
            "Perubahan Demand (%)": trend
        })

    trend_df = pd.DataFrame(trend_rows)

    df = df.merge(
        trend_df,
        on=["Store ID", "Product ID"],
        how="left",
        validate="many_to_one"
    )

    return df


# ==================================================
# 3. PREDIKSI DEMAND PER PRODUK DAN TOKO
# ==================================================
def hitung_prediksi(group):
    """
    Weighted Moving Average:
    data paling baru mendapat bobot paling besar.
    Menggunakan maksimal 7 data terakhir.
    """
    group = group.sort_values("Date")
    recent = group["Demand"].tail(7).to_numpy()

    if len(recent) == 0:
        return np.nan

    weights = np.arange(1, len(recent) + 1)

    forecast = np.average(
        recent,
        weights=weights
    )

    return max(0, float(forecast))


def buat_tabel_prediksi(data):
    rows = []

    for (store_id, product_id), group in data.groupby(
        ["Store ID", "Product ID"]
    ):
        group = group.sort_values("Date")

        latest_row = group.iloc[-1]
        daily_forecast = hitung_prediksi(group)

        rows.append({
            "Store ID": store_id,
            "Product ID": product_id,
            "Category": latest_row["Category"],
            "Region": latest_row["Region"],
            "Tanggal Data Terakhir": latest_row["Date"],
            "Inventory Level": latest_row["Inventory Level"],
            "Demand Aktual Terakhir": latest_row["Demand"],
            "Prediksi Demand Harian": daily_forecast
        })

    return pd.DataFrame(rows)


# ==================================================
# 4. MEMUAT APLIKASI
# ==================================================
try:
    data = load_data()

except Exception as e:
    st.error(f"Gagal memuat aplikasi: {e}")
    st.info(
        "Pastikan sales_data.xlsx tersedia di repository "
        "dan requirements.txt berisi streamlit, pandas, "
        "openpyxl, dan numpy."
    )
    st.stop()


latest_date = data["Date"].max()

st.caption(
    f"Data terbaru: {latest_date.strftime('%d %B %Y')}. "
    "Prediksi menggunakan Weighted Moving Average."
)


# ==================================================
# 5. SIDEBAR: FILTER DAN PARAMETER
# ==================================================
st.sidebar.header("🔎 Filter Data")

regions = sorted(
    data["Region"].dropna().unique().tolist(),
    key=str
)

categories = sorted(
    data["Category"].dropna().unique().tolist(),
    key=str
)

stores = sorted(
    data["Store ID"].dropna().unique().tolist(),
    key=str
)

selected_regions = st.sidebar.multiselect(
    "Pilih Region",
    regions,
    default=regions
)

selected_categories = st.sidebar.multiselect(
    "Pilih Kategori",
    categories,
    default=categories
)

selected_stores = st.sidebar.multiselect(
    "Pilih Store ID",
    stores,
    default=stores
)

st.sidebar.divider()
st.sidebar.header("⚙️ Parameter Perencanaan Stok")

forecast_horizon = st.sidebar.slider(
    "Horizon Prediksi (hari)",
    min_value=1,
    max_value=30,
    value=7
)

lead_time = st.sidebar.number_input(
    "Lead Time Pemasok (hari)",
    min_value=0,
    max_value=90,
    value=3,
    step=1,
    help="Perkiraan waktu sejak pemesanan hingga stok diterima."
)

safety_days = st.sidebar.number_input(
    "Stok Pengaman (hari kebutuhan)",
    min_value=0,
    max_value=30,
    value=2,
    step=1,
    help="Tambahan persediaan untuk mengantisipasi ketidakpastian."
)

st.sidebar.caption(
    "Lead time dan stok pengaman adalah parameter asumsi "
    "yang dapat disesuaikan."
)


# ==================================================
# 6. FILTER DATA
# ==================================================
filtered_history = data[
    data["Region"].isin(selected_regions)
    & data["Category"].isin(selected_categories)
    & data["Store ID"].isin(selected_stores)
].copy()

if filtered_history.empty:
    st.warning(
        "Tidak ada data untuk filter yang dipilih. "
        "Silakan ubah filter di sidebar."
    )
    st.stop()

# Snapshot data terbaru secara global
filtered = filtered_history[
    filtered_history["Date"] == latest_date
].copy()

if filtered.empty:
    st.warning("Data terbaru tidak tersedia untuk filter ini.")
    st.stop()


# ==================================================
# 7. MEMBUAT PREDIKSI DAN REKOMENDASI PEMESANAN
# ==================================================
forecast_table = buat_tabel_prediksi(filtered_history)

# Total kebutuhan selama horizon prediksi
forecast_table["Prediksi Total Demand"] = (
    forecast_table["Prediksi Demand Harian"]
    * forecast_horizon
)

# Kebutuhan untuk lead time + stok pengaman
forecast_table["Target Stok"] = (
    forecast_table["Prediksi Demand Harian"]
    * (lead_time + safety_days)
)

# Jumlah stok yang disarankan untuk dipesan
forecast_table["Rekomendasi Pesan"] = (
    forecast_table["Target Stok"]
    - forecast_table["Inventory Level"]
).clip(lower=0).apply(math.ceil)

forecast_table["Status Pemesanan"] = np.where(
    forecast_table["Rekomendasi Pesan"] > 0,
    "Perlu pemesanan",
    "Stok mencukupi"
)

# Menggabungkan hasil prediksi dengan snapshot
filtered = filtered.drop(
    columns=[
        "Prediksi Demand Harian",
        "Prediksi Total Demand",
        "Target Stok",
        "Rekomendasi Pesan",
        "Status Pemesanan"
    ],
    errors="ignore"
)

filtered = filtered.merge(
    forecast_table[
        [
            "Store ID",
            "Product ID",
            "Prediksi Demand Harian",
            "Prediksi Total Demand",
            "Target Stok",
            "Rekomendasi Pesan",
            "Status Pemesanan"
        ]
    ],
    on=["Store ID", "Product ID"],
    how="left",
    validate="one_to_one"
)


# ==================================================
# 8. RINGKASAN DASHBOARD
# ==================================================
st.subheader("📊 Ringkasan Persediaan Terbaru")

total_produk_toko = len(filtered)

prioritas_tinggi = (
    filtered["Evaluasi Stok"] == "Prioritas tinggi"
).sum()

perlu_dipantau = (
    filtered["Evaluasi Stok"] == "Perlu dipantau"
).sum()

stok_berlebih = (
    filtered["Evaluasi Stok"] == "Evaluasi stok berlebih"
).sum()

produk_perlu_pesan = (
    filtered["Rekomendasi Pesan"] > 0
).sum()

col1, col2, col3, col4 = st.columns(4)

col1.metric(
    "Baris Produk-Toko",
    f"{total_produk_toko:,}"
)

col2.metric(
    "Prioritas Tinggi",
    f"{prioritas_tinggi:,}"
)

col3.metric(
    "Potensi Stok Berlebih",
    f"{stok_berlebih:,}"
)

col4.metric(
    "Produk Perlu Dipesan",
    f"{produk_perlu_pesan:,}"
)

st.divider()


# ==================================================
# 9. DISTRIBUSI STATUS STOK
# ==================================================
st.subheader("📈 Distribusi Status Persediaan")

risk_order = [
    "Prioritas tinggi",
    "Perlu dipantau",
    "Stok relatif aman",
    "Evaluasi stok berlebih",
    "Demand nol"
]

risk_counts = (
    filtered["Evaluasi Stok"]
    .value_counts()
    .reindex(risk_order, fill_value=0)
)

risk_counts = risk_counts[risk_counts > 0]

if not risk_counts.empty:
    st.bar_chart(risk_counts)

st.caption(
    "Status stok menggunakan rasio Inventory Level terhadap "
    "Demand pada data terakhir."
)

st.divider()


# ==================================================
# 10. FITUR BARU: PREDIKSI DEMAND
# ==================================================
st.subheader("🔮 Prediksi Demand")

st.write(
    f"Prediksi kebutuhan untuk **{forecast_horizon} hari ke depan** "
    "berdasarkan Weighted Moving Average dari maksimal 7 data terakhir."
)

forecast_display = forecast_table.copy()

forecast_display["Prediksi Demand Harian"] = (
    forecast_display["Prediksi Demand Harian"].round(2)
)

forecast_display["Prediksi Total Demand"] = (
    forecast_display["Prediksi Total Demand"].round(2)
)

forecast_columns = [
    "Store ID",
    "Product ID",
    "Category",
    "Region",
    "Demand Aktual Terakhir",
    "Prediksi Demand Harian",
    "Prediksi Total Demand"
]

st.dataframe(
    forecast_display[forecast_columns].sort_values(
        by=["Store ID", "Product ID"],
        key=lambda col: col.astype(str)
    ),
    use_container_width=True,
    hide_index=True
)

st.caption(
    "Prediksi total demand dihitung dari prediksi demand harian "
    "dikalikan jumlah hari pada horizon. Ini merupakan estimasi "
    "baseline, bukan jaminan kebutuhan aktual."
)

# Grafik prediksi satu produk pada satu toko
st.markdown("#### Grafik Prediksi per Produk dan Toko")

product_options = sorted(
    forecast_table["Product ID"].dropna().unique().tolist(),
    key=str
)

if product_options:
    selected_product = st.selectbox(
        "Pilih Product ID",
        product_options,
        key="forecast_product"
    )

    store_options = sorted(
        forecast_table.loc[
            forecast_table["Product ID"] == selected_product,
            "Store ID"
        ].dropna().unique().tolist(),
        key=str
    )

    if store_options:
        selected_store = st.selectbox(
            "Pilih Store ID untuk grafik",
            store_options,
            key="forecast_store"
        )

        history_chart = filtered_history[
            (filtered_history["Product ID"] == selected_product)
            & (filtered_history["Store ID"] == selected_store)
        ].sort_values("Date").tail(30)

        actual_chart = history_chart[
            ["Date", "Demand"]
        ].rename(columns={"Demand": "Demand Aktual"})

        actual_chart = actual_chart.set_index("Date")

        daily_prediction = forecast_table[
            (forecast_table["Product ID"] == selected_product)
            & (forecast_table["Store ID"] == selected_store)
        ]["Prediksi Demand Harian"]

        if not daily_prediction.empty:
            daily_prediction = float(daily_prediction.iloc[0])

            future_dates = pd.date_range(
                start=latest_date + pd.Timedelta(days=1),
                periods=forecast_horizon,
                freq="D"
            )

            future_chart = pd.DataFrame({
                "Tanggal": future_dates,
                "Prediksi Demand": [
                    daily_prediction
                ] * forecast_horizon
            }).set_index("Tanggal")

            st.write("Demand aktual — maksimal 30 data terakhir")
            st.line_chart(actual_chart)

            st.write("Prediksi demand untuk periode mendatang")
            st.line_chart(future_chart)

st.divider()


# ==================================================
# 11. FITUR BARU: REKOMENDASI PEMESANAN
# ==================================================
st.subheader("🛒 Rekomendasi Pemesanan Otomatis")

st.write(
    "Sistem menghitung estimasi jumlah pemesanan agar persediaan "
    "mencukupi kebutuhan selama lead time ditambah stok pengaman."
)

st.markdown(
    """
    **Logika perhitungan**

    - Target stok = prediksi demand harian × (lead time + stok pengaman)
    - Rekomendasi pesan = maksimum dari 0 dan (target stok − stok saat ini)
    - Jumlah pemesanan dibulatkan ke atas menjadi bilangan bulat.
    """
)

order_data = forecast_table[
    forecast_table["Rekomendasi Pesan"] > 0
].copy()

if order_data.empty:
    st.success(
        "Tidak ada produk yang perlu dipesan berdasarkan parameter "
        "dan data yang sedang dipilih."
    )
else:
    order_data = order_data.sort_values(
        by="Rekomendasi Pesan",
        ascending=False
    )

    order_columns = [
        "Store ID",
        "Product ID",
        "Category",
        "Region",
        "Inventory Level",
        "Prediksi Demand Harian",
        "Target Stok",
        "Rekomendasi Pesan",
        "Status Pemesanan"
    ]

    order_display = order_data[order_columns].copy()

    order_display["Prediksi Demand Harian"] = (
        order_display["Prediksi Demand Harian"].round(2)
    )

    order_display["Target Stok"] = (
        order_display["Target Stok"].round(2)
    )

    st.dataframe(
        order_display,
        use_container_width=True,
        hide_index=True
    )

    total_recommended_units = int(
        order_data["Rekomendasi Pesan"].sum()
    )

    st.metric(
        "Total Unit yang Disarankan untuk Dipesan",
        f"{total_recommended_units:,}"
    )

    st.write("**Rekomendasi tindakan:**")
    st.write(
        "- Prioritaskan produk dengan jumlah pemesanan tertinggi."
    )
    st.write(
        "- Periksa stok fisik dan pesanan yang sedang dalam perjalanan."
    )
    st.write(
        "- Konfirmasikan lead time dan jumlah pesanan minimum pemasok."
    )
    st.write(
        "- Sesuaikan jumlah akhir berdasarkan kapasitas penyimpanan "
        "dan kebijakan pemesanan."
    )

st.divider()


# ==================================================
# 12. RISIKO KEKURANGAN STOK
# ==================================================
st.subheader("🚨 Risiko Kekurangan Stok")

shortage_data = filtered[
    filtered["Evaluasi Stok"].isin([
        "Prioritas tinggi",
        "Perlu dipantau"
    ])
].copy()

shortage_data = shortage_data.sort_values(
    by="Stock Ratio",
    ascending=True,
    na_position="last"
)

if shortage_data.empty:
    st.success(
        "Tidak ditemukan produk dengan status prioritas tinggi "
        "atau perlu dipantau."
    )
else:
    shortage_columns = [
        "Store ID",
        "Product ID",
        "Category",
        "Region",
        "Inventory Level",
        "Demand",
        "Stock Ratio",
        "Evaluasi Stok"
    ]

    st.dataframe(
        shortage_data[shortage_columns],
        use_container_width=True,
        hide_index=True
    )

    st.write("**Rekomendasi awal:**")
    st.write("- Periksa produk dengan rasio stok paling rendah.")
    st.write("- Bandingkan hasil risiko dengan rekomendasi pemesanan.")
    st.write("- Pastikan data stok dan demand sudah benar.")

st.divider()


# ==================================================
# 13. POTENSI STOK BERLEBIH
# ==================================================
st.subheader("📦 Potensi Stok Berlebih")

excess_data = filtered[
    filtered["Evaluasi Stok"] == "Evaluasi stok berlebih"
].copy()

excess_data = excess_data.sort_values(
    by="Stock Ratio",
    ascending=False,
    na_position="last"
)

if excess_data.empty:
    st.info(
        "Tidak ditemukan produk dengan rasio stok di atas "
        "batas evaluasi."
    )
else:
    excess_columns = [
        "Store ID",
        "Product ID",
        "Category",
        "Region",
        "Inventory Level",
        "Demand",
        "Stock Ratio",
        "Evaluasi Stok"
    ]

    st.dataframe(
        excess_data[excess_columns],
        use_container_width=True,
        hide_index=True
    )

    st.write("**Rekomendasi awal:**")
    st.write("- Evaluasi kembali kebutuhan pemesanan produk.")
    st.write("- Periksa kemungkinan pemindahan stok antar-toko.")
    st.write("- Pastikan produk tidak mengalami perubahan pola demand.")

st.divider()


# ==================================================
# 14. TREN DEMAND HISTORIS
# ==================================================
st.subheader("📉 Tren Demand Historis")

history_products = sorted(
    filtered_history["Product ID"].dropna().unique().tolist(),
    key=str
)

if history_products:
    selected_history_product = st.selectbox(
        "Pilih produk untuk melihat tren historis",
        history_products,
        key="history_product"
    )

    product_history = filtered_history[
        filtered_history["Product ID"] == selected_history_product
    ].copy()

    product_history = (
        product_history.groupby("Date", as_index=False)
        .agg({"Demand": "mean"})
        .sort_values("Date")
    )

    st.line_chart(
        product_history.set_index("Date")["Demand"]
    )

st.divider()


# ==================================================
# 15. TREN PER PRODUK DAN TOKO
# ==================================================
st.subheader("📌 Perubahan Demand per Produk dan Toko")

trend_latest = filtered[
    [
        "Store ID",
        "Product ID",
        "Category",
        "Region",
        "Rata-rata Demand 7 Hari",
        "Perubahan Demand (%)"
    ]
].copy()

trend_latest = trend_latest.sort_values(
    by="Perubahan Demand (%)",
    ascending=False,
    na_position="last"
)

st.dataframe(
    trend_latest,
    use_container_width=True,
    hide_index=True
)

st.caption(
    "Perubahan demand membandingkan rata-rata 7 data terakhir "
    "dengan 7 data sebelumnya. Jika data sebelumnya tidak tersedia "
    "atau bernilai nol, perubahan ditampilkan kosong."
)

st.divider()


# ==================================================
# 16. TABEL DETAIL DAN DOWNLOAD
# ==================================================
st.subheader("📋 Detail Persediaan Terbaru")

detail_columns = [
    "Date",
    "Store ID",
    "Product ID",
    "Category",
    "Region",
    "Inventory Level",
    "Units Sold",
    "Units Ordered",
    "Demand",
    "Stock Ratio",
    "Evaluasi Stok",
    "Rata-rata Demand 7 Hari",
    "Perubahan Demand (%)",
    "Prediksi Demand Harian",
    "Prediksi Total Demand",
    "Target Stok",
    "Rekomendasi Pesan",
    "Status Pemesanan"
]

detail_columns = [
    col for col in detail_columns
    if col in filtered.columns
]

st.dataframe(
    filtered[detail_columns].sort_values(
        by=["Store ID", "Product ID"],
        key=lambda col: col.astype(str)
    ),
    use_container_width=True,
    hide_index=True
)

st.subheader("⬇️ Unduh Hasil Analisis")

csv_data = filtered[detail_columns].to_csv(
    index=False
).encode("utf-8-sig")

st.download_button(
    label="Download Analisis Persediaan (CSV)",
    data=csv_data,
    file_name="retail_inventory_analysis.csv",
    mime="text/csv"
)

st.caption(
    "Catatan: prediksi menggunakan Weighted Moving Average sederhana. "
    "Kualitas hasil bergantung pada data historis. Rekomendasi pemesanan "
    "belum memperhitungkan pesanan yang sedang berjalan, minimum order "
    "quantity, kapasitas penyimpanan, atau biaya persediaan."
)
