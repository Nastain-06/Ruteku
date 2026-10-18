import httpx
import json

BASE = "http://localhost:8000"

def run_test():
    client = httpx.Client(timeout=10)

    # 1. Register
    print("=== 1. REGISTRASI AKUN ===")
    reg_data = {
        "email": "mahasiswa@ruteku.id",
        "password": "password123",
        "full_name": "Nastain"
    }
    r = client.post(f"{BASE}/auth/register", json=reg_data)
    if r.status_code == 201:
        print("Registrasi berhasil:", r.json())
    else:
        print("Info registrasi:", r.json())

    # 2. Login
    print("\n=== 2. LOGIN ===")
    login_data = {
        "email": "mahasiswa@ruteku.id",
        "password": "password123"
    }
    r = client.post(f"{BASE}/auth/login", json=login_data)
    res_login = r.json()
    print("Login sukses! Selamat datang,", res_login.get("full_name"))
    token = res_login["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 3. Cari Destinasi
    print("\n=== 3. DAFTAR DESTINASI DI BALI ===")
    r = client.get(f"{BASE}/destinations", params={"location": "Bali"}, headers=headers)
    for d in r.json():
        print(f"  • {d['name']} ({d['category']}) - Tiket: Rp {d['price_estimate']:,}".replace(",", "."))

    # 4. Generate AI Itinerary
    print("\n=== 4. GENERATE ITINERARY OLEH AI ===")
    body_itinerary = {
        "origin": "Samarinda",
        "destination": "Bali",
        "start_date": "2026-12-01",
        "end_date": "2026-12-04",
        "travelers": 2,
        "budget": 9000000,
        "interests": ["alam", "budaya"]
    }
    r = client.post(f"{BASE}/itineraries/generate", json=body_itinerary, headers=headers)
    plan = r.json()

    print(f"Status AI: {'Aktif (OpenAI)' if plan.get('ai_used') else 'Algoritma Fallback Mandiri (Offline)'}")
    print(f"Rute: {plan['origin']} -> {plan['destination']} ({plan['start_date']} s/d {plan['end_date']})")
    print(f"Jumlah Peserta: {plan['travelers']} Orang | Anggaran: Rp {plan['budget']:,}".replace(",", "."))
    print("\n--- Jadwal Harian ---")
    for day in plan.get("days", []):
        print(f"[Hari ke-{day['day']}]")
        for it in day.get("items", []):
            tiket = it["ticket_price"]["value"]
            harga_str = f"Rp {tiket:,}".replace(",", ".") if tiket is not None else "Gratis"
            print(f"   {it['time']} : {it['name']} ({it['category']}) - Tiket: {harga_str}")

    print("\n--- Rincian Estimasi Biaya ---")
    cost = plan["cost"]
    print(f"  • Hotel        : Rp {cost['hotel']['total']:,} ({cost['hotel']['nights']} malam x {cost['hotel']['rooms']} kamar)".replace(",", "."))
    print(f"  • Transportasi : Rp {cost['transport']['total']:,} (Tiket PP untuk {plan['travelers']} orang)".replace(",", "."))
    print(f"  • Tiket Objek  : Rp {cost['tickets']['total']:,}".replace(",", "."))
    print(f"  ----------------------------------------")
    print(f"  TOTAL ESTIMASI : Rp {cost['total']:,}".replace(",", "."))
    if cost["over_budget"]:
        print(f"  STATUS         : MELEBIHI ANGGARAN sebesar Rp {abs(cost['difference']):,}".replace(",", "."))
    else:
        print(f"  STATUS         : AMAN (Sisa anggaran: Rp {cost['difference']:,})".replace(",", "."))

    print("\n--- Catatan & Peringatan Sistem ---")
    for w in plan.get("warnings", []):
        print(f"  ⚠ {w}")

    # 5. Simpan Itinerary
    print("\n=== 5. SIMPAN RENCANA KE RIWAYAT ===")
    save_data = {
        "plan_id": plan["plan_id"],
        "title": "Liburan Seru ke Bali Bareng Teman"
    }
    r = client.post(f"{BASE}/itineraries", json=save_data, headers=headers)
    print("Tersimpan dengan ID:", r.json())

    # 6. Lihat Riwayat
    print("\n=== 6. CEK RIWAYAT PERJALANAN ===")
    r = client.get(f"{BASE}/itineraries", headers=headers)
    for h in r.json():
        print(f"  • {h['title']} - Total Biaya: Rp {h['total_cost']:,} (Dibuat: {h['created_at']})".replace(",", "."))

if __name__ == "__main__":
    run_test()
