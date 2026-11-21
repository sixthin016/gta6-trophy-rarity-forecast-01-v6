# gta6-trophy-rarity-forecast-01 — v6 build notes

- Kompetisi: forecast 55 trophy GTA VI (Exophase) di 2026-11-26 00:00 UTC,
  5 kuantil/trophy, skor pinball loss skala logit. Hadiah $250, top 20
  (1st $50, 2nd $35, 3rd $25, 4-10 $10, 11-20 $7). Deadline entri
  21 Nov 2026 11:30 UTC = 19:30 WITA. Kuota dicek 21 Nov ~13:20 WITA:
  can_submit=true, day cap 6, taken 1, left 5, hard limit left 36/40,
  entries_made 4 (v1, v2, v3r, v5 — v4 tidak pernah disubmit).

## Diagnosis: kenapa v5 jatuh (dan koreksi soal v3r)

- Board saat ini adalah fase PRACTICE (dev, skor live): dua kasus dengan
  histori flat sempurna (638 pemain) dan jawaban = satu refresh di
  target (3.868 pemain, 4.276 earners, semua rate kecuali 100% turun —
  semua terbit di competition.yaml). Refresh itu mendilusi rate ke
  ~0,20-0,25x: pendatang baru hampir tidak memegang apa pun kecuali
  trofi pertama (100%), jadi 54 trofi lain berbagi hanya ~103 earners
  baru. Ini dipaksa agregat terbit, bukan asumsi.
- Bukti tiga arah (semua diukur, bukan klaim):
  * persistence (house baseline) skor produksi ~1,51; v5 skor 1,85;
    v2 skor 0,139 (rank 515). Pada truth faktor-seragam, ketiga angka
    itu hanya konsisten bersama pada faktor ~0,20.
  * v3r median = dilusi seragam 0,60x (mult 5, phi 0,5) → skor proxy
    0,6998. Jadi v3r BUKAN rank 350 / loss 0,114 — angka "350" itu artefak
    basi rank-check (state keyed by slug, carry-over rank lama saat
    submission tidak ditemukan di leaderboard, yang hanya menampilkan
    satu entri terbaru per akun). v3r adalah REGRESI dari v2 (0,139),
    bukan perbaikan. Proxy v3r sendiri (skenario A-D, mult 5, phi
    0,5-0,7) tidak konsisten-agregat: tidak pernah memaksakan total
    4.276 earners, jadi median 0,6x tampak benar di proxy itu.
  * v1/v2 median faktor 0,216-0,320 (hazard-age) — cocok dengan faktor
    nyata ~0,20-0,25. v4 (tidak disubmit) proxy 0,1135.
- v5 jatuh karena tiga hal: (1) tidak ada prior dilusi — median di
  histori flat diam di rate terakhir atau NAIK (1,0-2,5x via saturating
  trend + shrinkage ke tier pool); (2) fan normal simetris sd 0,40,
  bukan count fan; (3) backtest "final-like"-nya (0,58 vs v3r 1,52)
  memakai dunia yang refresh-nya memberi pendatang baru 70% rate
  incumbent — rezim yang tidak ada di jawaban practice. Jadi v5
  dioptimasi untuk dunia yang tidak dinilai board.

## Desain v6 (ditulis fresh di sesi ini)

1. Jalur FLAT (histori flat): satu refresh di target. Median di ruang
   earners/players: hazard-age (hazard dari rate + umur trofi, pendatang
   baru umur efektif 0,2 jam), pemain x6,064 (terbit), fan count
   (Poisson + overdispersi lognormal + pengali refresh lognormal,
   3000 draw, seed per trofi). Knob dituning di proxy+factor:
   NEW_AGE=0,20, GROWTH=0,15 (tidak teridentifikasi di horizon 1,5 jam),
   S_MULT=0,15, S_ALPHA=0,30.
