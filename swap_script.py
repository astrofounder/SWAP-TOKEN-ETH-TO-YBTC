import json
import time
import os
import random
from web3 import Web3
from web3.exceptions import TransactionNotFound
from colorama import init, Fore, Style, Back

# Inisialisasi Colorama (reset otomatis setelah setiap print)
init(autoreset=True)

# --- Konfigurasi Warna ---
INFO_COLOR = Fore.CYAN
SUCCESS_COLOR = Fore.GREEN
ERROR_COLOR = Fore.RED
WARNING_COLOR = Fore.YELLOW
LINK_COLOR = Fore.BLUE
HEADER_COLOR = Fore.MAGENTA

# --- Konfigurasi ---
RPC_URL = "https://11155111.rpc.thirdweb.com/"
PK_FILE = "PK.txt"
FAILURE_LOG_FILE = "Fail.txt"
SEPOLIA_CHAIN_ID = 11155111

# Alamat Kontrak (Sepolia)
ROUTER_ADDRESS = Web3.toChecksumAddress("0x3A9D48AB9751398BbFa63ad67599Bb04e4BdF98b") # Universal Router
WETH_ADDRESS = Web3.toChecksumAddress("0xfff9976782d46cc05630d1f6ebab18b2324d6b14") # WETH9
YBTC_ADDRESS = Web3.toChecksumAddress("0xBBd3EDd4D3B519C0d14965d9311185CFaC8c3220") # Yala BTC (YBTC) - Ganti jika berbeda
FEE_RECIPIENT_ADDRESS = Web3.toChecksumAddress("0xE49ACc3B16c097ec88Dc9352CE4Cd57aB7e35B95") # Alamat penerima fee 0.25%

# ABI Universal Router (Hanya fungsi execute yang relevan)
ROUTER_ABI = json.loads('[{"inputs":[{"internalType":"bytes","name":"commands","type":"bytes"},{"internalType":"bytes[]","name":"inputs","type":"bytes[]"},{"internalType":"uint256","name":"deadline","type":"uint256"}],"name":"execute","outputs":[],"stateMutability":"payable","type":"function"}]')

# Perkiraan Gas Limit (ambil dari transaksi contoh, bisa disesuaikan)
GAS_LIMIT_ESTIMATE = 300000 # Sedikit lebih tinggi dari contoh (249,549) untuk buffer

# Jeda antar transaksi (detik)
DELAY_BETWEEN_TXS = 5

# Konfigurasi Retry Mechanism
MAX_RETRIES = 3
RETRY_DELAY = 10 # Jeda antar retry (detik)

# --- Fungsi Helper ---

def encode_v3_path(token_addresses, fees):
    """Encode path untuk Uniswap V3.
    Contoh: [TokenA, fee, TokenB, fee, TokenC] -> encode([addrA, addrB, addrC], [fee1, fee2])
    Untuk single hop: [TokenA, fee, TokenB] -> encode([addrA, addrB], [fee])
    """
    if len(token_addresses) != len(fees) + 1:
        raise ValueError("Jumlah token harus satu lebih banyak dari jumlah fee")

    encoded = b""
    for i in range(len(fees)):
        encoded += bytes.fromhex(token_addresses[i][2:]) # Hapus 0x
        encoded += fees[i].to_bytes(3, 'big') # Fee dalam 3 bytes
    encoded += bytes.fromhex(token_addresses[-1][2:]) # Token terakhir
    return encoded

def read_private_keys(file_path):
    """Membaca private keys dari file, satu per baris."""
    if not os.path.exists(file_path):
        print(f"Error: File private key '{file_path}' tidak ditemukan.")
        return []
    with open(file_path, 'r') as f:
        keys = [line.strip() for line in f if line.strip() and not line.startswith('#')]
    print(f"Ditemukan {len(keys)} private key di '{file_path}'.")
    return keys

