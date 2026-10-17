# Proposal

## Why

Petugas membutuhkan cara yang konsisten dan dapat ditelusuri untuk menilai apakah bukti dalam klaim rawat inap mendukung koding diagnosis menurut interpretasi rule RSDS. Karena interpretasi tersebut dapat berubah dan tidak selalu menentukan posisi diagnosis, aplikasi harus memeriksa hanya kriteria yang dinyatakan oleh versi rule yang berlaku.

## What Changes

- Menambahkan telaah klaim rawat inap melalui formulir terstruktur dengan data sintetis untuk pengembangan dan PostgreSQL sebagai sumber data aplikasi.
- Memulai pilot dengan rule hipokalemia E87.6: kalium < 3,00 dan terapi injeksi KCl; kedua kriteria harus didukung bukti.
- Menampilkan status per kriteria sebagai terpenuhi, tidak terpenuhi, atau bukti belum ditemukan, beserta rujukan bukti dan rule.
- Memeriksa posisi diagnosis hanya jika rule yang berlaku secara eksplisit memuat kriteria posisi; E87.6 tidak menilai posisi diagnosis.
- Menambahkan pengelolaan rule RSDS dengan alur draf, peninjauan, dan aktivasi, serta mempertahankan versi dan provenance sumber untuk penelusuran.
- Membatasi hasil pada dukungan bukti untuk koding; aplikasi tidak menetapkan penerimaan klaim atau menggantikan penilaian petugas.

## Capabilities

### New Capabilities
- `inpatient-claim-review`: Telaah terstruktur atas bukti klaim rawat inap terhadap kriteria rule yang berlaku.
- `coding-rule-management`: Pengelolaan rule RSDS, siklus persetujuan, versi, dan rujukan sumber.

### Modified Capabilities

None.

## Impact

- Kapabilitas aplikasi telaah klaim rawat inap dan administrasi rule.
- Penyimpanan data aplikasi berbasis PostgreSQL; data sintetis digunakan untuk pengembangan awal.
- Rujukan dokumen harus membedakan Berita Acara Kemenkes sebagai sumber asal dengan interpretasi RSDS sebagai rule operasional, serta mencatat sumber dan halaman yang mendasari setiap rule.
- Belum ada implementasi kode, API, atau migrasi database dalam change perencanaan ini.