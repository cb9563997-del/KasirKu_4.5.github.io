KASIRKU PRO 4.5 — TERMUX ANDROID

CARA INSTALL:
1. Ekstrak ZIP ke folder yang mudah ditemukan, misalnya Download/KasirKu_Pro_4.5.
2. Buka Termux.
3. Jalankan:
   termux-setup-storage
   pkg update
   pkg install python unzip
4. Masuk ke folder hasil ekstrak. Contoh:
   cd /sdcard/Download/KasirKu_Pro_4.5
   bash START_KASIRKU.sh
   (Sesuaikan nama folder jika berbeda.)
5. Buka Chrome dan kunjungi:
   http://127.0.0.1:5000

PIN AWAL:
Kasir = 1111
Admin = 2222
Owner = 3333
Segera login sebagai Owner lalu ganti PIN lewat Pengaturan.

FITUR:
- Kasir, keranjang, total, pembayaran, kembalian.
- SQLite lokal, transaksi tersimpan, stok otomatis berkurang.
- Admin/Owner dapat mengelola produk dan stok.
- Scan barcode kamera pada browser yang mendukung BarcodeDetector.
- Struk cetak melalui dialog print browser.
- Laporan omzet dan estimasi laba kotor.
- Pengaturan nama/alamat toko dan PIN.
- Metode pembayaran Tunai, QRIS, Transfer.

CATATAN:
- Server harus tetap berjalan di Termux saat dipakai.
- Ini berjalan lokal pada HP ini, bukan hosting publik.
- QRIS hanya metode pencatatan; belum ada verifikasi pembayaran otomatis.
- Backup file kasirku.db secara berkala.
- PIN awal adalah contoh; ganti sebelum dipakai sungguhan.
- Jangan buka server ini ke internet tanpa menambahkan keamanan yang sesuai.