# --- Fungsi Logging Kegagalan (Untuk SEMUA jenis kegagalan akun) ---
def log_failure(private_key, address, reason="Unknown"):
    """Mencatat private key, alamat (jika ada), dan alasan ke file kegagalan."""
    address_str = address if address else "N/A"
    try:
        with open(FAILURE_LOG_FILE, 'a') as f:
            f.write(f"{private_key}|{address_str}|{reason}\n")
        print(f"{ERROR_COLOR}Gagal: Info akun dicatat ke {FAILURE_LOG_FILE} (Alasan: {reason})")
    except Exception as e:
        print(f"{ERROR_COLOR}Error saat mencatat kegagalan ke file: {e}")

# --- Fungsi Swap Utama ---

def swap_eth_for_ybtc(private_key, wallet_index, total_wallets):
    """Melakukan swap ETH ke YBTC menggunakan Universal Router.
    Jumlah swap adalah 3-5% random dari saldo ETH.
    """
    my_address = None # Inisialisasi my_address
    log_prefix = f"[{wallet_index + 1}/{total_wallets} Wallets]" # Tambahkan prefix log
    try:
        # 1. Koneksi Web3
        w3 = Web3(Web3.HTTPProvider(RPC_URL))
        if not w3.isConnected():
            print(f"{ERROR_COLOR}Error: Gagal terhubung ke RPC.")
            log_failure(private_key, my_address, "RPC Connection Failed") # my_address masih None di sini
            return

        # 2. Muat Akun
        try:
            account = w3.eth.account.from_key(private_key)
            my_address = account.address
            # Modifikasi log header untuk menyertakan index/total
            print(f"{HEADER_COLOR}\n{log_prefix} --- Memproses Akun: {INFO_COLOR}{my_address}{HEADER_COLOR} ---")
        except Exception as e:
            print(f"{ERROR_COLOR}{log_prefix} Error memuat private key: {e}. Pastikan format PK benar.")
            log_failure(private_key, None, "Invalid Private Key Format")
            return # Lanjut ke PK berikutnya jika ada error

        # 3. Inisialisasi Kontrak Router
        router_contract = w3.eth.contract(address=ROUTER_ADDRESS, abi=ROUTER_ABI)

        # 4. Hitung Jumlah Swap & Persiapan Parameter `execute`
        nonce = w3.eth.get_transaction_count(my_address)

        # Cek saldo ETH
        balance_wei = w3.eth.get_balance(my_address)
        balance_eth = w3.fromWei(balance_wei, 'ether')
        print(f"{INFO_COLOR}{log_prefix} Saldo ETH: {balance_eth}")

        if balance_wei == 0:
             print(f"{WARNING_COLOR}{log_prefix} Saldo ETH 0, melewati swap.")
             return

        # Hitung 3-5% random dari saldo
        random_percentage = random.uniform(3.0, 9.0)
        amount_to_swap_wei = int(balance_wei * (random_percentage / 100.0))
        amount_to_swap_eth = w3.fromWei(amount_to_swap_wei, 'ether')

        print(f"{INFO_COLOR}{log_prefix} Menghitung {random_percentage:.2f}% dari saldo: {amount_to_swap_eth} ETH akan di-swap.")

        if amount_to_swap_wei <= 0: # Pastikan ada jumlah yang valid untuk di-swap
            print(f"{WARNING_COLOR}{log_prefix} Jumlah swap yang dihitung terlalu kecil (<= 0), melewati swap.")
            return

        deadline = int(time.time()) + 600 # 10 menit deadline

        # Perintah (bytes)
        commands = b'\x0b\x00\x06\x04' # WRAP_ETH, V3_SWAP_EXACT_IN, PAY_PORTION, SWEEP

        # Inputs (bytes[])
        inputs = []

        # Input 0: WRAP_ETH
        # abi.encode(['address', 'uint256'], [recipient, amountIn])
        input_wrap = w3.codec.encode(['address', 'uint256'], [ROUTER_ADDRESS, amount_to_swap_wei]) # Gunakan jumlah yang dihitung
        inputs.append(input_wrap)

        # Input 1: V3_SWAP_EXACT_IN
        # abi.encode(['address', 'uint256', 'uint256', 'bytes', 'bool'],
        #            [recipient, amountIn, amountOutMinimum, path, payerIsUser])
        path_bytes = encode_v3_path([WETH_ADDRESS, YBTC_ADDRESS], [3000]) # Fee 0.3% = 3000
        amount_out_minimum = 1 # Slippage sangat rendah, hanya 1 wei YBTC
        input_swap = w3.codec.encode(['address', 'uint256', 'uint256', 'bytes', 'bool'],
                                     [ROUTER_ADDRESS, amount_to_swap_wei, amount_out_minimum, path_bytes, False]) # Gunakan jumlah yang dihitung
        inputs.append(input_swap)

        # Input 2: PAY_PORTION
        # abi.encode(['address', 'address', 'uint256'], [token, recipient, bips])
        fee_bips = 25 # 0.25% = 25 basis points
        input_pay_portion = w3.codec.encode(['address', 'address', 'uint256'],
                                            [YBTC_ADDRESS, FEE_RECIPIENT_ADDRESS, fee_bips])
        inputs.append(input_pay_portion)

        # Input 3: SWEEP
        # abi.encode(['address', 'address', 'uint256'], [token, recipient, amountOutMinimum])
        sweep_min_amount = 1 # Ambil semua sisa (> 1 wei)
        input_sweep = w3.codec.encode(['address', 'address', 'uint256'],
                                      [YBTC_ADDRESS, my_address, sweep_min_amount])
        inputs.append(input_sweep)

        # 5. Bangun Transaksi
        print(f"{INFO_COLOR}{log_prefix} Membangun transaksi...")
        # nonce sudah didapatkan sebelumnya

        # Gunakan EIP-1559 jika memungkinkan untuk estimasi fee
        try:
            base_fee = w3.eth.get_block('latest')['baseFeePerGas']
            # Tambah priority fee kecil (misal 1 Gwei)
            max_priority_fee_per_gas = w3.toWei(1, 'gwei')
            # Max fee = 2 * base + priority (umumnya cukup)
            max_fee_per_gas = (2 * base_fee) + max_priority_fee_per_gas

            tx_params = {
                'from': my_address,
                # 'to': ROUTER_ADDRESS, # Dihapus: Ditangani oleh build_transaction
                'value': amount_to_swap_wei, # Gunakan jumlah yang dihitung
                'gas': GAS_LIMIT_ESTIMATE, # Gunakan estimasi kasar dulu
                'maxFeePerGas': max_fee_per_gas,
                'maxPriorityFeePerGas': max_priority_fee_per_gas,
                'nonce': nonce,
                'chainId': SEPOLIA_CHAIN_ID,
            }
            # Cek apakah saldo cukup untuk value + max gas cost
            max_tx_cost = tx_params['gas'] * tx_params['maxFeePerGas']
            if balance_wei < (amount_to_swap_wei + max_tx_cost): # Gunakan jumlah yg dihitung
                print(f"{ERROR_COLOR}{log_prefix} Error: Saldo ETH tidak cukup ({balance_eth} ETH) untuk swap ({amount_to_swap_eth} ETH) + estimasi max gas ({w3.fromWei(max_tx_cost, 'ether')} ETH).")
                log_failure(private_key, my_address, "Insufficient ETH Balance for Calculated Swap + Gas")
                return

            transaction = router_contract.functions.execute(
                commands, inputs, deadline
            ).build_transaction(tx_params)

        except Exception as e:
             print(f"{ERROR_COLOR}Error saat membangun transaksi EIP-1559: {e}")
             # Fallback ke Legacy Tx (jika perlu, tapi EIP-1559 lebih baik)
             try:
                 gas_price = w3.eth.gas_price
                 print(f"{WARNING_COLOR}Menggunakan harga gas legacy: {w3.fromWei(gas_price, 'gwei')} Gwei")
                 tx_params_legacy = {
                    'from': my_address,
                    # 'to': ROUTER_ADDRESS, # Dihapus: Ditangani oleh build_transaction
                    'value': amount_to_swap_wei, # Gunakan jumlah yang dihitung
                    'gas': GAS_LIMIT_ESTIMATE, # Estimasi kasar
                    'gasPrice': gas_price,
                    'nonce': nonce,
                    'chainId': SEPOLIA_CHAIN_ID,
                 }
                 # Cek saldo legacy
                 legacy_tx_cost = tx_params_legacy['gas'] * tx_params_legacy['gasPrice']
                 if balance_wei < (amount_to_swap_wei + legacy_tx_cost): # Gunakan jumlah yg dihitung
                     print(f"{ERROR_COLOR}{log_prefix} Error: Saldo ETH tidak cukup ({balance_eth} ETH) untuk swap ({amount_to_swap_eth} ETH) + estimasi gas legacy ({w3.fromWei(legacy_tx_cost, 'ether')} ETH).")
                     log_failure(private_key, my_address, "Insufficient ETH Balance for Calculated Swap + Legacy Gas")
                     return

                 transaction = router_contract.functions.execute(
                     commands, inputs, deadline
                 ).build_transaction(tx_params_legacy)
             except Exception as legacy_err:
                 print(f"{ERROR_COLOR}Error fatal saat membangun transaksi (EIP-1559 & Legacy): {legacy_err}")
                 log_failure(private_key, my_address, f"Fatal Transaction Build Error: {legacy_err}")
                 return


        # 6. Tandatangani Transaksi
        signed_tx = w3.eth.account.sign_transaction(transaction, private_key)
        print(f"{INFO_COLOR}Transaksi ditandatangani.")

        # 7. & 8. Kirim Transaksi dan Tunggu Konfirmasi (dengan Retry)
        tx_successful = False
        last_tx_hash = None
        for attempt in range(MAX_RETRIES):
            print(f"{INFO_COLOR}\nMencoba mengirim transaksi (Percobaan {attempt + 1}/{MAX_RETRIES})...")
            try:
                # Kirim transaksi
                tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
                last_tx_hash = tx_hash # Simpan hash terakhir yang berhasil dikirim
                print(f"{SUCCESS_COLOR}Transaksi dikirim! Hash: {tx_hash.hex()}")
                print("Menunggu konfirmasi...")

                # Tunggu konfirmasi
                receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180) # Timeout 3 menit per percobaan

                if receipt['status'] == 1:
                    print(f"{SUCCESS_COLOR}Transaksi Sukses!")
                    print(f"Detail: {LINK_COLOR}https://sepolia.etherscan.io/tx/{tx_hash.hex()}")
                    tx_successful = True
                    break # Keluar dari loop retry jika sukses
                else:
                    print(f"{ERROR_COLOR}Transaksi Gagal di blockchain! Status: {receipt['status']}")
                    print(f"Detail: {LINK_COLOR}https://sepolia.etherscan.io/tx/{tx_hash.hex()}")
                    log_failure(private_key, my_address, f"Transaction Failed On-Chain (Status 0) - Hash: {tx_hash.hex() if tx_hash else 'N/A'}")
                    # Tidak retry jika gagal on-chain, keluar loop
                    break

            except TransactionNotFound:
                hash_str = last_tx_hash.hex() if last_tx_hash else 'N/A'
                print(f"{ERROR_COLOR}Error: Transaksi {hash_str} tidak ditemukan setelah timeout (Percobaan {attempt + 1}/{MAX_RETRIES}).")
                if attempt < MAX_RETRIES - 1:
                    print(f"{WARNING_COLOR}Akan mencoba lagi dalam {RETRY_DELAY} detik...")
                    time.sleep(RETRY_DELAY)
                    # Lanjut ke percobaan berikutnya
                else:
                    print(f"{ERROR_COLOR}Jumlah percobaan maksimal untuk timeout tercapai.")
                    log_failure(private_key, my_address, f"Transaction Not Found after Retries - Last Hash: {hash_str}") # Tetap log timeout di sini
                    # Keluar loop setelah percobaan terakhir

            except ValueError as ve:
                # Tangani error nonce atau gas yang mungkin muncul pada retry
                error_str = str(ve).lower()
                if 'nonce too low' in error_str or 'replacement transaction underpriced' in error_str or 'already known' in error_str:
                    print(f"{ERROR_COLOR}Error saat mengirim (Percobaan {attempt+1}): {ve}.")
                    print(f"{WARNING_COLOR}Ini bisa berarti transaksi dari percobaan sebelumnya sudah masuk atau sedang diproses.")
                    print(f"{WARNING_COLOR}Menghentikan percobaan ulang untuk akun ini. Periksa Etherscan secara manual.")
                    log_failure(private_key, my_address, f"Retry Stopped (Nonce/Gas Error): {ve}")
                    # Coba cek status hash terakhir jika ada
                    if last_tx_hash:
                        try:
                            receipt_check = w3.eth.get_transaction_receipt(last_tx_hash)
                            if receipt_check and receipt_check['status'] == 1:
                                print(f"{SUCCESS_COLOR}UPDATE: Transaksi {last_tx_hash.hex()} ternyata SUKSES.")
                                tx_successful = True # Anggap sukses jika update menemukannya
                            elif receipt_check:
                                print(f"{ERROR_COLOR}UPDATE: Transaksi {last_tx_hash.hex()} ternyata GAGAL.")
                            else:
                                print(f"{WARNING_COLOR}UPDATE: Status transaksi {last_tx_hash.hex()} masih belum pasti.")
                        except TransactionNotFound:
                            print(f"{WARNING_COLOR}UPDATE: Transaksi {last_tx_hash.hex()} masih belum ditemukan.")
                        except Exception as check_err:
                             print(f"{ERROR_COLOR}UPDATE: Gagal memeriksa status tx terakhir: {check_err}")
                    break # Keluar dari loop retry
                else:
                    # Error ValueError lain saat mengirim
                    print(f"{ERROR_COLOR}Error tak terduga (ValueError) saat mengirim (Percobaan {attempt+1}): {ve}")
                    log_failure(private_key, my_address, f"Unexpected ValueError During Send: {ve}")
                    import traceback
                    traceback.print_exc()
                    break # Keluar loop jika ada error kirim lain

            except Exception as e:
                # Tangani error lain saat mengirim atau menunggu
                print(f"{ERROR_COLOR}Error tak terduga (Percobaan {attempt + 1}): {e}")
                log_failure(private_key, my_address, f"Unexpected Error During Send/Wait: {e}")
                import traceback
                traceback.print_exc()
                # Keluar loop jika ada error tak terduga
                break

        # Setelah loop retry selesai atau di-break
        if not tx_successful:
             # Pesan gagal sudah dicetak di dalam loop atau di log_failure
             # print(f"Gagal memproses swap untuk akun {my_address} setelah {MAX_RETRIES} percobaan.")
             pass # Cukup pass karena log_failure sudah dipanggil sebelumnya

    except Exception as e:
        # Tangani error yang terjadi SEBELUM loop retry (koneksi, build tx, dll)
        error_context = f"akun {my_address}" if my_address else "proses"
        print(f"{ERROR_COLOR}\nTerjadi error tak terduga di luar loop retry untuk {error_context}: {e}")
        # Log kegagalan jika terjadi setelah my_address didapatkan tapi sebelum loop retry
        if my_address:
             log_failure(private_key, my_address, f"Unexpected Error Outside Retry Loop: {e}")
        import traceback
        traceback.print_exc()

# --- Eksekusi Skrip ---
if __name__ == "__main__":
    private_keys = read_private_keys(PK_FILE)
    total_keys = len(private_keys)

    if not private_keys:
        print("Tidak ada private key yang valid untuk diproses. Keluar.")
    else:
        print(f"{HEADER_COLOR}\nAkan melakukan swap 3-5% random dari saldo ETH untuk {total_keys} akun.")

        for i, pk in enumerate(private_keys):
            # Panggil fungsi tanpa argumen jumlah ETH
            swap_eth_for_ybtc(pk, i, total_keys)
            if i < total_keys - 1: # Jangan delay setelah akun terakhir
                # Dapatkan log_prefix dari dalam fungsi tidak praktis, jadi kita buat ulang di sini untuk log jeda
                log_prefix_jeda = f"[{i + 1}/{total_keys} Wallets]"
                print(f"{INFO_COLOR}\n{log_prefix_jeda} Menunggu {DELAY_BETWEEN_TXS} detik sebelum akun berikutnya...")
                time.sleep(DELAY_BETWEEN_TXS)

        print(f"{HEADER_COLOR}\n--- Selesai memproses semua akun --- {Style.RESET_ALL}") 