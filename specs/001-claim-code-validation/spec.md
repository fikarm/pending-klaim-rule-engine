# Feature Specification: Claim Diagnosis Code Validation

**Feature Branch**: `001-claim-code-validation`

**Created**: 2026-10-17

**Status**: Draft

**Input**: User description: "Buatkan aplikasi untuk cek kesesuaian kode diagnosa primer dan sekunder untuk klaim asuransi. Tim RSDS sudah menyusun rule validasi berdasarkan Berita Acara Kesepakatan Pending Klaim Tahun 2019 yang dikeluarkan oleh Kementerian Kesehatan Republik Indonesia."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Periksa kode diagnosis klaim (Priority: P1)

Petugas koding rumah sakit memasukkan jenis layanan rawat inap atau rawat jalan, daftar diagnosis beserta urutannya, dan fakta pendukung yang tersedia. Aplikasi memeriksa setiap diagnosis terhadap aturan yang sesuai dengan jenis layanan dan posisi diagnosis, lalu menunjukkan hasil per kode.

**Why this priority**: Pemeriksaan kesesuaian diagnosis primer dan sekunder adalah tujuan utama aplikasi dan dapat memberi manfaat tanpa alur tambahan.

**Independent Test**: Masukkan klaim contoh dengan kode diagnosis dan bukti yang sesuai dengan aturan terverifikasi; pastikan aplikasi menghasilkan hasil untuk setiap diagnosis tanpa mengubah data klaim.

**Acceptance Scenarios**:

1. **Given** klaim rawat inap dengan diagnosis primer dan sekunder yang memiliki aturan aktif, **When** petugas menjalankan pemeriksaan, **Then** aplikasi menampilkan status dan alasan terpisah untuk setiap diagnosis.
2. **Given** aturan hanya berlaku pada posisi diagnosis tertentu, **When** kode yang sama dimasukkan pada posisi lain, **Then** aplikasi menerapkan batasan posisi tersebut dan menjelaskan ketidaksesuaian tanpa mengubah urutan atau kode.
3. **Given** diagnosis tidak memiliki aturan yang cocok dengan jenis layanan, **When** pemeriksaan dijalankan, **Then** hasilnya ditandai Tidak Berlaku dan tidak dinyatakan sesuai atau tidak sesuai.

---

### User Story 2 - Pahami bukti dan tindak lanjut (Priority: P2)

Petugas meninjau hasil untuk mengetahui kriteria mana yang terpenuhi, tidak terpenuhi, atau belum didukung dokumen, serta bukti dan sumber aturan yang digunakan. Petugas dapat mengenali data yang bertentangan dan menentukan bahwa pemeriksaan manual diperlukan.

**Why this priority**: Hasil yang dapat dijelaskan membantu petugas memperbaiki kelengkapan berkas dan menghindari keputusan yang tidak didukung bukti.

**Independent Test**: Jalankan pemeriksaan dengan bukti laboratorium yang hilang, dokumen wajib yang tidak tersedia, dan dua sumber data yang bertentangan; pastikan aplikasi menunjukkan alasan serta kebutuhan tinjauan untuk tiap kasus.

**Acceptance Scenarios**:

1. **Given** kriteria memerlukan hasil pemeriksaan atau tata laksana tertentu yang tidak ditemukan, **When** hasil ditampilkan, **Then** aplikasi mencantumkan data atau dokumen yang belum tersedia dan memberikan status Perlu Tinjauan.
2. **Given** dua sumber bukti memberikan nilai yang bertentangan, **When** aturan dievaluasi, **Then** aplikasi memperlihatkan kedua sumber dan nilai yang bertentangan serta tidak menyimpulkan hasil final.
3. **Given** aturan memiliki rujukan dokumen, tahun, dan halaman, **When** petugas membuka alasan hasil, **Then** rujukan tersebut ditampilkan bersama kriteria yang digunakan.

---

### User Story 3 - Periksa dasar dan status aturan (Priority: P3)

Petugas atau penanggung jawab aturan meninjau dasar suatu hasil, termasuk sumber aturan, status verifikasi, jenis layanan, kode yang dicakup, dan catatan perbedaan antar dokumen.

**Why this priority**: Aturan bersumber dari dokumen kesepakatan; keterlacakan mencegah aturan yang masih berupa draf atau diperselisihkan dianggap sebagai keputusan resmi.

**Independent Test**: Gunakan satu aturan terverifikasi dan satu aturan berstatus draf, tidak terverifikasi, atau memiliki perbedaan sumber; pastikan sumber dan status aturan terlihat dan hanya aturan terverifikasi yang dapat menghasilkan keputusan final.

**Acceptance Scenarios**:

1. **Given** aturan aktif yang telah diverifikasi terhadap sumbernya, **When** aturan digunakan, **Then** hasil menampilkan sumber, versi atau tanggal aturan, dan status verifikasinya.
2. **Given** aturan berstatus draf, belum diverifikasi, atau memiliki perbedaan dengan sumber rujukan, **When** aturan cocok dengan diagnosis, **Then** aplikasi menghasilkan Perlu Tinjauan dan menjelaskan bahwa aturan belum dapat menjadi keputusan final.

---

### Edge Cases

