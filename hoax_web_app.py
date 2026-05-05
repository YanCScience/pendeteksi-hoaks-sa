import streamlit as st
import sys
import os
from pathlib import Path

sys.path.append(os.path.dirname(__file__))

from hoax_program import (
    prepare_experiment_assets,
    tune_threshold,
    HoaxDetector,
    normalize_for_matching,
    SEARCH_FUNCTIONS
)

st.set_page_config(
    page_title="Hoax Detector",
    page_icon="🕵️‍♂️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        color: #FF6B6B;
        text-align: center;
        margin-bottom: 2rem;
        font-weight: bold;
    }
    .result-box {
        padding: 2rem;
        border-radius: 10px;
        margin: 1rem 0;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .hoax-result {
        background-color: #FFE5E5;
        border-left: 5px solid #FF6B6B;
    }
    .safe-result {
        background-color: #E5FFE5;
        border-left: 5px solid #4CAF50;
    }
    .metric-card {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 8px;
        text-align: center;
        margin: 0.5rem;
    }
    .stTextArea textarea {
        font-size: 16px;
    }
</style>
""", unsafe_allow_html=True)

def main():
    st.markdown("""
    <style>
        .centered-title {
            display: block;
            text-align: center !important;
            font-size: 3.5rem;
            background: linear-gradient(45deg, #FF6B6B, #4ECDC4);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
            margin-bottom: 1rem;
            font-weight: bold;
            text-shadow: none;
        }
    </style>
    <div class="centered-title">🕵️‍♂️ Hoax Detector</div>
    """, unsafe_allow_html=True)
    st.markdown("### Deteksi Berita Hoax dengan Algoritma String Matching")
    st.markdown("---")

    st.sidebar.title("⚙️ Pengaturan")
    
    dataset_source = st.sidebar.radio(
        "Sumber Dataset",
        ["Merged CSV (Lebih Cepat)", "4 File Excel (Raw)"],
        index=0
    )
    force_excel = dataset_source == "4 File Excel (Raw)"

    compare_mode = st.sidebar.checkbox(
        "🔄 Mode Perbandingan (KMP vs Rabin-Karp)",
        value=False,
        help="Jalankan kedua algoritma dan bandingkan hasilnya"
    )
    
    if not compare_mode:
        algorithm = st.sidebar.selectbox(
            "Pilih Algoritma",
            list(SEARCH_FUNCTIONS),
            index=0,
            help="KMP: Knuth-Morris-Pratt, Rabin-Karp: Algoritma hashing"
        )
    else:
        algorithm = None 

    keyword_count = st.sidebar.slider(
        "Jumlah Keyword",
        min_value=10,
        max_value=200,
        value=50,
        step=10,
        help="Jumlah keyword teratas yang digunakan untuk deteksi"
    )

    st.subheader("📝 Masukkan Berita")
    text_input = st.text_area(
        "Teks berita yang ingin diperiksa:",
        height=250,
        placeholder="Ketik atau paste berita di sini...",
        help="Masukkan teks berita lengkap untuk analisis hoax",
        key="input_text"
    )

    col_btn_left, col_btn_right = st.columns([1, 3]) 
    with col_btn_right:
        if st.button("🔍 Analisis Hoax", type="primary", use_container_width=True):
            if not text_input.strip():
                st.error("⚠️ Silakan masukkan teks berita terlebih dahulu!")
                st.stop()

            with st.spinner("🔄 Menganalisis berita..."):
                try:
                    assets = prepare_experiment_assets(
                        data_dir=Path("data"),
                        merged_dataset_path=None,
                        seed=45,
                        train_ratio=0.7,
                        validation_ratio=0.15,
                        keyword_source_docs_per_class=1500,
                        keyword_pool_size=max(keyword_count, 100),
                        validation_docs_per_class=250,
                        max_text_length=120,
                        force_excel=force_excel,
                    )

                    keywords = assets["keywords"][:keyword_count]
                    validation_sample = assets["validation_sample"]
                    
                    if compare_mode:
                        display_comparison(text_input, keywords, validation_sample)
                    else:
                        threshold = tune_threshold(
                            validation_documents=validation_sample,
                            keywords=keywords,
                            algorithm_name=algorithm,
                        )

                        detector = HoaxDetector(
                            keywords=keywords,
                            algorithm_name=algorithm,
                            threshold=threshold
                        )

                        result = detector.detect(text_input)

                        display_results(result, keywords)

                except Exception as e:
                    st.error(f"❌ Terjadi kesalahan: {str(e)}")
                    st.info(
                        "Pastikan folder `data` berisi `merged_hoax_dataset.csv` atau empat file dataset `.xlsx` bawaan project."
                    )

    st.markdown("---")

    st.subheader("📊 Statistik")
    col_stat1, col_stat2 = st.columns(2)

    with col_stat1:
        st.markdown("### Cara Kerja")
        st.markdown("""
        1. **Preprocessing**: Teks dinormalisasi  
        2. **Keyword Matching**: Pencarian keyword menggunakan algoritma terpilih  
        3. **Scoring**: Hitung skor berdasarkan jumlah match  
        4. **Klasifikasi**: Bandingkan dengan threshold  
        """)

    with col_stat2:
        st.markdown("### Algoritma")
        algo_info = {
            "kmp": "Knuth-Morris-Pratt: Efisien untuk pola berulang",
            "rabin-karp": "Rabin-Karp: Menggunakan hashing untuk kecepatan"
        }
        st.info(algo_info.get(algorithm, "Mode Perbandingan: Kedua algoritma dijalankan"))


def display_comparison(text_input, keywords, validation_sample):
    """Display side-by-side comparison of KMP and Rabin-Karp algorithms"""
    import time
    
    st.subheader("⚖️ Perbandingan Algoritma")
    
    results = {}
    timings = {}
    
    # Test both algorithms
    for algo_name in SEARCH_FUNCTIONS:
        col_placeholder = st.empty()
        with col_placeholder.container():
            st.info(f"🔄 Memproses algoritma {algo_name.upper()}...")
        
        # Tune threshold
        threshold = tune_threshold(
            validation_documents=validation_sample,
            keywords=keywords,
            algorithm_name=algo_name,
        )
        
        detector = HoaxDetector(
            keywords=keywords,
            algorithm_name=algo_name,
            threshold=threshold
        )
        
        start_time = time.perf_counter()
        result = detector.detect(text_input)
        end_time = time.perf_counter()
        
        results[algo_name] = result
        timings[algo_name] = (end_time - start_time) * 1000  
        col_placeholder.empty()
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 🔵 KMP (Knuth-Morris-Pratt)")
        kmp_result = results['kmp']
        display_single_result(kmp_result, keywords, timings['kmp'], 'kmp')
    
    with col2:
        st.markdown("### 🔴 Rabin-Karp")
        rk_result = results['rabin-karp']
        display_single_result(rk_result, keywords, timings['rabin-karp'], 'rabin-karp')
    
    st.markdown("---")
    st.subheader("📊 Analisis Perbandingan")
    
    kmp_time = timings['kmp']
    rk_time = timings['rabin-karp']
    time_diff = abs(kmp_time - rk_time)
    faster = "KMP" if kmp_time < rk_time else "Rabin-Karp" if rk_time < kmp_time else "Sama"
    
    comp_col1, comp_col2 = st.columns(2)
    with comp_col1:
        st.metric("KMP", f"{kmp_time:.2f} ms")
        st.metric("Rabin-Karp", f"{rk_time:.2f} ms")
    with comp_col2:
        st.metric("Lebih Cepat", faster)
        st.metric("Selisih", f"{time_diff:.2f} ms")
    
    kmp_label = results['kmp']['label']
    rk_label = results['rabin-karp']['label']
    kmp_score = results['kmp']['score']
    rk_score = results['rabin-karp']['score']
    
    st.markdown("### Hasil Klasifikasi")
    comp_col1, comp_col2 = st.columns(2)
    
    with comp_col1:
        kmp_icon = "✅" if kmp_label == "BUKAN_HOAKS" else "🚨"
        st.success(f"{kmp_icon} **KMP**: {kmp_label.replace('_', ' ')}")
        st.caption(f"Score: {kmp_score:.2f}")
    with comp_col2:
        rk_icon = "✅" if rk_label == "BUKAN_HOAKS" else "🚨"
        st.success(f"{rk_icon} **Rabin-Karp**: {rk_label.replace('_', ' ')}")
        st.caption(f"Score: {rk_score:.2f}")

    
    if kmp_label == rk_label:
        st.success("✅ Kedua algoritma menghasilkan kesimpulan yang SAMA")
    else:
        st.warning("⚠️ Kedua algoritma menghasilkan kesimpulan yang BERBEDA")

def display_single_result(result, keywords, exec_time, algo_name):
    """Display result for a single algorithm"""
    label = result['label']
    score = result['score']
    total_matches = result['total_matches']
    threshold = result['threshold']
    matches = result['matches']
    
    result_class = "hoax-result" if label == "HOAKS" else "safe-result"
    icon = "🚨" if label == "HOAKS" else "✅"
    
    st.markdown(f"""
    <div class="result-box {result_class}">
        <h3 style="margin-top: 0; color: {'#FF6B6B' if label == 'HOAKS' else '#4CAF50'};">
            {icon} {label.replace('_', ' ')}
        </h3>
    </div>
    """, unsafe_allow_html=True)
    
    m_col1, m_col2 = st.columns(2)
    with m_col1:
        st.metric("Skor", f"{score:.2f}")
        st.metric("Waktu", f"{exec_time:.2f} ms")
    with m_col2:
        st.metric("Total Match", total_matches)
        st.metric("Threshold", threshold)

    if matches:
        st.caption("Top 5 Keyword Terdeteksi:")
        top_matches = dict(sorted(matches.items(), key=lambda x: (-len(x[1]), x[0]))[:5])
        for keyword, positions in top_matches.items():
            st.text(f"• {keyword}: {len(positions)} match")
    else:
        st.caption("❌ Tidak ada keyword terdeteksi")

def display_results(result, keywords):
    label = result['label']
    score = result['score']
    total_matches = result['total_matches']
    threshold = result['threshold']
    matches = result['matches']

    result_class = "hoax-result" if label == "HOAKS" else "safe-result"
    icon = "🚨" if label == "HOAKS" else "✅"

    st.markdown(f"""
    <div class="result-box {result_class}">
        <h2 style="margin-top: 0;">{icon} Hasil Analisis</h2>
        <h3 style="color: {'#FF6B6B' if label == 'HOAKS' else '#4CAF50'};">
            {label.replace('_', ' ')}
        </h3>
    </div>
    """, unsafe_allow_html=True)

    col_m1, col_m2 = st.columns(2)
    with col_m1:
        st.metric("Skor", f"{score:.2f}")
        st.metric("Total Match", total_matches)
    with col_m2:
        st.metric("Threshold", threshold)
        st.metric("Keyword Digunakan", len(keywords))

    if matches:
        st.subheader("🔍 Keyword yang Ditemukan")
        match_data = []
        for keyword, positions in sorted(matches.items(), key=lambda x: (-len(x[1]), x[0])):
            match_data.append({
                "Keyword": keyword,
                "Jumlah": len(positions),
                "Posisi": ", ".join(str(p) for p in positions[:5]) + ("..." if len(positions) > 5 else "")
            })

        st.dataframe(match_data, use_container_width=True)
    else:
        st.info("✅ Tidak ada keyword hoax yang ditemukan dalam teks.")

    confidence = min(score * 100, 100)
    st.progress(confidence / 100)
    st.caption(f"Tingkat Kepercayaan: {confidence:.1f}%")

if __name__ == "__main__":
    main()
