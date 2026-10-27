from flask import Flask, request, redirect, url_for, session, flash, render_template_string, g
import sqlite3, os, secrets
from functools import wraps
from datetime import datetime

BASE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE, "kasirku.db")
app = Flask(__name__)
app.secret_key = os.environ.get("KASIRKU_SECRET", secrets.token_hex(24))

DEFAULT_PINS = {"Kasir": "1111", "Admin": "2222", "Owner": "3333"}

def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(exc):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS products(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      barcode TEXT UNIQUE, name TEXT NOT NULL,
      price INTEGER NOT NULL DEFAULT 0,
      stock INTEGER NOT NULL DEFAULT 0,
      cost INTEGER NOT NULL DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS sales(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      created_at TEXT NOT NULL, cashier TEXT NOT NULL,
      total INTEGER NOT NULL, paid INTEGER NOT NULL,
      change_amount INTEGER NOT NULL, payment TEXT NOT NULL DEFAULT 'Tunai'
    );
    CREATE TABLE IF NOT EXISTS sale_items(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      sale_id INTEGER NOT NULL REFERENCES sales(id),
      product_id INTEGER, name TEXT NOT NULL,
      qty INTEGER NOT NULL, price INTEGER NOT NULL, cost INTEGER NOT NULL
    );
    CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT NOT NULL);
    """)
    conn.commit()
    conn.close()

def setting(key, default=""):
    row = db().execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else default

def save_setting(key, value):
    db().execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))
    db().commit()

def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not session.get("role"):
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapper

def roles(*allowed):
    def deco(fn):
        @wraps(fn)
        @login_required
        def wrapper(*args, **kwargs):
            if session.get("role") not in allowed:
                flash("Akses ditolak untuk jabatan ini.", "error")
                return redirect(url_for("home"))
            return fn(*args, **kwargs)
        return wrapper
    return deco

LAYOUT = r"""
<!doctype html><html lang="id"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>{{ title }} • KasirKu Pro 4.5</title><link rel="stylesheet" href="{{ url_for('static', filename='style.css') }}">
</head><body>
<header class="topbar"><a class="brand" href="{{ url_for('home') }}"><span class="logo">K</span><span>KasirKu <small>PRO 4.5</small></span></a>
{% if session.get('role') %}<div class="userpill">{{ session.get('name','Petugas') }} · {{ session.get('role') }}</div>{% endif %}</header>
{% if session.get('role') %}<nav class="nav">
<a href="{{ url_for('home') }}">Kasir</a>
{% if session.get('role') in ['Admin','Owner'] %}<a href="{{ url_for('products') }}">Produk & Stok</a>{% endif %}
{% if session.get('role') == 'Owner' %}<a href="{{ url_for('reports') }}">Laporan</a><a href="{{ url_for('settings') }}">Pengaturan</a>{% endif %}
<a href="{{ url_for('logout') }}">Keluar</a></nav>{% endif %}
<main class="container">
{% with messages = get_flashed_messages(with_categories=true) %}{% for category,message in messages %}<div class="flash {{ category }}">{{ message }}</div>{% endfor %}{% endwith %}
{{ body|safe }}
<footer>KasirKu Pro 4.5 · Lokal di perangkat ini</footer></main></body></html>
"""

def page(title, body, **context):
    return render_template_string(LAYOUT, title=title, body=render_template_string(body, **context))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        role = request.form.get("role", "")
        name = request.form.get("name", "").strip()
        pin = request.form.get("pin", "").strip()
        pins = {r: setting("pin_"+r.lower(), v) for r,v in DEFAULT_PINS.items()}
        if role in pins and name and secrets.compare_digest(pin, pins[role]):
            session.clear()
            session["role"], session["name"] = role, name
            return redirect(url_for("home"))
        flash("Nama, jabatan, atau PIN salah.", "error")
    body = r"""
    <section class="login-wrap"><div class="hero"><div class="eyebrow">POINT OF SALE • 4.5 ULTIMATE</div><h1>Kasir lebih cepat.<br><span>Bisnis lebih terkontrol.</span></h1><p>Sistem kasir ringan untuk toko, langsung dari HP Android.</p><div class="hero-stats"><div><b>01</b><small>Penjualan</small></div><div><b>02</b><small>Stok barang</small></div><div><b>03</b><small>Laporan</small></div></div></div>
    <form class="panel login-form" method="post"><div class="eyebrow">MASUK SISTEM</div><h2>Siapa yang bertugas?</h2>
    <label>Nama petugas</label><input name="name" required placeholder="Contoh: Arif">
    <label>Jabatan</label><select name="role"><option>Kasir</option><option>Admin</option><option>Owner</option></select>
    <label>PIN jabatan</label><input name="pin" inputmode="numeric" type="password" required placeholder="Masukkan PIN">
    <button class="btn primary full">Masuk KasirKu</button><p class="hint">PIN awal: Kasir 1111 · Admin 2222 · Owner 3333. Ganti lewat menu Pengaturan sebagai Owner.</p></form></section>"""
    return page("Login", body)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
@login_required
def home():
    products = db().execute("SELECT * FROM products ORDER BY name").fetchall()
    today = datetime.now().strftime("%Y-%m-%d")
    stats = db().execute("SELECT COUNT(*) n, COALESCE(SUM(total),0) total FROM sales WHERE substr(created_at,1,10)=?", (today,)).fetchone()
    body = r"""
    <div class="pagehead"><div><div class="eyebrow">DASHBOARD</div><h1>Kasir hari ini</h1><p>Input barang, cek total, lalu selesaikan pembayaran.</p></div><span class="status">● Sistem siap</span></div>
    <div class="stats"><div class="stat"><small>Transaksi hari ini</small><b>{{ stats.n }}</b></div><div class="stat"><small>Penjualan hari ini</small><b>Rp {{ '{:,}'.format(stats.total).replace(',', '.') }}</b></div><div class="stat"><small>Produk terdaftar</small><b>{{ products|length }}</b></div></div>
    <div class="pos-grid"><section class="panel"><div class="panelhead"><h2>Tambah barang</h2><button type="button" class="btn light small" onclick="scanBarcode()">▣ Scan kamera</button></div>
    <div id="scanner" class="scanner hidden"><video id="video" playsinline></video><p id="scanmsg" class="hint">Arahkan kamera ke barcode.</p><button class="btn light small" type="button" onclick="stopScan()">Tutup kamera</button></div>
    <div class="searchrow"><input id="search" placeholder="Cari nama atau barcode..." oninput="filterProducts()"><input id="qty" type="number" min="1" value="1" class="qtyinput" aria-label="Jumlah"></div>
    <div id="product-list" class="product-list">{% for p in products %}<button type="button" class="product-option" data-name="{{ p.name|lower }}" data-barcode="{{ p.barcode or '' }}" onclick="addProduct({{ p.id }}, {{ p.name|tojson }}, {{ p.price }}, {{ p.stock }}, {{ p.cost }})"><span><b>{{ p.name }}</b><small>{{ p.barcode or 'Tanpa barcode' }} · Stok {{ p.stock }}</small></span><strong>Rp {{ '{:,}'.format(p.price).replace(',', '.') }}</strong></button>{% else %}<p class="empty">Belum ada produk. Minta Admin menambahkan barang.</p>{% endfor %}</div></section>
    <section class="panel"><div class="panelhead"><h2>Keranjang</h2><button class="textbtn" onclick="clearCart()">Kosongkan</button></div>
    <div id="cart" class="cart empty">Pilih barang untuk memulai transaksi.</div><div class="total-line"><span>Total belanja</span><b id="total">Rp 0</b></div>
    <form id="checkout" method="post" action="{{ url_for('checkout') }}"><input type="hidden" name="cart" id="cartdata"><label>Metode pembayaran</label><select name="payment" id="payment"><option>Tunai</option><option>QRIS</option><option>Transfer</option></select>
    <label>Uang diterima (Rp)</label><input id="paid" name="paid" type="number" min="0" inputmode="numeric" placeholder="Contoh: 100000" required oninput="calcChange()"><div class="change-line"><span>Kembalian</span><b id="change">Rp 0</b></div><button class="btn primary full" type="submit">Bayar & Simpan Transaksi</button><p class="hint">Untuk QRIS, pembayaran tetap harus dikonfirmasi secara nyata sebelum transaksi diselesaikan.</p></form></section></div>
    <script>
    const products = {}; let cart = [];
    function money(n){return 'Rp '+Number(n||0).toLocaleString('id-ID')}
    function addProduct(id,name,price,stock,cost){if(stock<1){alert('Stok habis!');return;}let item=cart.find(x=>x.id===id);let q=Math.max(1,parseInt(document.getElementById('qty').value||1));if((item?item.qty:0)+q>stock){alert('Jumlah melebihi stok tersedia.');return;}if(item)item.qty+=q;else cart.push({id,name,price,stock,cost,qty:q});renderCart();}
    function renderCart(){const el=document.getElementById('cart');if(!cart.length){el.className='cart empty';el.textContent='Pilih barang untuk memulai transaksi.';}else{el.className='cart';el.innerHTML=cart.map((x,i)=>`<div class="cartitem"><div><b>${escapeHtml(x.name)}</b><small>${x.qty} × ${money(x.price)}</small></div><strong>${money(x.qty*x.price)}</strong><button type="button" class="remove" onclick="removeItem(${i})">×</button></div>`).join('');}document.getElementById('total').textContent=money(cart.reduce((s,x)=>s+x.qty*x.price,0));document.getElementById('cartdata').value=JSON.stringify(cart.map(x=>({id:x.id,qty:x.qty})));calcChange();}
    function removeItem(i){cart.splice(i,1);renderCart()}function clearCart(){cart=[];renderCart()}
    function calcChange(){let total=cart.reduce((s,x)=>s+x.qty*x.price,0),paid=Number(document.getElementById('paid').value||0);document.getElementById('change').textContent=money(Math.max(0,paid-total));}
    function filterProducts(){let q=document.getElementById('search').value.toLowerCase();document.querySelectorAll('.product-option').forEach(e=>e.style.display=(e.dataset.name.includes(q)||e.dataset.barcode.toLowerCase().includes(q))?'flex':'none');}
    function escapeHtml(s){return String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));}
    document.getElementById('checkout').addEventListener('submit',e=>{if(!cart.length){e.preventDefault();alert('Keranjang masih kosong.');return;}let total=cart.reduce((s,x)=>s+x.qty*x.price,0);if(Number(document.getElementById('paid').value||0)<total){e.preventDefault();alert('Uang diterima belum cukup.');}});
    let stream=null, scanTimer=null;
    async function scanBarcode(){if(!('BarcodeDetector' in window)){alert('Browser ini belum mendukung scan barcode otomatis. Coba Chrome terbaru atau gunakan kolom pencarian/barcode.');return;}try{stream=await navigator.mediaDevices.getUserMedia({video:{facingMode:'environment'}});let video=document.getElementById('video');video.srcObject=stream;document.getElementById('scanner').classList.remove('hidden');await video.play();let detector=new BarcodeDetector({formats:['ean_13','ean_8','code_128','upc_a','upc_e','qr_code']});async function tick(){if(!stream)return;try{let codes=await detector.detect(video);if(codes.length){document.getElementById('search').value=codes[0].rawValue;filterProducts();stopScan();document.getElementById('scanmsg').textContent='Barcode ditemukan: '+codes[0].rawValue;return;}}catch(e){}scanTimer=setTimeout(tick,180);}tick();}catch(e){alert('Kamera tidak bisa dibuka. Izinkan akses kamera di browser.');stopScan();}}
    function stopScan(){if(scanTimer)clearTimeout(scanTimer);if(stream){stream.getTracks().forEach(t=>t.stop());stream=null;}document.getElementById('scanner').classList.add('hidden');}
    </script>"""
    return page("Kasir", body, products=products, stats=stats)

@app.route("/checkout", methods=["POST"])
@login_required
def checkout():
    import json
    try:
        items = json.loads(request.form.get("cart", "[]"))
        paid = int(request.form.get("paid", "0"))
        payment = request.form.get("payment", "Tunai")
        if not isinstance(items, list) or not items:
            raise ValueError()
        conn = db()
        clean, total = [], 0
        for item in items:
            pid, qty = int(item["id"]), int(item["qty"])
            if qty < 1: raise ValueError()
            p = conn.execute("SELECT * FROM products WHERE id=?", (pid,)).fetchone()
            if not p or p["stock"] < qty:
                flash("Produk tidak ditemukan atau stok tidak cukup. Transaksi dibatalkan.", "error")
                return redirect(url_for("home"))
            clean.append((p, qty)); total += p["price"] * qty
        if paid < total:
            flash("Uang diterima kurang dari total belanja.", "error")
            return redirect(url_for("home"))
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur = conn.execute("INSERT INTO sales(created_at,cashier,total,paid,change_amount,payment) VALUES(?,?,?,?,?,?)",
                           (now, session.get("name","Petugas"), total, paid, paid-total, payment))
        sale_id = cur.lastrowid
        for p, qty in clean:
            conn.execute("INSERT INTO sale_items(sale_id,product_id,name,qty,price,cost) VALUES(?,?,?,?,?,?)",
                         (sale_id, p["id"], p["name"], qty, p["price"], p["cost"]))
            conn.execute("UPDATE products SET stock=stock-? WHERE id=?", (qty, p["id"]))
        conn.commit()
        return redirect(url_for("receipt", sale_id=sale_id))
    except (ValueError, KeyError, TypeError):
        flash("Data transaksi tidak valid.", "error")
        return redirect(url_for("home"))

@app.route("/receipt/<int:sale_id>")
@login_required
def receipt(sale_id):
    sale = db().execute("SELECT * FROM sales WHERE id=?", (sale_id,)).fetchone()
    if not sale:
        flash("Transaksi tidak ditemukan.", "error")
        return redirect(url_for("home"))
    items = db().execute("SELECT * FROM sale_items WHERE sale_id=?", (sale_id,)).fetchall()
    body = r"""
    <div class="pagehead no-print"><div><div class="eyebrow">TRANSAKSI BERHASIL</div><h1>Struk penjualan</h1><p>Transaksi #{{ sale.id }} berhasil disimpan.</p></div><button class="btn primary" onclick="window.print()">Cetak struk</button></div>
    <section class="receipt"><div class="receipt-center"><h2>{{ store_name }}</h2><p>{{ store_address }}</p><b>STRUK PEMBAYARAN</b><p>{{ sale.created_at }}<br>No: {{ sale.id }} · Kasir: {{ sale.cashier }}</p></div><hr>
    {% for i in items %}<div class="receipt-row"><span>{{ i.name }}<br>{{ i.qty }} × Rp {{ '{:,}'.format(i.price).replace(',', '.') }}</span><b>Rp {{ '{:,}'.format(i.qty*i.price).replace(',', '.') }}</b></div>{% endfor %}<hr>
    <div class="receipt-row"><span>Total</span><b>Rp {{ '{:,}'.format(sale.total).replace(',', '.') }}</b></div><div class="receipt-row"><span>Bayar ({{ sale.payment }})</span><b>Rp {{ '{:,}'.format(sale.paid).replace(',', '.') }}</b></div><div class="receipt-row"><span>Kembalian</span><b>Rp {{ '{:,}'.format(sale.change_amount).replace(',', '.') }}</b></div><hr><p class="receipt-center">Terima kasih telah berbelanja!</p><div class="no-print"><a class="btn primary full" href="{{ url_for('home') }}">Transaksi baru</a></div></section>
    """
    return page("Struk", body, sale=sale, items=items, store_name=setting("store_name","KasirKu Store"), store_address=setting("store_address",""))

@app.route("/products", methods=["GET", "POST"])
@roles("Admin", "Owner")
def products():
    if request.method == "POST":
        action = request.form.get("action","save")
        conn = db()
        if action == "delete":
            conn.execute("DELETE FROM products WHERE id=?", (request.form.get("id"),))
            conn.commit(); flash("Produk dihapus.", "success")
        else:
            try:
                name=request.form.get("name","").strip()
                barcode=request.form.get("barcode","").strip() or None
                price=int(request.form.get("price","0")); cost=int(request.form.get("cost","0")); stock=int(request.form.get("stock","0"))
                pid=request.form.get("id","").strip()
                if not name or min(price,cost,stock)<0: raise ValueError()
                if pid:
                    conn.execute("UPDATE products SET barcode=?,name=?,price=?,stock=?,cost=? WHERE id=?", (barcode,name,price,stock,cost,pid))
                else:
                    conn.execute("INSERT INTO products(barcode,name,price,stock,cost) VALUES(?,?,?,?,?)", (barcode,name,price,stock,cost))
                conn.commit(); flash("Produk berhasil disimpan.", "success")
            except sqlite3.IntegrityError:
                flash("Barcode sudah digunakan produk lain.", "error")
            except ValueError:
                flash("Periksa nama, harga, modal, dan stok.", "error")
        return redirect(url_for("products"))
    rows=db().execute("SELECT * FROM products ORDER BY name").fetchall()
    body = r"""
    <div class="pagehead"><div><div class="eyebrow">INVENTORY</div><h1>Produk & stok</h1><p>Tambah produk atau perbarui stok dan harga.</p></div></div>
    <section class="panel"><h2>Tambah produk</h2><form method="post" class="formgrid">
    <div class="wide"><label>Nama produk</label><input name="name" required placeholder="Contoh: Air mineral 600 ml"></div>
    <div><label>Barcode (opsional)</label><input name="barcode" placeholder="Scan atau ketik kode"></div>
    <div><label>Harga jual (Rp)</label><input name="price" type="number" min="0" required></div>
    <div><label>Harga modal (Rp)</label><input name="cost" type="number" min="0" value="0" required></div>
    <div><label>Stok awal</label><input name="stock" type="number" min="0" value="0" required></div>
    <div class="wide"><button class="btn primary">Simpan produk</button></div></form></section>
    <section class="panel"><div class="panelhead"><h2>Daftar produk ({{ rows|length }})</h2></div><div class="tablewrap"><table><thead><tr><th>Produk</th><th>Harga</th><th>Modal</th><th>Stok</th><th>Aksi</th></tr></thead><tbody>
    {% for p in rows %}<tr><td><b>{{ p.name }}</b><small>{{ p.barcode or 'Tanpa barcode' }}</small></td><td>Rp {{ '{:,}'.format(p.price).replace(',', '.') }}</td><td>Rp {{ '{:,}'.format(p.cost).replace(',', '.') }}</td><td>{{ p.stock }}</td><td><details><summary>Edit</summary><form method="post" class="editform"><input type="hidden" name="id" value="{{ p.id }}"><input name="name" value="{{ p.name }}" required><input name="barcode" value="{{ p.barcode or '' }}" placeholder="Barcode"><input name="price" type="number" min="0" value="{{ p.price }}" required><input name="cost" type="number" min="0" value="{{ p.cost }}" required><input name="stock" type="number" min="0" value="{{ p.stock }}" required><button class="btn primary small">Update</button></form><form method="post" onsubmit="return confirm('Hapus produk ini?')"><input type="hidden" name="action" value="delete"><input type="hidden" name="id" value="{{ p.id }}"><button class="btn danger small">Hapus</button></form></details></td></tr>{% else %}<tr><td colspan="5">Belum ada produk.</td></tr>{% endfor %}
    </tbody></table></div></section>"""
    return page("Produk", body, rows=rows)

@app.route("/reports")
@roles("Owner")
def reports():
    rows=db().execute("SELECT * FROM sales ORDER BY id DESC LIMIT 100").fetchall()
    today=datetime.now().strftime("%Y-%m-%d")
    daily=db().execute("SELECT COUNT(*) n, COALESCE(SUM(total),0) total FROM sales WHERE substr(created_at,1,10)=?",(today,)).fetchone()
    profit=db().execute("SELECT COALESCE(SUM((si.price-si.cost)*si.qty),0) profit FROM sale_items si JOIN sales s ON s.id=si.sale_id WHERE substr(s.created_at,1,10)=?",(today,)).fetchone()["profit"]
    body=r"""
    <div class="pagehead"><div><div class="eyebrow">OWNER INSIGHTS</div><h1>Laporan penjualan</h1><p>Ringkasan hari ini dan 100 transaksi terbaru.</p></div></div>
    <div class="stats"><div class="stat"><small>Transaksi hari ini</small><b>{{ daily.n }}</b></div><div class="stat"><small>Omzet hari ini</small><b>Rp {{ '{:,}'.format(daily.total).replace(',', '.') }}</b></div><div class="stat"><small>Estimasi laba kotor</small><b>Rp {{ '{:,}'.format(profit).replace(',', '.') }}</b></div></div>
    <section class="panel"><div class="panelhead"><h2>Transaksi terbaru</h2><button class="btn light small" onclick="window.print()">Cetak laporan</button></div><div class="tablewrap"><table><thead><tr><th>No / Waktu</th><th>Kasir</th><th>Metode</th><th>Total</th><th></th></tr></thead><tbody>{% for s in rows %}<tr><td>#{{ s.id }}<small>{{ s.created_at }}</small></td><td>{{ s.cashier }}</td><td>{{ s.payment }}</td><td>Rp {{ '{:,}'.format(s.total).replace(',', '.') }}</td><td><a href="{{ url_for('receipt',sale_id=s.id) }}">Struk</a></td></tr>{% else %}<tr><td colspan="5">Belum ada transaksi.</td></tr>{% endfor %}</tbody></table></div></section>
    <p class="hint">Laba kotor dihitung dari harga jual dikurangi modal produk yang dimasukkan Admin. Biaya operasional belum dihitung.</p>"""
    return page("Laporan", body, rows=rows, daily=daily, profit=profit)

@app.route("/settings", methods=["GET", "POST"])
@roles("Owner")
def settings():
    if request.method=="POST":
        for key in ["store_name","store_address","qris_note"]:
            save_setting(key, request.form.get(key,"").strip())
        for role in ["Kasir","Admin","Owner"]:
            pin=request.form.get("pin_"+role.lower(),"").strip()
            if pin:
                if not pin.isdigit() or len(pin)<4 or len(pin)>8:
                    flash("PIN harus berupa 4–8 digit angka. Pengaturan lain mungkin sudah tersimpan.", "error")
                    return redirect(url_for("settings"))
                save_setting("pin_"+role.lower(),pin)
        flash("Pengaturan disimpan.", "success")
        return redirect(url_for("settings"))
    body=r"""
    <div class="pagehead"><div><div class="eyebrow">KONFIGURASI</div><h1>Pengaturan toko</h1><p>Ganti nama toko dan PIN masing-masing jabatan.</p></div></div>
    <form class="panel settingsform" method="post"><h2>Identitas toko</h2><label>Nama toko</label><input name="store_name" value="{{ store_name }}" required><label>Alamat toko</label><input name="store_address" value="{{ store_address }}" placeholder="Alamat untuk struk"><label>Catatan QRIS (opsional)</label><textarea name="qris_note" rows="2" placeholder="Contoh: Scan QRIS resmi di meja kasir">{{ qris_note }}</textarea><p class="hint">Versi ini belum memvalidasi pembayaran QRIS secara otomatis. Jangan tandai pembayaran lunas hanya berdasarkan tampilan gambar.</p><hr><h2>Ubah PIN (4–8 digit)</h2>
    {% for role in ['Kasir','Admin','Owner'] %}<label>PIN {{ role }}</label><input name="pin_{{ role|lower }}" type="password" inputmode="numeric" placeholder="Kosongkan jika tidak diubah">{% endfor %}<button class="btn primary full">Simpan pengaturan</button></form>"""
    return page("Pengaturan", body, store_name=setting("store_name","KasirKu Store"), store_address=setting("store_address",""), qris_note=setting("qris_note",""))

@app.route("/health")
def health():
    return {"app":"KasirKu Pro 4.5","status":"ok"}

if __name__ == "__main__":
    init_db()
    print("\\nKasirKu Pro 4.5 berjalan di http://127.0.0.1:5000")
    print("PIN awal: Kasir 1111 | Admin 2222 | Owner 3333")
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT","5000")), debug=False)
