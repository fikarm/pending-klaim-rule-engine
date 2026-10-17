# Spec Delta

## Purpose

Mengelola interpretasi rule RSDS sebagai kriteria operasional yang dapat ditinjau, diaktifkan, dan ditelusuri versinya tanpa menyamakan interpretasi tersebut dengan dokumen sumber resmi.

## ADDED Requirements

### Requirement: Rule memiliki provenance sumber
Setiap rule SHALL menyimpan identitas sumber, versi atau tanggal sumber bila tersedia, dan rujukan halaman atau bagian yang mendasari kriteria operasional.

#### Scenario: Rule merujuk pada interpretasi RSDS
- **WHEN** rule RSDS dibuat dari dokumen interpretasi
- **THEN** rule mencatat dokumen RSDS sebagai sumber operasional dan rujukan dokumen sumber yang dinyatakan di dalamnya

### Requirement: Rule mengikuti alur status
Rule SHALL mengikuti status draf, ditinjau, dan aktif sebelum digunakan untuk evaluasi klaim.

#### Scenario: Rule masih berupa draf
- **WHEN** rule berada pada status draf atau ditinjau
- **THEN** sistem tidak menggunakan rule tersebut untuk evaluasi klaim

#### Scenario: Rule diaktifkan setelah ditinjau
- **WHEN** rule telah ditinjau dan diaktifkan oleh petugas berwenang
- **THEN** sistem dapat menggunakan rule tersebut pada evaluasi baru

### Requirement: Perubahan rule mempertahankan versi sebelumnya
Perubahan rule aktif SHALL menghasilkan versi baru dan SHALL mempertahankan versi sebelumnya untuk penelusuran hasil evaluasi terdahulu.

#### Scenario: Rule aktif direvisi
- **WHEN** petugas mengubah kriteria pada rule aktif dan versi perubahan diaktifkan
- **THEN** sistem mempertahankan versi lama dan menggunakan versi baru untuk evaluasi setelah aktivasi

#### Scenario: Hasil lama ditinjau setelah revisi
- **WHEN** petugas membuka evaluasi yang dibuat sebelum versi baru diaktifkan
- **THEN** sistem menampilkan versi rule yang digunakan pada evaluasi tersebut, bukan menggantinya dengan versi terbaru