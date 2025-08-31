# billing_app.py
import csv
import os
import webbrowser
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog, filedialog

# ---------- Config ----------
PRODUCTS_CSV = "products.csv"
INVOICES_DIR = "invoices"
GST_DEFAULT = Decimal("18.0")  # percent
CURRENCY_QUANT = Decimal("0.01")
# ----------------------------

def money(d: Decimal) -> str:
    return f"{d.quantize(CURRENCY_QUANT, rounding=ROUND_HALF_UP)}"

def read_products(path=PRODUCTS_CSV):
    products = {}
    if not os.path.exists(path):
        return products
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            code = r.get("code") or r.get("id") or r.get("sku")
            name = r.get("name") or r.get("product") or ""
            price = r.get("price") or "0"
            if not code:
                continue
            try:
                price_d = Decimal(price)
            except:
                price_d = Decimal("0")
            products[code] = {"name": name, "price": price_d}
    return products

def ensure_invoices_dir():
    os.makedirs(INVOICES_DIR, exist_ok=True)

def next_invoice_number():
    ensure_invoices_dir()
    nums = []
    for fname in os.listdir(INVOICES_DIR):
        if fname.startswith("invoice_") and fname.endswith(".csv"):
            try:
                n = int(fname.split("_")[1].split(".")[0])
                nums.append(n)
            except:
                pass
    return max(nums + [0]) + 1

def save_invoice_csv(inv_number, invoice_data, filename=None):
    ensure_invoices_dir()
    if filename is None:
        filename = os.path.join(INVOICES_DIR, f"invoice_{inv_number}.csv")
    with open(filename, "w", newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["invoice_number", inv_number])
        writer.writerow(["date", invoice_data["date"]])
        writer.writerow(["customer_name", invoice_data.get("customer_name","")])
        writer.writerow([])
        writer.writerow(["code","name","price","qty","total"])
        for row in invoice_data["items"]:
            writer.writerow([row["code"], row["name"], money(row["price"]), row["qty"], money(row["line_total"])])
        writer.writerow([])
        writer.writerow(["subtotal", money(invoice_data["subtotal"])])
        writer.writerow(["gst_percent", str(invoice_data["gst_percent"])])
        writer.writerow(["gst_total", money(invoice_data["gst_total"])])
        writer.writerow(["cgst", money(invoice_data["cgst"])])
        writer.writerow(["sgst", money(invoice_data["sgst"])])
        writer.writerow(["grand_total", money(invoice_data["grand_total"])])
    return filename

def save_invoice_html(inv_number, invoice_data, filename=None):
    ensure_invoices_dir()
    if filename is None:
        filename = os.path.join(INVOICES_DIR, f"invoice_{inv_number}.html")
    rows_html = ""
    for row in invoice_data["items"]:
        rows_html += f"<tr><td>{row['code']}</td><td>{row['name']}</td><td align='right'>{money(row['price'])}</td><td align='center'>{row['qty']}</td><td align='right'>{money(row['line_total'])}</td></tr>\n"
    html = f"""
    <html>
    <head><meta charset="utf-8"><title>Invoice {inv_number}</title></head>
    <body>
    <h2>Invoice #{inv_number}</h2>
    <p>Date: {invoice_data['date']}</p>
    <p>Customer: {invoice_data.get('customer_name','-')}</p>
    <table border="1" cellspacing="0" cellpadding="6" width="80%">
      <thead>
        <tr><th>Code</th><th>Item</th><th>Price</th><th>Qty</th><th>Line Total</th></tr>
      </thead>
      <tbody>
      {rows_html}
      </tbody>
    </table>
    <p>Subtotal: <b>{money(invoice_data['subtotal'])}</b></p>
    <p>GST ({invoice_data['gst_percent']}%): <b>{money(invoice_data['gst_total'])}</b> (CGST {money(invoice_data['cgst'])} + SGST {money(invoice_data['sgst'])})</p>
    <h3>Grand Total: {money(invoice_data['grand_total'])}</h3>
    <hr>
    <p>Thank you for your business!</p>
    </body>
    </html>
    """
    with open(filename, "w", encoding='utf-8') as f:
        f.write(html)
    return filename

class BillingApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Billing Software")
        self.geometry("900x600")
        self.products = read_products()
        if not self.products:
            messagebox.showinfo("No products", f"No products found in {PRODUCTS_CSV}. Please create the file and restart.")
        self.cart = []  # list of dicts {code,name,price,qty,line_total}
        self.gst_percent = GST_DEFAULT

        self.create_ui()
        self.refresh_product_list()
        self.update_totals()

    def create_ui(self):
        # Left: product list + quantity
        left = tk.Frame(self)
        left.pack(side=tk.LEFT, fill=tk.Y, padx=10, pady=10)

        tk.Label(left, text="Products").pack(anchor="w")
        self.product_listbox = tk.Listbox(left, width=40, height=20)
        self.product_listbox.pack()
        self.product_listbox.bind("<Double-Button-1>", lambda e: self.add_selected_product())

        qty_frame = tk.Frame(left)
        qty_frame.pack(pady=6, anchor="w")
        tk.Label(qty_frame, text="Qty:").pack(side=tk.LEFT)
        self.qty_var = tk.IntVar(value=1)
        tk.Entry(qty_frame, textvariable=self.qty_var, width=5).pack(side=tk.LEFT, padx=6)
        tk.Button(qty_frame, text="Add to Cart", command=self.add_selected_product).pack(side=tk.LEFT)

        tk.Button(left, text="Load products CSV", command=self.load_products_csv).pack(pady=6, anchor="w")

        # Right: cart and totals
        right = tk.Frame(self)
        right.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10, pady=10)

        topright = tk.Frame(right)
        topright.pack(fill=tk.X)
        tk.Label(topright, text="Cart").pack(anchor="w")
        cols = ("code","name","price","qty","total")
        self.tree = ttk.Treeview(right, columns=cols, show="headings", height=12)
        for c in cols:
            self.tree.heading(c, text=c.capitalize())
            self.tree.column(c, anchor="center")
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<Delete>", lambda e: self.remove_selected())

        btns = tk.Frame(right)
        btns.pack(fill=tk.X, pady=6)
        tk.Button(btns, text="Remove selected", command=self.remove_selected).pack(side=tk.LEFT)
        tk.Button(btns, text="Clear cart", command=self.clear_cart).pack(side=tk.LEFT, padx=6)

        # Totals and GST
        bottom = tk.Frame(right)
        bottom.pack(fill=tk.X, pady=8)
        tk.Label(bottom, text="Customer Name:").grid(row=0, column=0, sticky="e")
        self.customer_entry = tk.Entry(bottom, width=30)
        self.customer_entry.grid(row=0, column=1, sticky="w")

        tk.Label(bottom, text="GST %:").grid(row=1, column=0, sticky="e")
        self.gst_var = tk.StringVar(value=str(self.gst_percent))
        tk.Entry(bottom, textvariable=self.gst_var, width=8).grid(row=1, column=1, sticky="w")

        self.subtotal_label = tk.Label(bottom, text="Subtotal: 0.00")
        self.subtotal_label.grid(row=2, column=0, columnspan=2, sticky="w")
        self.gst_label = tk.Label(bottom, text="GST: 0.00 (CGST 0.00 + SGST 0.00)")
        self.gst_label.grid(row=3, column=0, columnspan=2, sticky="w")
        self.grand_label = tk.Label(bottom, text="Grand Total: 0.00", font=("Arial", 14, "bold"))
        self.grand_label.grid(row=4, column=0, columnspan=2, sticky="w", pady=6)

        actions = tk.Frame(right)
        actions.pack(fill=tk.X)
        tk.Button(actions, text="Generate Invoice", command=self.generate_invoice).pack(side=tk.LEFT)
        tk.Button(actions, text="Export cart CSV", command=self.export_cart_csv).pack(side=tk.LEFT, padx=6)
        tk.Button(actions, text="Open invoices folder", command=self.open_invoices_folder).pack(side=tk.LEFT, padx=6)

    def refresh_product_list(self):
        self.product_listbox.delete(0, tk.END)
        for code, p in sorted(self.products.items()):
            self.product_listbox.insert(tk.END, f"{code} | {p['name']} | {money(p['price'])}")

    def add_selected_product(self):
        sel = self.product_listbox.curselection()
        if not sel:
            messagebox.showwarning("Select product", "Please select a product from the list (double-click works).")
            return
        idx = sel[0]
        line = self.product_listbox.get(idx)
        code = line.split("|")[0].strip()
        prod = self.products.get(code)
        if not prod:
            return
        qty = self.qty_var.get()
        if qty <= 0:
            messagebox.showwarning("Quantity", "Enter quantity >= 1")
            return
        price = prod["price"]
        line_total = (price * Decimal(qty)).quantize(CURRENCY_QUANT, rounding=ROUND_HALF_UP)
        # if already in cart, increment qty
        found = False
        for item in self.cart:
            if item["code"] == code:
                item["qty"] += qty
                item["line_total"] = (item["price"] * Decimal(item["qty"])).quantize(CURRENCY_QUANT, rounding=ROUND_HALF_UP)
                found = True
                break
        if not found:
            self.cart.append({"code": code, "name": prod["name"], "price": price, "qty": qty, "line_total": line_total})
        self.refresh_cart()
        self.update_totals()

    def refresh_cart(self):
        for i in self.tree.get_children():
            self.tree.delete(i)
        for item in self.cart:
            self.tree.insert("", tk.END, values=(item["code"], item["name"], money(item["price"]), item["qty"], money(item["line_total"])))

    def remove_selected(self):
        sel = self.tree.selection()
        if not sel:
            return
        for s in sel:
            vals = self.tree.item(s, "values")
            code = vals[0]
            # remove from cart (first occurrence)
            for i, it in enumerate(self.cart):
                if it["code"] == code:
                    del self.cart[i]
                    break
        self.refresh_cart()
        self.update_totals()

    def clear_cart(self):
        if messagebox.askyesno("Clear", "Clear the cart?"):
            self.cart = []
            self.refresh_cart()
            self.update_totals()

    def update_totals(self):
        subtotal = Decimal("0")
        for it in self.cart:
            subtotal += it["line_total"]
        try:
            gst_percent = Decimal(self.gst_var.get())
        except:
            gst_percent = GST_DEFAULT
            self.gst_var.set(str(gst_percent))
        gst_total = (subtotal * gst_percent / Decimal("100")).quantize(CURRENCY_QUANT, rounding=ROUND_HALF_UP)
        cgst = (gst_total / 2).quantize(CURRENCY_QUANT, rounding=ROUND_HALF_UP)
        sgst = gst_total - cgst  # safe split
        grand_total = (subtotal + gst_total).quantize(CURRENCY_QUANT, rounding=ROUND_HALF_UP)
        self.subtotal = subtotal
        self.gst_total = gst_total
        self.cgst = cgst
        self.sgst = sgst
        self.grand_total = grand_total
        # update labels
        self.subtotal_label.config(text=f"Subtotal: {money(subtotal)}")
        self.gst_label.config(text=f"GST: {money(gst_total)} ({money(cgst)} CGST + {money(sgst)} SGST)")
        self.grand_label.config(text=f"Grand Total: {money(grand_total)}")

    def generate_invoice(self):
        if not self.cart:
            messagebox.showwarning("Empty cart", "Add items before generating an invoice.")
            return
        inv_num = next_invoice_number()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        customer = self.customer_entry.get().strip()
        invoice_data = {
            "date": now,
            "customer_name": customer,
            "items": self.cart,
            "subtotal": self.subtotal,
            "gst_percent": str(self.gst_var.get()),
            "gst_total": self.gst_total,
            "cgst": self.cgst,
            "sgst": self.sgst,
            "grand_total": self.grand_total
        }
        csvfile = save_invoice_csv(inv_num, invoice_data)
        htmlfile = save_invoice_html(inv_num, invoice_data)
        messagebox.showinfo("Saved", f"Invoice #{inv_num} saved.\nCSV: {csvfile}\nHTML: {htmlfile}")
        # open the html in default browser for print/preview
        webbrowser.open_new_tab(os.path.abspath(htmlfile))
        # reset cart
        self.cart = []
        self.refresh_cart()
        self.update_totals()

    def export_cart_csv(self):
        if not self.cart:
            messagebox.showwarning("Empty cart", "No items to export.")
            return
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV files","*.csv")])
        if not path:
            return
        with open(path, "w", newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["code","name","price","qty","total"])
            for it in self.cart:
                writer.writerow([it["code"], it["name"], money(it["price"]), it["qty"], money(it["line_total"])])
        messagebox.showinfo("Exported", f"Cart exported to {path}")

    def open_invoices_folder(self):
        ensure_invoices_dir()
        path = os.path.abspath(INVOICES_DIR)
        if os.name == 'nt':
            os.startfile(path)
        else:
            try:
                # mac / linux
                webbrowser.open("file://" + path)
            except:
                messagebox.showinfo("Invoices folder", path)

    def load_products_csv(self):
        path = filedialog.askopenfilename(title="Select products CSV", filetypes=[("CSV files","*.csv")])
        if not path:
            return
        # copy/replace local products file
        try:
            with open(path, newline='', encoding='utf-8') as src:
                txt = src.read()
            with open(PRODUCTS_CSV, "w", newline='', encoding='utf-8') as dst:
                dst.write(txt)
            self.products = read_products()
            self.refresh_product_list()
            messagebox.showinfo("Loaded", f"Products loaded from {path} into {PRODUCTS_CSV}")
        except Exception as e:
            messagebox.showerror("Error", str(e))

if __name__ == "__main__":
    app = BillingApp()
    app.mainloop()
