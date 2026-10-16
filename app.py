import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="Retail Inventory Agent",
    page_icon="📦",
    layout="wide"
)

@st.cache_data
def load_data():
    data = pd.read_excel("sales_data.xlsx")

    data["Stock Ratio"] = (
        data["Inventory Level"]
        / data["Demand"].replace(0, float("nan"))
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
        else:
            return "Evaluasi stok berlebih"

    data["Evaluasi Stok"] = data["Stock Ratio"].apply(evaluate)
    return data


st.title("📦 Retail Inventory Agent")
st.caption("Dashboard analisis dan evaluasi persediaan")

try:
    df = load_data()

    st.sidebar.header("Filter Data")

    regions = st.sidebar.multiselect(
        "Pilih Region",
        sorted(df["Region"].dropna().unique()),
        default=sorted(df["Region"].dropna().unique())
    )

    categories = st.sidebar.multiselect(
        "Pilih Category",
        sorted(df["Category"].dropna().unique()),
        default=sorted(df["Category"].dropna().unique())
    )

    filtered = df[
        df["Region"].isin(regions)
        & df["Category"].isin(categories)
    ]

    c1, c2, c3, c4 = st.columns(4)

    c1.metric("Total Data", f"{len(filtered):,}")
    c2.metric(
        "Prioritas Tinggi",
        int((filtered["Evaluasi Stok"] == "Prioritas tinggi").sum())
    )
    c3.metric(
        "Stok Relatif Aman",
        int((filtered["Evaluasi Stok"] == "Stok relatif aman").sum())
    )
    c4.metric(
        "Evaluasi Stok Berlebih",
        int((filtered["Evaluasi Stok"] == "Evaluasi stok berlebih").sum())
    )

    st.subheader("Jumlah Data per Evaluasi Stok")
    counts = filtered["Evaluasi Stok"].value_counts()
    st.bar_chart(counts)

    st.subheader("Tabel Evaluasi Persediaan")

    search = st.text_input("Cari Store ID atau Product ID")

    if search:
        filtered = filtered[
            filtered["Store ID"].astype(str).str.contains(search, case=False)
            | filtered["Product ID"].astype(str).str.contains(search, case=False)
        ]

    st.dataframe(filtered, use_container_width=True)

    st.download_button(
        "Download Hasil Evaluasi (CSV)",
        data=filtered.to_csv(index=False).encode("utf-8-sig"),
        file_name="hasil_evaluasi_stok.csv",
        mime="text/csv"
    )

except Exception as e:
    st.error(f"Gagal memuat aplikasi: {e}")
    st.info(
        "Pastikan file sales_data.xlsx sudah di-upload "
        "ke repository GitHub yang sama."
    )