2. Jalur MOVING: ensemble saturating-curve (logit rate vs log-time) +
   garis logit-linear + tren log(earners) + ekstrapolasi refresh
   (delta per-refresh teramati x jumlah refresh), semua fit HANYA di
   jendela 24 jam terakhir (crash dilusi launch-night tidak boleh
   menjangkar fit yang dibaca 108 jam ke depan); bobot dari
   rolling-origin backtest di histori kasus sendiri; pangsa keluarga
   kurva dibatasi 1/(1+hari horizon) (prudence horizon — backtest hanya
   memvalidasi 6-24 jam). Trofi nyaris-nol earners meminjam kurva pool
   tier. Fan conformal dari error backtest terstandarisasi.
3. Dua perbaikan berurutan yang terukur di dunia final-like (d):
   jendela-24-jam memperbaiki synth-final 0,6110 -> 0,5265 dan
   cv-cut48 0,2647 -> 0,0519; prudence horizon memperbaiki synth-final
   0,5265 -> 0,1598 (setara v4 0,1579) dan mean (d) 0,3463 -> 0,1778.
   Uji pangsa kurva (half-life 12/24/48 jam): 24 jam terbaik
   (mean (c)+(d) 0,487 vs 0,490 / 0,509).

## Hasil validasi (tools/backtest_v6.py, N_MC=3000)

| suite | v6 | v3r | v4 | v5 | persistence |
|---|---|---|---|---|---|
| practice-proxy (13) | **0,0794** | 0,6998 | 0,1135 | 1,7459 | 1,4034 |
| uniform-factor (f 0,15-0,30) | **0,1455** | 0,7065 | 0,1585 | 1,7492 | 1,4066 |
| v5-style final-like (8) | 0,7960 | 1,5217 | 1,7800 | **0,5797** | 1,5518 |
| v4-style synthetic (praktik+final+CV) | **0,1778** | 1,1162 | 0,1955 | 1,1197 | 1,0652 |

- Pada faktor f=0,20 (yang dipin produksi): v6 0,0824 vs v4 0,1262
  vs v3r 0,7770. Synth-final: v6 0,1598 ~ v4 0,1579.
  Synth-practice: v6 0,0856 (terbaik).
- v5 hanya menang suite (c), didorong dunia flat-refresh-nya
  (pendatang 70% rate) yang bertentangan dengan fisika refresh terbit;
  v6 tidak mengejarnya. v6 terbaik gabungan kedua suite final-like
  (mean 0,487 vs v5 0,850, v4 0,988, v3r 1,319).
- Perkiraan rank live practice dari loss proxy 0,0794: ~110-130
  (rank 100 = 0,0758; rank 350 = 0,114) — dari 8722 sekarang. BUKAN
  top 20 (cutoff ~0,022): hanya 14 entri < 0,01, konsisten dengan
  tabel jawaban refresh yang diobservasi langsung; tidak ada lever
  jujur yang tersisa menuju 0,022 (klaster model jujur 0,08-0,15).
  Yang membayar adalah grade FINAL (10 Des), dan di sana v6 setara
  model jujur terbaik (v4).

## Batasan / risiko

- Proxy worlds mengasumsikan dispersi antar-trofi (alpha ~ U(0,3-1,0)
  yang di-rescale ke agregat). Bila dispersi nyata lebih besar, skor
  practice nyata v6 bisa lebih buruk dari 0,08; bila lebih kecil,
  bisa lebih baik. Median (faktor ~0,22) kokoh terhadap asumsi ini;
  fan yang dituning di proxy adalah bagian yang paling sensitif.
- CV cut24 (checkpoint 24 jam, horizon 24 jam) masih buruk untuk
  SEMUA model (v6 1,78; v5 1,59; persistence 1,28): rezim stres
  checkpoint dini + pertumbuhan curam. Kasus final (checkpoint ~60
  jam, horizon 108 jam) cocok dengan rezim synth-final, bukan cut24.
- Deterministik (2 run identik). Runtime 0,55-0,69 dtk/kasus (< 8 dtk).
  Output 2.777 byte (< 65.536).
