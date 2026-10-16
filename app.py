
import streamlit as st
import pandas as pd
import numpy as np

# =========================
# KONFIGURASI HALAMAN
# =========================
st.set_page_config(
    page_title="Retail Inventory Agent",
    page_icon="📦",
    layout="wide"
)

st.title("📦 Retail Inventory Agent")
st.write(
    "Dashboard untuk memantau persediaan, mengidentifikasi risiko "
    "kekurangan stok, dan mengevaluasi kemungkinan kelebihan stok."
)

# =========================
# KONFIGURASI BATAS RISIKO
# =========================
BATAS_STOK_RENDAH = 0.5
BATAS_STOK_PANTAU = 1.0
BATAS_STOK_AMAN = 1.5


# =========================
# MEMUAT DAN MEMBERSIHKAN DATA
# =========================
@st.cache_data
def load_data():
    df = pd.read_excel("sales_data.xlsx")

    # Membersihkan nama kolom
    df.columns = df.columns.str.strip()

    # Memastikan kolom wajib tersedia
    required_columns = [
        "Date",
        "Store ID",
        "Product ID",
        "Category",
        "Region",
        "Inventory Level",
        "Units Sold",
        "Units Ordered",
        "Demand"
    ]

    missing_columns = [
        col for col in required_columns
        if col not in df.columns
    ]

    if missing_columns:
        raise ValueError(
            "Kolom berikut tidak ditemukan: "
            + ", ".join(missing_columns)
        )

    # Membersihkan tipe data
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    numeric_columns = [
        "Inventory Level",
        "Units Sold",
        "Units Ordered",
        "Demand"
    ]

    for col in numeric_columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # Menghapus baris dengan data utama yang tidak valid
    df = df.dropna(
        subset=[
            "Date",
            "Store ID",
            "Product ID",
            "Inventory Level",
            "Demand"
        ]
    ).copy()

    # Nilai negatif tidak digunakan dalam analisis stok
    df = df[
        (df["Inventory Level"] >= 0)
        & (df["Demand"] >= 0)
    ].copy()

    if df.empty:
        raise ValueError(
            "Tidak ada data valid yang dapat dianalisis."
        )

    # Menghitung rasio persediaan terhadap demand
    df["Stock Ratio"] = np.where(
        df["Demand"] > 0,
        df["Inventory Level"] / df["Demand"],
        np.nan
    )

    # Mengelompokkan risiko persediaan
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

    # =========================
    # MENGHITUNG TREN DEMAND
    # =========================
    # Membandingkan rata-rata 7 data terakhir dengan
    # 7 data sebelumnya untuk setiap kombinasi toko-produk.

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
            trend = ((recent - previous) / previous) * 100

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


# =========================
# MENAMPILKAN DATA
# =========================
try:
    data = load_data()

except Exception as e:
    st.error(f"Gagal memuat aplikasi: {e}")
    st.info(
        "Pastikan sales_data.xlsx berada di repository yang sama "
        "dengan app.py dan requirements.txt sudah benar."
    )
    st.stop()


# =========================
# INFORMASI DATA TERBARU
# =========================
latest_date = data["Date"].max()

latest_data = data[
    data["Date"] == latest_date
].copy()

st.caption(
    f"Analisis menggunakan data terbaru: "
    f"{latest_date.strftime('%d %B %Y')}. "
    "Batas rasio merupakan aturan awal yang perlu divalidasi."
)

# =========================
# SIDEBAR FILTER
# =========================
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
    options=regions,
    default=regions
)

selected_categories = st.sidebar.multiselect(
    "Pilih Kategori Produk",
    options=categories,
    default=categories
)

selected_stores = st.sidebar.multiselect(
    "Pilih Store ID",
    options=stores,
    default=stores
)

# Filter snapshot tanggal terbaru
filtered = latest_data[
    latest_data["Region"].isin(selected_regions)
    & latest_data["Category"].isin(selected_categories)
    & latest_data["Store ID"].isin(selected_stores)
].copy()

# Filter seluruh data untuk analisis tren
filtered_history = data[
    data["Region"].isin(selected_regions)
    & data["Category"].isin(selected_categories)
    & data["Store ID"].isin(selected_stores)
].copy()

if filtered.empty:
    st.warning(
        "Tidak ada data untuk kombinasi filter yang dipilih. "
        "Silakan ubah filter di sidebar."
    )
    st.stop()


