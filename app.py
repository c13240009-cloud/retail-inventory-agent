
import streamlit as st
import pandas as pd
import numpy as np

st.set_page_config(
    page_title="Retail Inventory Agent",
    page_icon="📦",
    layout="wide"
)


@st.cache_data
def load_data():
    data = pd.read_excel("sales_data.xlsx")
    data["Date"] = pd.to_datetime(data["Date"], errors="coerce")

    numeric_cols = [
        "Inventory Level", "Demand", "Units Sold", "Units Ordered"
    ]
    for col in numeric_cols:
        data[col] = pd.to_numeric(data[col], errors="coerce")

    data = data.dropna(
        subset=["Date", "Store ID", "Product ID", "Inventory Level", "Demand"]
    )

    data["Stock Ratio"] = (
        data["Inventory Level"]
        / data["Demand"].replace(0, np.nan)
    )

    def evaluate(ratio):
        if pd.isna(ratio):
            return "Demand tidak valid"
        elif ratio <= 0.5:
            return "Prioritas tinggi"
        elif ratio <= 1.0:
            return "Perlu dipantau"
        elif ratio <= 1.5:
            return "Stok relatif aman"
        return "Evaluasi stok berlebih"

    data["Evaluasi Stok"] = data["Stock Ratio"].apply(evaluate)

    data = data.sort_values("Date")

    # Bandingkan rata-rata Demand 7 hari terakhir dengan 7 hari sebelumnya
    def calculate_trend(group):
        group = group.sort_values("Date").copy()
        recent = group["Demand"].tail(7).mean()
        previous = group["Demand"].iloc[-14:-7].mean()

        if pd.isna(previous) or previous == 0:
            trend = np.nan
        else:
            trend = ((recent - previous) / previous) * 100

        group["Rata-rata Demand 7 Hari"] = recent
        group["Perubahan Demand (%)"] = trend
        return group

    data = (
        data.groupby(["Store ID", "Product ID"], group_keys=False)
        .apply(calculate_trend)
        .reset_index(drop=True)
    )

    return data


def recommendation(row):
    ratio = row["Stock Ratio"]
    trend = row["Perubahan Demand (%)"]

    if pd.isna(ratio):
        return "Periksa data Demand terlebih dahulu."

    if ratio <= 0.5:
        action = (
            "Prioritaskan pemeriksaan ketersediaan stok "
            "dan kebutuhan pengisian ulang."
        )
    elif ratio <= 1.0:
        action = (
            "Pantau persediaan dan periksa perubahan permintaan."
        )
    elif ratio <= 1.5:
        action = (
            "Pantau kondisi stok secara berkala."
        )
    else:
        action = (
            "Evaluasi potensi stok berlebih sebelum melakukan "
            "pemesanan berikutnya."
        )

    if pd.notna(trend):
        if trend >= 10:
            action += " Demand naik dibandingkan 7 hari sebelumnya."
        elif trend <= -10:
            action += " Demand turun dibandingkan 7 hari sebelumnya."

    return action


