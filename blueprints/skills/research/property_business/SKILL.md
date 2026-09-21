# Riset Model Bisnis Properti

## 1. Tujuan dan ruang lingkup

Gunakan Skill ini untuk mengevaluasi proposisi nilai, target customer, paket produk, pricing, channel,
revenue model, cost structure, margin, cash timing, dan unit economics bisnis properti. Hasilnya
adalah scenario analysis dan rekomendasi draft, bukan perubahan harga, kontrak, atau anggaran.

Skill ini menggunakan prosedur **Riset Berbasis Bukti** dan domain `PROPERTY_BUSINESS`.

## 2. Input minimum

Pastikan tersedia:

- proyek, lokasi, produk, unit type, customer segment, dan periode analisis;
- problem atau keputusan komersial yang akan didukung;
- paket serta harga saat ini dan alternatif yang dinilai;
- funnel: lead, qualified lead, visit, booking, akad, cancellation, dan collection;
- volume, revenue, discount, incentive, commission, direct cost, overhead, dan cash timing;
- constraint legal, finance, delivery, capacity, dan brand;
- target metric serta definisinya;
- sumber, tanggal, satuan, dan owner setiap asumsi material.

Jika definisi unit, periode, atau funnel berbeda antar-sumber dan tidak dapat dinormalisasi, jangan
melanjutkan ke kesimpulan numerik.

## 3. Prosedur domain

### 3.1 Tetapkan unit analisis

Nyatakan secara eksplisit apakah analisis dilakukan per unit, tipe unit, proyek, customer, channel,
bulan, tahun, atau keseluruhan portfolio. Gunakan satuan dan periode yang konsisten.

### 3.2 Petakan model bisnis

Dokumentasikan:

- customer dan kebutuhan yang dilayani;
- value proposition dan pembeda;
- paket, fitur, service, serta exclusions;
- acquisition dan sales channel;
- revenue stream dan payment schedule;
- cost driver dan operational dependency;
- partner, supplier, regulator, serta contractual constraint;
- risiko cancellation, collection, delivery, dan after-sales.

### 3.3 Bangun assumption register

Untuk setiap asumsi, catat:

| Field | Isi minimum |
|---|---|
| Asumsi | Pernyataan yang digunakan dalam model |
| Nilai dan unit | Angka, mata uang, persentase, atau durasi |
| Scope | Proyek, produk, segmen, channel, wilayah, dan periode |
| Sumber | Evidence reference dan tanggal |
| Jenis | Aktual, benchmark, forecast, management assumption, atau inferensi |
| Owner | Fungsi yang harus memvalidasi |
| Confidence | Tinggi, sedang, atau rendah beserta alasan |
| Sensitivity | Dampak jika asumsi berubah |

Jangan mencampur actual dengan forecast tanpa label.

### 3.4 Hitung unit economics secara transparan

Pilih metrik yang relevan, misalnya:

- average selling price dan net realized price;
- revenue per unit/customer/channel;
- direct cost dan contribution margin;
- acquisition cost dan conversion rate;
- cancellation/default rate;
- commission dan incentive burden;
- cash collection timing dan working-capital implication;
- break-even volume atau payback period.

Nyatakan formula. Pastikan angka hasil dapat direkonstruksi dari assumption register. Hindari metrik
yang tidak memiliki definisi operasional yang disepakati.

### 3.5 Bentuk scenario

Gunakan minimal:

- **Base** — asumsi paling didukung evidence saat ini;
- **Downside** — kombinasi downside yang masuk akal, bukan angka arbitrer;
- **Upside** — peluang yang masih realistis dan memiliki driver jelas.

Lakukan sensitivity pada variabel yang paling memengaruhi hasil, seperti price, volume, conversion,
discount, cancellation, construction/delivery cost, interest, atau collection timing. Jangan
menyembunyikan hasil negatif dengan averaging lintas scenario.

### 3.6 Bandingkan alternatif

Bandingkan paket atau pricing dengan dimensi konsisten:

| Dimensi | Pemeriksaan |
|---|---|
| Customer value | Kebutuhan, affordability, perceived value, dan differentiation |
| Demand | Segment size, conversion, elasticity, dan cannibalization |
| Economics | Revenue, margin, cash timing, downside exposure, dan break-even |
| Delivery | Capacity, operational complexity, supplier, dan service obligation |
| Risk | Legal, contract, reputation, collection, dan execution risk |
| Reversibility | Kemudahan pilot, monitoring, rollback, dan exit |

### 3.7 Bentuk rekomendasi draft

Rekomendasi dapat berupa pilot terbatas, validasi asumsi, perubahan scenario untuk dipertimbangkan,
atau penghentian analisis karena evidence tidak cukup. Sertakan metric pilot, guardrail, sample,
periode, owner, approval, dan exit criteria. Jangan mengaktifkan paket atau harga.

## 4. Strategi sumber dan evidence

Prioritaskan:

1. kontrak, price list, budget, actual sales, collection, cost, dan performance internal terotorisasi;
2. approved product/package definition dan project constraint;
3. transaksi atau comparable yang definisinya dapat disejajarkan;
4. market benchmark terkini dengan metode jelas;
5. survey atau interview dengan sample dan bias yang dijelaskan;
6. opini atau marketing material hanya sebagai evidence pendukung.

Setiap angka harus mencantumkan currency, tax treatment, gross/net status, unit, geography, period,
dan inclusion/exclusion yang relevan.

## 5. Penanganan konflik

- Normalisasi gross versus net, termasuk versus tidak termasuk pajak/fee, serta nominal versus persen.
- Bedakan asking price, contracted price, realized price, dan cash collected.
- Bedakan booking, akad, revenue recognition, dan collection.
- Jika Finance dan Sales menggunakan definisi berbeda, tampilkan kedua definisi dan minta owner
  menyepakati baseline.
- Jika benchmark tidak sebanding, gunakan sebagai konteks saja, bukan basis perhitungan utama.

## 6. Format keluaran domain

1. Scope, customer, produk, periode, dan keputusan yang didukung.
2. Current model dan alternatif.
3. Assumption register beserta evidence dan confidence.
4. Formula serta hasil unit economics.
5. Base, downside, upside, dan sensitivity.
6. Konflik data serta limitation.
7. Rekomendasi draft, validation plan, owner, dan reviewer.

## 7. Larangan tindakan otomatis

Jangan mengubah active pricing, discount, package, contract, budget, target, commission, sales policy,
atau commercial commitment. Jangan membuat atau mengeksekusi Production Backlog. Semua keputusan
komersial memerlukan review dan approval fungsi yang berwenang.

## 8. Checklist evaluasi

- [ ] Unit analisis, currency, periode, dan definisi funnel konsisten.
- [ ] Semua asumsi material memiliki sumber, owner, dan confidence.
- [ ] Actual, forecast, benchmark, dan inferensi dibedakan.
- [ ] Formula dapat direkonstruksi.
- [ ] Base, downside, upside, dan sensitivity memiliki driver yang jelas.
- [ ] Risiko legal, delivery, cash, collection, dan reputation dibahas.
- [ ] Rekomendasi tetap berupa draft dan tidak mengubah kondisi komersial aktif.