- Klaim tidak memiliki diagnosis primer, memiliki lebih dari satu diagnosis yang ditandai primer, atau mempunyai urutan diagnosis yang tidak lengkap.
- Kode tidak valid, tidak dikenali, atau hanya sebagian cocok dengan cakupan aturan.
- Jenis layanan tidak diketahui atau tidak sesuai dengan cakupan aturan rawat inap/rawat jalan.
- Nilai bukti tidak memiliki satuan, waktu pemeriksaan, atau sumber yang dapat ditelusuri.
- Bukti menunjukkan status tidak ada, tidak diketahui, atau bertentangan; keadaan tersebut tidak boleh disamakan dengan hasil negatif.
- Dokumen wajib, hasil laboratorium, pemeriksaan pencitraan, atau bukti tata laksana tidak tersedia.
- Ambang, satuan, atau syarat pada aturan RSDS berbeda dari Berita Acara Kesepakatan Pending Klaim Tahun 2019.
- Aturan untuk kasus tertentu belum tersedia, belum diverifikasi, atau belum menjelaskan apakah kode harus menjadi diagnosis primer atau sekunder.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Aplikasi MUST allow petugas membuat pemeriksaan klaim rawat inap atau rawat jalan dan memasukkan kode diagnosis, urutan, serta penanda diagnosis primer atau sekunder.
- **FR-002**: Aplikasi MUST evaluate each diagnosis only against rules whose code, jenis layanan, and posisi diagnosis match the claim.
- **FR-003**: Aplikasi MUST allow petugas mencatat atau meninjau fakta pendukung diagnosis, termasuk nilai, satuan, waktu, status ketersediaan, dokumen sumber, dan tata laksana yang relevan dengan aturan.
- **FR-004**: Aplikasi MUST show one result for each diagnosis using the meanings Sesuai (PASS), Tidak Sesuai (FAIL), Perlu Tinjauan (REVIEW), or Tidak Berlaku (NOT_APPLICABLE). PASS and FAIL MUST only be produced by applicable, verified rules with sufficient, non-conflicting evidence.
- **FR-005**: Aplikasi MUST explain each result by showing the matched rule, criteria evaluated, evidence that met or failed each criterion, missing information or documents, and a suggested next step for the verifier.
- **FR-006**: Aplikasi MUST show the source document, year, page or section when known, and verification status for every rule used in a result.
- **FR-007**: Aplikasi MUST return Perlu Tinjauan when required evidence is missing or conflicting, a rule is draft or unverified, or the RSDS rule differs from the cited agreement; it MUST identify the reason and MUST NOT silently choose which source prevails.
- **FR-008**: The initial supported diagnosis rules MUST cover the diagnosis cases defined in the RSDS rules and their cited sources for inpatient and outpatient claims, including cases such as pleural effusion, sepsis, pneumonia, acute/chronic respiratory failure, anemia, ascites, hypokalemia, cerebrovascular infarction, liver abscess, beta thalassemia, chemotherapy visits, follow-up visits, heart failure with hypertension, rehabilitation, and tuberculosis with pneumonia/pleural effusion. Rules not verified or reconciled MUST remain subject to FR-007.
- **FR-009**: Aplikasi MUST preserve the entered diagnosis codes and their order; it MUST NOT automatically add, remove, replace, or reorder diagnoses, determine a patient's diagnosis, or submit a claim.
- **FR-010**: Aplikasi MUST present results and explanations in Bahasa Indonesia and MUST avoid requiring direct patient identifiers for rule evaluation.

### Key Entities *(include if data involved)*

- **Pemeriksaan Klaim**: Satu konteks pemeriksaan yang mencakup jenis layanan, daftar diagnosis, dan bukti pendukung yang relevan.
- **Diagnosis Klaim**: Kode diagnosis, urutan, dan perannya sebagai diagnosis primer atau sekunder dalam satu klaim.
- **Aturan Validasi**: Kriteria yang menghubungkan kode dan cakupan layanan dengan bukti, dokumen, tata laksana, hasil, dan sumber rujukan.
- **Bukti Pendukung**: Fakta atau dokumen dari klaim yang memiliki nilai/status, satuan atau waktu bila relevan, serta asal yang dapat ditelusuri.
- **Hasil Pemeriksaan**: Status per diagnosis beserta alasan, kriteria, bukti, kekurangan, sumber aturan, dan tindak lanjut yang disarankan.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In an agreed acceptance set covering every supported rule and both service types, 100% of claim cases produce the expected per-diagnosis status and primary/secondary interpretation.
- **SC-002**: 100% of final PASS or FAIL results identify the applicable verified rule, its source, and the evidence supporting the outcome.
- **SC-003**: 100% of acceptance cases with missing/conflicting evidence or an unresolved rule-source difference produce Perlu Tinjauan rather than a final PASS or FAIL.
- **SC-004**: At least 90% of representative coding staff can complete a sample claim review and identify the required next step without assistance in a usability evaluation.

## Assumptions

- Pengguna utama adalah petugas koding atau verifikator klaim rumah sakit yang memahami proses klaim dan menilai hasil aplikasi.
- Ruang lingkup v1 adalah validasi kode diagnosis primer/sekunder rawat inap dan rawat jalan. Validasi kode prosedur operasi, endoskopi, MRI, eligibility, dan pengajuan klaim tidak termasuk.
- Pengguna memasukkan data klaim dan bukti secara manual. OCR, unggah/ekstraksi dokumen otomatis, dan integrasi dengan sistem rumah sakit atau penjamin tidak termasuk dalam ruang lingkup v1.
- Berita Acara Kesepakatan Pending Klaim Tahun 2019 dan aturan RSDS merupakan rujukan awal. Perbedaan antara keduanya harus ditetapkan oleh penanggung jawab aturan sebelum menjadi aturan terverifikasi; aplikasi tidak mengasumsikan salah satunya menang secara otomatis.
- Pemeriksaan tidak memerlukan nama atau nomor identitas pasien. Kebijakan akses dan retensi data untuk penerapan produksi ditetapkan oleh organisasi sebelum penggunaan dengan data klaim nyata.
- Sumber kebenaran untuk uji penerimaan adalah contoh klaim yang telah disetujui petugas koding/penanggung jawab aturan, termasuk kasus sesuai, tidak sesuai, tidak berlaku, data kurang, dan konflik sumber.