try:
    df = load_data()

    st.title("📦 Retail Inventory Agent")
    st.caption(
        "Analisis risiko persediaan, tren permintaan, "
        "dan rekomendasi pemeriksaan stok"
    )

    latest_date = df["Date"].max()
    snapshot = df[df["Date"] == latest_date].copy()

    st.info(
        f"Analisis risiko menggunakan data terbaru: "
        f"{latest_date:%d %B %Y}. "
        "Batas rasio merupakan aturan awal yang perlu divalidasi."
    )

    # Filter
    st.sidebar.header("Filter Data")

    regions = sorted(snapshot["Region"].dropna().unique())
    categories = sorted(snapshot["Category"].dropna().unique())
    stores = sorted(snapshot["Store ID"].dropna().unique())

    selected_regions = st.sidebar.multiselect(
        "Pilih Region", regions, default=regions
    )
    selected_categories = st.sidebar.multiselect(
        "Pilih Category", categories, default=categories
    )
    selected_stores = st.sidebar.multiselect(
        "Pilih Store ID", stores, default=stores
    )

    filtered = snapshot[
        snapshot["Region"].isin(selected_regions)
        & snapshot["Category"].isin(selected_categories)
        & snapshot["Store ID"].isin(selected_stores)
    ].copy()

    if filtered.empty:
        st.warning("Tidak ada data untuk kombinasi filter tersebut.")
        st.stop()

    # Metrik utama
    st.subheader("Ringkasan Risiko Persediaan")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Produk-Toko Dianalisis", f"{len(filtered):,}")
    c2.metric(
        "Prioritas Tinggi",
        int((filtered["Evaluasi Stok"] == "Prioritas tinggi").sum())
    )
    c3.metric(
        "Perlu Dipantau",
        int((filtered["Evaluasi Stok"] == "Perlu dipantau").sum())
    )
    c4.metric(
        "Potensi Stok Berlebih",
        int(
            (filtered["Evaluasi Stok"] == "Evaluasi stok berlebih").sum()
        )
    )

    # Distribusi risiko
    st.subheader("Distribusi Evaluasi Stok")

    order = [
        "Prioritas tinggi",
        "Perlu dipantau",
        "Stok relatif aman",
        "Evaluasi stok berlebih",
        "Demand tidak valid"
    ]

    counts = (
        filtered["Evaluasi Stok"]
        .value_counts()
        .reindex(order, fill_value=0)
    )

    st.bar_chart(counts, horizontal=True)

    # Analisis produk berisiko
    st.subheader("Produk dengan Risiko Kekurangan Stok")

    shortage = filtered[
        filtered["Evaluasi Stok"].isin(
            ["Prioritas tinggi", "Perlu dipantau"]
        )
    ].sort_values("Stock Ratio", ascending=True).head(10).copy()

    if shortage.empty:
        st.success("Tidak ada produk dalam kategori risiko awal ini.")
    else:
        shortage["Rekomendasi"] = shortage.apply(recommendation, axis=1)
        st.dataframe(
            shortage[
                [
                    "Store ID", "Product ID", "Category", "Region",
                    "Inventory Level", "Demand", "Stock Ratio",
                    "Perubahan Demand (%)", "Evaluasi Stok", "Rekomendasi"
                ]
            ].round(2),
            use_container_width=True,
            hide_index=True
        )

    st.subheader("Produk dengan Potensi Stok Berlebih")

    excess = filtered[
        filtered["Evaluasi Stok"] == "Evaluasi stok berlebih"
    ].sort_values("Stock Ratio", ascending=False).head(10).copy()

    if excess.empty:
        st.success("Tidak ada produk dalam kategori ini.")
    else:
        excess["Rekomendasi"] = excess.apply(recommendation, axis=1)
        st.dataframe(
            excess[
                [
                    "Store ID", "Product ID", "Category", "Region",
                    "Inventory Level", "Demand", "Stock Ratio",
                    "Perubahan Demand (%)", "Evaluasi Stok", "Rekomendasi"
                ]
            ].round(2),
            use_container_width=True,
            hide_index=True
        )

    # Tren permintaan
    st.subheader("Tren Permintaan")

    trend_data = (
        df[df["Date"] <= latest_date]
        .sort_values("Date")
        .tail(14)
    )

    trend_options = sorted(trend_data["Product ID"].unique())
    selected_product = st.selectbox(
        "Pilih produk untuk melihat tren Demand",
        trend_options
    )

    product_trend = (
        df[
            (df["Product ID"] == selected_product)
            & (df["Date"] <= latest_date)
        ]
        .groupby("Date", as_index=False)["Demand"]
        .mean()
        .sort_values("Date")
        .tail(30)
    )

    st.line_chart(
        product_trend.set_index("Date")["Demand"],
        x_label="Tanggal",
        y_label="Rata-rata Demand"
    )

    # Tabel lengkap dan ekspor
    st.subheader("Data Persediaan yang Dianalisis")

    search = st.text_input("Cari Store ID atau Product ID")

    display_data = filtered.copy()

    if search:
        mask = (
            display_data["Store ID"].astype(str).str.contains(
                search, case=False, na=False
            )
            | display_data["Product ID"].astype(str).str.contains(
                search, case=False, na=False
            )
        )
        display_data = display_data[mask]

    display_data["Rekomendasi"] = display_data.apply(
        recommendation, axis=1
    )

    st.dataframe(display_data, use_container_width=True, hide_index=True)

    st.download_button(
        "Download Hasil Analisis CSV",
        data=display_data.to_csv(index=False).encode("utf-8-sig"),
        file_name="hasil_analisis_inventory.csv",
        mime="text/csv"
    )

    st.caption(
        "Catatan: rasio Inventory Level / Demand dan batas kategorinya "
        "adalah indikator heuristik. Validasi arti dan periode Demand, "
        "lead time, serta kebijakan stok sebelum menggunakan hasil "
        "untuk keputusan pemesanan nyata."
    )

except Exception as e:
    st.error(f"Gagal memuat aplikasi: {e}")
    st.info(
        "Pastikan sales_data.xlsx tersedia di repository dan "
        "requirements.txt memuat streamlit, pandas, openpyxl, dan numpy."
    )
