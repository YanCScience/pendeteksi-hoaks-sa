# Hoax Detection Benchmark

Program ini dibuat dari isi laporan `Perbandingan Algoritma KMP dan Rabin-Karp untuk Deteksi Konten Hoaks Berdasarkan Pola Kata Kunci pada Platform Media Sosial`.

Yang dilakukan program:

- membaca 4 file dataset `.xlsx` langsung tanpa library tambahan
- bisa menyatukan semuanya ke satu file `merged_hoax_dataset.csv`
- menggabungkan data `CNN`, `Kompas`, `Tempo` sebagai `non-hoax`
- menggabungkan `TurnBackHoax` sebagai `hoax`
- membentuk keyword kandidat otomatis dari data hoaks
- mengimplementasikan `KMP` dan `Rabin-Karp`
- menjalankan benchmark skenario `A`, `B`, `C`
- menghitung `execution time`, `peak memory`, `precision`, `recall`, dan `F1`

## 🚀 Web App Interface

Untuk pengujian interaktif dengan interface visual yang menarik:

1. Pastikan Python virtual environment aktif
2. Install dependencies: `pip install streamlit`
3. Jalankan: `python -m streamlit run hoax_web_app.py`
4. Buka browser ke `http://localhost:8501`

## Menjalankan di Windows PowerShell

Kalau `.\.venv\Scripts\Activate.ps1` gagal karena `running scripts is disabled on this system`, tidak perlu memaksa aktivasi virtual environment. Langsung pakai interpreter virtual environment:

```powershell
.\.venv\Scripts\python.exe -m streamlit run hoax_web_app.py
```

Untuk program terminal, file `hoax_program.py` wajib memakai subcommand. Jadi `python hoax_program.py` saja akan error karena argumen `merge`, `benchmark`, atau `classify` harus dipilih.

Contoh yang benar:

```powershell
.\.venv\Scripts\python.exe hoax_program.py benchmark --repeats 1
.\.venv\Scripts\python.exe hoax_program.py classify --algorithm kmp --keyword-count 100 --text "Viral kabar hakim mengalami kecelakaan setelah vonis."
```

Catatan:

- Jangan jalankan web app dengan `python hoax_web_app.py` karena file itu adalah aplikasi Streamlit.
- Jika launcher `streamlit.exe` di virtual environment tidak jalan, pakai `python -m streamlit` seperti contoh di atas.

Fitur web app:
- Input teks berita secara real-time
- Pilih algoritma (KMP/Rabin-Karp)
- Atur jumlah keyword
- Tampilan hasil yang menarik dengan warna dan ikon
- Statistik deteksi dengan progress bar
- Daftar keyword yang terdeteksi

## File yang dipakai

- `dataset_cnn_10k_cleaned.xlsx`
- `dataset_kompas_4k_cleaned.xlsx`
- `dataset_tempo_6k_cleaned.xlsx`
- `dataset_turnbackhoax_10_cleaned.xlsx`

## Cara menyatukan dataset

```powershell
python hoax_program.py merge
```

Perintah ini akan membuat file:

- `merged_hoax_dataset.csv`

Kolom hasil gabungan:

- `id`
- `source`
- `label`
- `title`
- `timestamp`
- `tags`
- `author`
- `url`
- `text`
- `text_column`

Setelah file gabungan ini ada, command `benchmark` dan `classify` akan otomatis memakainya.

## Cara menjalankan benchmark

```powershell
python hoax_program.py benchmark
```

Secara default benchmark memakai potongan teks maksimal `120` karakter per dokumen supaya lebih mendekati konten media sosial dan runtime tetap masuk akal.

Kalau ingin pakai full text:

```powershell
python hoax_program.py --max-text-length 0 benchmark
```

Kalau ingin lebih cepat saat uji coba awal:

```powershell
python hoax_program.py benchmark --repeats 1
```

Hasil benchmark akan:

- tampil di terminal
- disimpan ke file `benchmark_results.json`

## Cara klasifikasi satu teks

Contoh:

```powershell
python hoax_program.py classify --algorithm kmp --keyword-count 100 --text "Viral kabar hakim mengalami kecelakaan setelah vonis."
```

Atau pakai `rabin-karp`:

```powershell
python hoax_program.py classify --algorithm rabin-karp --keyword-count 100 --text "Viral kabar hakim mengalami kecelakaan setelah vonis."
```

## Catatan asumsi

- Struktur kolom asli tidak 100% sama, jadi program menormalkan semuanya ke format CSV gabungan yang konsisten.
- Keyword tidak tersedia sebagai file terpisah, jadi program menurunkannya otomatis dari dokumen hoaks pada data training.
- `TurnBackHoax` diprioritaskan memakai kolom `Clean Narasi`, lalu fallback ke `Narasi`, lalu `Title`.
- Threshold klasifikasi dipilih otomatis dari data validasi.
- Pencocokan dilakukan secara `case-insensitive`, sesuai laporan.
- Jika argumen global seperti `--max-text-length` dipakai, letakkan sebelum subcommand, misalnya `python hoax_program.py --max-text-length 0 benchmark`.
