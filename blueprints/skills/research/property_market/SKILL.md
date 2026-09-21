# Riset Pasar Properti

## 1. Tujuan dan ruang lingkup

Gunakan Skill ini untuk menganalisis lokasi, asset class, segment, competitor, demand, supply,
transaction, pricing, regulation, infrastructure, dan social trend yang relevan terhadap properti.
Hasilnya adalah market findings dan rekomendasi due diligence draft, bukan appraisal final atau
keputusan investasi, transaksi, legal, maupun regulasi.

Skill ini menggunakan prosedur **Riset Berbasis Bukti** dan domain `PROPERTY_MARKET`.

## 2. Input minimum

Pastikan tersedia:

- pertanyaan dan keputusan yang akan didukung;
- negara, provinsi, kota, kecamatan, micro-location, atau catchment area;
- asset class, product type, grade, tenure, dan customer segment;
- periode historis serta horizon analisis;
- unit pengukuran dan mata uang;
- comparable selection rule;
- risk, freshness, dan confidence requirement;
- regulatory topic serta tanggal relevan;
- internal project evidence yang diizinkan.

Jangan menggunakan istilah “pasar” tanpa menentukan geography, segment, product, dan period.

## 3. Prosedur domain

### 3.1 Definisikan market frame

Nyatakan:

- geographic boundary dan alasan pemilihannya;
- primary dan secondary catchment;
- asset class, product specification, serta customer segment;
- periode observasi;
- metric yang digunakan;
- inclusion/exclusion comparable.

Perubahan boundary dapat mengubah kesimpulan. Jangan memperluas atau mempersempit geography setelah
melihat hasil tanpa menjelaskan alasannya.

### 3.2 Bangun source map

Kelompokkan sumber menjadi:

1. regulator, peraturan, statistik resmi, dan public record;
2. verified transaction, deed/contract evidence, appraisal, atau approved internal actual;
3. developer/project disclosure dan competitor evidence;
4. listing portal atau broker evidence;
5. research report, survey, mobility, demographic, dan economic indicator;
6. interview, observation, social signal, atau anecdotal evidence.

Semakin rendah posisi sumber, semakin besar kebutuhan triangulasi dan limitation.

### 3.3 Normalisasi evidence

Untuk setiap observasi, catat:

| Dimensi | Isi minimum |
|---|---|
| Lokasi | Wilayah dan micro-location |
| Produk | Asset class, tipe, ukuran, grade, tenure, furnishing, dan kondisi |
| Harga | Asking/contracted/realized/appraised, gross/net, currency, tax, dan unit |
| Waktu | Tanggal observasi, periode transaksi, dan publication date |
| Metode | Sample, collection method, calculation, serta inclusion/exclusion |
| Insentif | Discount, cashback, furnishing, payment term, atau bundle |
| Sumber | Evidence reference, provenance, reliability, dan conflict of interest |

Jangan membandingkan harga per unit dengan harga per meter persegi, freehold dengan leasehold, atau
asking price dengan realized transaction tanpa normalisasi dan label.

### 3.4 Analisis demand dan supply

Sesuai kebutuhan, nilai:

- inventory, new launch, completion, pipeline, dan withdrawal;
- transaction atau booking volume;
- absorption dan time-on-market;
- vacancy/occupancy;
- buyer/renter profile dan affordability;
- financing availability dan interest sensitivity;
- infrastructure, accessibility, employment, amenity, dan migration driver;
- seasonality serta one-off event.

Jelaskan apakah metric merupakan observasi langsung, estimasi, proxy, atau inferensi.

### 3.5 Analisis competitor dan comparable

Pilih comparable berdasarkan location, product, segment, specification, timing, dan commercial terms.
Untuk setiap comparable, jelaskan alasan inclusion serta adjustment. Jangan cherry-pick comparable
yang hanya mendukung arah kesimpulan.

### 3.6 Analisis regulasi

Untuk setiap klaim regulasi:

- gunakan sumber resmi terkini;
- catat jurisdiction, nomor atau identitas aturan, tanggal berlaku, dan status perubahan;
- bedakan bunyi aturan, interpretasi, dan dampak bisnis yang diinferensikan;
- tandai kebutuhan legal opinion;
- jangan menyatakan kepatuhan atau kesimpulan hukum final.

### 3.7 Nilai freshness dan reliability

Freshness harus disesuaikan dengan volatility. Listing, pricing, dan regulation mungkin memerlukan
data sangat terkini; demographic trend dapat memakai horizon lebih panjang. Jelaskan cut-off date.

Reliability dipengaruhi oleh verification, sample, metode, representativeness, source incentive,
dan konsistensi dengan sumber lain. Banyak listing dari sumber yang sama tidak selalu berarti banyak
evidence independen.

### 3.8 Bentuk temuan dan rekomendasi

Temuan harus menyebut geography, product, segment, period, metric, direction, confidence, evidence,
dan limitation. Rekomendasi hanya boleh berupa due diligence berikutnya, validation plan, scenario
untuk dipertimbangkan, atau strategi draft untuk human review.

## 4. Penanganan konflik

- Periksa perbedaan geography, segment, product spec, unit, period, sample, dan incentive.
- Utamakan verified actual dan sumber resmi dibanding asking price atau marketing claim.
- Jika official data lebih lambat tetapi andal, tampilkan bersama current leading indicator dan
  jelaskan perbedaan perannya.
- Jika sumber memiliki conflict of interest, jangan membuangnya otomatis; turunkan reliability dan
  triangulasi.
- Jika conflict dapat mengubah keputusan material, turunkan confidence dan minta due diligence.

## 5. Format keluaran domain

1. Market frame, geography, asset class, segment, dan period.
2. Source map, cut-off date, serta metode normalisasi.
3. Demand, supply, pricing, transaction, dan competitor findings.
4. Regulatory findings dengan sumber resmi dan legal limitation.
5. Comparable table dan adjustment.
6. Conflict, freshness, reliability, bias, dan data gap.
7. Scenario atau recommendation draft serta due-diligence plan.

## 6. Larangan tindakan otomatis

Jangan menjalankan acquisition, sale, investment, booking, pricing change, negotiation, appraisal
final, legal opinion, regulatory filing, permit, atau commitment apa pun. Jangan menyajikan hasil
sebagai jaminan nilai atau performa masa depan.

## 7. Checklist evaluasi

- [ ] Geography, asset class, segment, product, dan period jelas.
- [ ] Asking, contracted, realized, appraised, dan inferred value dibedakan.
- [ ] Unit, currency, tax, incentive, dan timing dinormalisasi.
- [ ] Comparable dipilih dengan aturan konsisten dan adjustment dijelaskan.
- [ ] Cut-off date, freshness, reliability, sample, dan bias dinyatakan.
- [ ] Klaim regulasi memakai sumber resmi dan tidak menjadi legal opinion.
- [ ] Setiap market claim material memiliki evidence reference.
- [ ] Rekomendasi hanya berupa draft atau due diligence, bukan keputusan transaksi.
