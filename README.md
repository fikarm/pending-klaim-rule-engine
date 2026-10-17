# Pending Klaim Rule Engine

Prototype CLI untuk telaah bukti koding diagnosis klaim rawat inap. Hasilnya
adalah dukungan telaah petugas, bukan keputusan penerimaan atau penolakan klaim.

## Development

Gunakan Python 3.14 dan `uv`. Siapkan PostgreSQL lokal, lalu atur URL koneksi di
environment terminal (jangan simpan kredensial dalam source code):

```sh
export DATABASE_URL='postgresql+psycopg://USER:PASSWORD@localhost/DATABASE'
uv sync
uv run alembic upgrade head
uv run pending-klaim-rule-engine-seed
uv run pending-klaim-rule-engine
```

Seed membuat rule E87.6 sintetis untuk development berdasarkan contoh di
`docs/rule_rsds.pdf`. Seed ini bukan rule produksi yang telah disahkan dan tidak
boleh digunakan untuk telaah klaim nyata. Form CLI meminta kode diagnosis, nilai
kalium dan satuannya, status terapi injeksi KCl, serta rujukan bukti dokumen.
Posisi diagnosis hanya diminta jika rule aktif menyatakan kriteria posisi.

Jalankan pemeriksaan lokal dengan:

```sh
uv run pytest
```

Tes migrasi dan round-trip SQLite dijalankan otomatis. Tes PostgreSQL memakai
schema acak sementara pada database disposable yang ditentukan terpisah melalui
`POSTGRES_TEST_URL`; schema tersebut dihapus setelah tes.

```sh
export POSTGRES_TEST_URL='postgresql+psycopg://USER:PASSWORD@localhost/DISPOSABLE_DATABASE'
uv run pytest
```