# =========================
# RINGKASAN DASHBOARD
# =========================
st.subheader("📊 Ringkasan Persediaan Terbaru")

total_produk_toko = len(filtered)

prioritas_tinggi = (
    filtered["Evaluasi Stok"] == "Prioritas tinggi"
).sum()

perlu_dipantau = (
    filtered["Evaluasi Stok"] == "Perlu dipantau"
).sum()

stok_aman = (
    filtered["Evaluasi Stok"] == "Stok relatif aman"
).sum()

stok_berlebih = (
    filtered["Evaluasi Stok"] == "Evaluasi stok berlebih"
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
    "Perlu Dipantau",
    f"{perlu_dipantau:,}"
)

col4.metric(
    "Evaluasi Stok Berlebih",
    f"{stok_berlebih:,}"
)

st.divider()


# =========================
# DISTRIBUSI RISIKO
# =========================
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

risk_chart = risk_counts[
    risk_counts > 0
].rename_axis("Status").reset_index(name="Jumlah")

if not risk_chart.empty:
    st.bar_chart(
        risk_chart.set_index("Status")["Jumlah"]
    )

st.caption(
    "Klasifikasi ini menggunakan rasio Inventory Level terhadap "
    "Demand, bukan hasil prediksi stok habis yang telah divalidasi."
)

st.divider()


# =========================
# ANALISIS RISIKO KEKURANGAN STOK
# =========================
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
        "atau perlu dipantau pada filter saat ini."
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

    st.write(
        "- Periksa produk berstatus Prioritas Tinggi terlebih dahulu."
    )
    st.write(
        "- Tinjau kebutuhan pemesanan berdasarkan demand dan "
        "lead time pemasok."
    )
    st.write(
        "- Periksa kembali data stok fisik sebelum melakukan pemesanan."
    )

st.divider()


# =========================
# ANALISIS POTENSI STOK BERLEBIH
# =========================
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
        "batas evaluasi pada filter saat ini."
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

    st.write(
        "- Periksa apakah persediaan sesuai dengan kebutuhan penjualan."
    )
    st.write(
        "- Pertimbangkan pemindahan stok ke toko lain jika dibutuhkan."
    )
    st.write(
        "- Evaluasi kembali jumlah pemesanan periode berikutnya."
    )

st.divider()


# =========================
# ANALISIS TREN DEMAND
# =========================
st.subheader("📉 Analisis Tren Demand")

products = sorted(
    filtered_history["Product ID"].dropna().unique().tolist(),
    key=str
)

if products:
    selected_product = st.selectbox(
        "Pilih Product ID untuk melihat tren",
        options=products
    )

    product_history = filtered_history[
        filtered_history["Product ID"] == selected_product
    ].copy()

    product_history = (
        product_history.groupby("Date", as_index=False)
        .agg({
            "Demand": "mean",
            "Units Sold": "mean"
        })
        .sort_values("Date")
    )

    st.line_chart(
        product_history.set_index("Date")[[
            "Demand",
            "Units Sold"
        ]]
    )

    st.caption(
        "Grafik menampilkan rata-rata Demand dan Units Sold "
        "produk yang dipilih pada toko-toko dalam filter."
    )

st.divider()


# =========================
# RINGKASAN TREN PER PRODUK-TOKO
# =========================
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
    "Perubahan demand dihitung dengan membandingkan rata-rata "
    "7 data terakhir dan 7 data sebelumnya pada setiap produk-toko. "
    "Jika data sebelumnya tidak tersedia atau bernilai nol, "
    "perubahan ditampilkan sebagai nilai kosong."
)

st.divider()


# =========================
# TABEL DATA LENGKAP
# =========================
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
    "Perubahan Demand (%)"
]

# Hanya tampilkan kolom yang tersedia
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


# =========================
# DOWNLOAD HASIL ANALISIS
# =========================
st.subheader("⬇️ Unduh Hasil Analisis")

csv_data = filtered[detail_columns].to_csv(
    index=False
).encode("utf-8-sig")

st.download_button(
    label="Download Analisis Persediaan (CSV)",
    data=csv_data,
    file_name="analisis_persediaan.csv",
    mime="text/csv"
)

st.caption(
    "Catatan: batas rasio stok pada dashboard ini adalah asumsi awal. "
    "Untuk keputusan operasional, validasi definisi Demand, periode "
    "data, lead time pemasok, dan stok pengaman terlebih dahulu."
)
