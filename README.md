# Sepolia ETH -> Token Swap (Uniswap Universal Router)

Skrip Python ini dirancang untuk melakukan swap Ether (ETH) ke token ERC20 tertentu (secara default Yala BTC - YBTC) pada jaringan testnet Sepolia. Skrip ini menggunakan Uniswap Universal Router dan mendukung pemrosesan beberapa wallet secara otomatis.

**Fitur Utama:**

*   **Multi-Wallet:** Membaca beberapa private key dari file `PK.txt` dan memprosesnya secara berurutan.
*   **Swap Persentase Acak:** Secara otomatis men-swap persentase acak (antara 3% hingga 9%, dapat diubah di kode) dari saldo ETH asli *setiap* wallet.
*   **Uniswap Universal Router:** Berinteraksi langsung dengan kontrak Universal Router untuk melakukan swap, mereplikasi logika transaksi yang kompleks (Wrap ETH -> V3 Swap -> Pay Portion -> Sweep).
*   **Dukungan EIP-1559:** Mencoba menggunakan transaksi Tipe 2 (EIP-1559) untuk penentuan biaya gas yang lebih efisien, dengan fallback ke transaksi Legacy jika diperlukan.
*   **Estimasi Gas:** Mencoba mengestimasi gas limit yang dibutuhkan untuk transaksi.
*   **Mekanisme Coba Ulang (Retry):** Mencoba ulang pengiriman transaksi jika terjadi timeout (`TransactionNotFound`) saat menunggu konfirmasi (maksimal 3 kali).
*   **Logging Kegagalan:** Mencatat informasi (Private Key, Alamat, Alasan) ke `Fail.txt` untuk setiap wallet yang gagal menyelesaikan proses swap.
*   **Logging Berwarna:** Menggunakan `colorama` untuk output terminal yang lebih mudah dibaca.

## ⚠️ Peringatan Penting & Penafian

*   **RISIKO PRIVATE KEY:** Skrip ini membutuhkan akses ke **PRIVATE KEYS** Anda yang disimpan dalam file `PK.txt`. Private key memberikan **kontrol penuh** atas aset Anda. **Jangan pernah membagikan private key Anda atau file `PK.txt` kepada siapapun.** Pastikan file ini disimpan dengan sangat aman.
*   **TESTNET SAJA:** Skrip ini dikonfigurasi untuk jaringan **Sepolia Testnet**. Menggunakannya di Ethereum Mainnet atau jaringan utama lainnya dengan private key asli akan **sangat berisiko** dan dapat mengakibatkan **kehilangan dana permanen**.
*   **TUJUAN EDUKASI/PENGUJIAN:** Gunakan skrip ini hanya untuk tujuan edukasi atau pengujian di testnet. Penulis tidak bertanggung jawab atas kehilangan dana atau masalah lain yang timbul dari penggunaan atau modifikasi skrip ini.
*   **TANPA JAMINAN:** Skrip ini disediakan "sebagaimana adanya" tanpa jaminan apa pun. Lakukan riset Anda sendiri (DYOR) sebelum menggunakannya.

## Prasyarat

*   Python 3.8 atau lebih baru
*   pip (biasanya terinstal bersama Python)

## Setup

1.  **Clone Repositori:**
    ```bash
    git clone https://github.com/astrofounder/SWAP-TOKEN-ETH-TO-YBTC.git
    cd SWAP-TOKEN-ETH-TO-YBTC
    ```

2.  **Instal Dependensi:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Siapkan Private Keys:**
    *   Buat file bernama `PK.txt` di direktori yang sama dengan `swap_script.py`.
    *   Masukkan private key akun Sepolia Anda ke dalam `PK.txt`, **satu private key per baris**.
    *   Pastikan tidak ada spasi tambahan dan formatnya benar (biasanya diawali `0x`).
    *   **SANGAT PENTING:** Lindungi file `PK.txt` ini! Pertimbangkan untuk menambahkannya ke `.gitignore` jika Anda menggunakan Git untuk mencegah unggahan yang tidak disengaja.
    *   Pastikan setiap akun memiliki saldo ETH Sepolia yang cukup untuk jumlah swap ditambah biaya gas.

4.  **(Opsional) Periksa Konfigurasi:**
    *   Buka `swap_script.py`.
    *   Di bagian atas, Anda dapat meninjau/mengubah variabel konfigurasi seperti `RPC_URL` (pastikan kunci API Alchemy Anda masih valid), alamat token (`YBTC_ADDRESS`), alamat penerima fee (`FEE_RECIPIENT_ADDRESS`), persentase random swap, pengaturan retry, dll., jika diperlukan.

## Penggunaan

Jalankan skrip dari terminal Anda:

```bash
python swap_script.py
```

Skrip akan:
1.  Membaca private keys dari `PK.txt`.
2.  Memproses setiap akun satu per satu.
3.  Menampilkan log berwarna yang menunjukkan progres, saldo, jumlah swap yang dihitung, status transaksi, dan detail lainnya.
4.  Menunggu beberapa detik antar pemrosesan akun.
5.  Mencatat kegagalan (jika ada) ke `Fail.txt`.

## Output

*   **Terminal:** Menampilkan log proses secara real-time dengan indikator warna untuk sukses, error, peringatan, dan informasi.
*   **`Fail.txt`:** Dibuat jika ada kegagalan. Berisi baris dengan format `PRIVATE_KEY|WALLET_ADDRESS|REASON` untuk setiap akun yang gagal diproses.
