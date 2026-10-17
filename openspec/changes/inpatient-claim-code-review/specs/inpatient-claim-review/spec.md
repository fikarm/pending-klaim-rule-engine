# Spec Delta

## Purpose

Menilai bukti terstruktur pada klaim rawat inap terhadap kriteria rule RSDS yang berlaku, dengan hasil yang dapat ditelusuri dan tidak menggantikan keputusan petugas.

## ADDED Requirements

### Requirement: Petugas dapat memasukkan bukti klaim secara terstruktur
Sistem SHALL menyediakan masukan terstruktur untuk diagnosis yang ditelaah, nilai pemeriksaan, terapi, dan rujukan bukti yang relevan dengan kriteria rule.

#### Scenario: Petugas memasukkan bukti hipokalemia
- **WHEN** petugas menelaah diagnosis E87.6 dan memasukkan hasil kalium, terapi injeksi KCl, serta rujukan dokumen pendukung
- **THEN** sistem menyimpan masukan tersebut sebagai bukti untuk kriteria rule E87.6

### Requirement: Sistem mengevaluasi kriteria rule yang berlaku
Sistem SHALL mengevaluasi bukti terhadap kriteria dan logika gabungan yang dinyatakan dalam versi rule aktif untuk diagnosis yang ditelaah.

#### Scenario: Seluruh kriteria E87.6 terpenuhi
- **WHEN** bukti menunjukkan kalium < 3,00 dan terapi injeksi KCl
- **THEN** kedua kriteria E87.6 ditandai terpenuhi

#### Scenario: Salah satu kriteria E87.6 tidak terpenuhi
- **WHEN** bukti yang tersedia menunjukkan kalium >= 3,00 atau tidak ada terapi injeksi KCl
- **THEN** sistem menandai kriteria terkait tidak terpenuhi dan tidak menyatakan seluruh kriteria E87.6 terpenuhi

#### Scenario: Bukti suatu kriteria belum tersedia
- **WHEN** petugas belum memasukkan bukti yang diperlukan untuk satu atau lebih kriteria
- **THEN** sistem menandai kriteria tersebut sebagai bukti belum ditemukan, bukan sebagai tidak terpenuhi

### Requirement: Hasil telaah dapat ditelusuri
Sistem SHALL menampilkan status setiap kriteria beserta bukti yang digunakan dan versi rule yang menjadi dasar evaluasi.

#### Scenario: Petugas meninjau hasil evaluasi
- **WHEN** sistem menampilkan hasil telaah klaim
- **THEN** petugas dapat melihat status per kriteria, rujukan bukti, dan versi rule yang dievaluasi

### Requirement: Pemeriksaan posisi diagnosis mengikuti rule
Sistem SHALL memeriksa posisi diagnosis hanya apabila versi rule yang dievaluasi secara eksplisit menetapkan kriteria posisi diagnosis.

#### Scenario: Rule tidak menetapkan posisi diagnosis
- **WHEN** sistem mengevaluasi rule E87.6 yang tidak memuat kriteria posisi diagnosis
- **THEN** sistem tidak menilai posisi diagnosis sebagai bagian dari hasil rule tersebut

#### Scenario: Rule menetapkan posisi diagnosis
- **WHEN** sistem mengevaluasi rule aktif yang secara eksplisit menyatakan posisi diagnosis yang disyaratkan
- **THEN** sistem membandingkan posisi diagnosis yang dimasukkan dengan kriteria posisi tersebut dan menampilkan hasilnya

### Requirement: Hasil telaah tidak menjadi keputusan klaim otomatis
Sistem SHALL menyajikan hasil sebagai dukungan telaah koding dan SHALL NOT menetapkan penerimaan atau penolakan klaim.

#### Scenario: Bukti tidak memenuhi kriteria
- **WHEN** satu atau lebih kriteria rule tidak terpenuhi atau buktinya belum ditemukan
- **THEN** sistem melaporkan temuan tersebut untuk ditinjau petugas tanpa memutuskan klaim diterima atau ditolak