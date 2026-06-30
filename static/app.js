/* ── API helpers ─────────────────────────────────────────────────────────── */

async function api(method, path, body) {
  const opts = { method, headers: { "Content-Type": "application/json" } };
  if (body !== undefined) opts.body = JSON.stringify(body);
  const res = await fetch("/api" + path, opts);
  if (res.status === 204) return null;
  const data = await res.json();
  if (!res.ok) throw new Error(data.detail || "Request failed");
  return data;
}

const GET    = (p)    => api("GET",    p);
const POST   = (p, b) => api("POST",   p, b);
const PUT    = (p, b) => api("PUT",    p, b);
const DELETE = (p)    => api("DELETE", p);

/* ── State ───────────────────────────────────────────────────────────────── */

let state = {
  products: [],
  categories: [],
  selectedId: null,
  chart: null,
};

/* ── Toast ───────────────────────────────────────────────────────────────── */

function toast(msg, isError = false) {
  const el = document.createElement("div");
  el.className = "toast" + (isError ? " error" : "");
  el.textContent = msg;
  document.getElementById("toast-container").appendChild(el);
  setTimeout(() => el.remove(), 3000);
}

/* ── Modal helpers ───────────────────────────────────────────────────────── */

function openModal(id)  { document.getElementById(id).classList.remove("hidden"); }
function closeModal(id) { document.getElementById(id).classList.add("hidden"); }

document.querySelectorAll("[data-modal]").forEach(btn => {
  btn.addEventListener("click", () => closeModal(btn.dataset.modal));
});

document.querySelectorAll(".modal-backdrop").forEach(backdrop => {
  backdrop.addEventListener("click", e => {
    if (e.target === backdrop) closeModal(backdrop.id);
  });
});

/* ── Formatting ──────────────────────────────────────────────────────────── */

function fmt(price) {
  if (price == null) return "—";
  return "$" + Number(price).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function fmtDate(iso) {
  if (!iso) return "—";
  return new Date(iso + (iso.endsWith("Z") ? "" : "Z")).toLocaleDateString("en-US", {
    year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit"
  });
}

function fmtDateShort(iso) {
  if (!iso) return "—";
  return new Date(iso + (iso.endsWith("Z") ? "" : "Z")).toLocaleDateString("en-US", {
    month: "short", day: "numeric", year: "2-digit"
  });
}

/* ── Stats ───────────────────────────────────────────────────────────────── */

async function loadStats() {
  try {
    const s = await GET("/stats");
    document.getElementById("stat-products").textContent = `${s.total_products} product${s.total_products !== 1 ? "s" : ""}`;
    document.getElementById("stat-prices").textContent   = `${s.total_price_entries} price entries`;
    document.getElementById("stat-drops").textContent    = `${s.price_drops} price drop${s.price_drops !== 1 ? "s" : ""}`;
  } catch (_) {}
}

/* ── Categories ──────────────────────────────────────────────────────────── */

async function loadCategories() {
  state.categories = await GET("/categories");
  const filterSel = document.getElementById("category-filter");
  const formSel   = document.getElementById("product-category");
  state.categories.forEach(cat => {
    [filterSel, formSel].forEach(sel => {
      const opt = document.createElement("option");
      opt.value = cat; opt.textContent = cat;
      sel.appendChild(opt.cloneNode(true));
    });
  });
}

/* ── Product list ────────────────────────────────────────────────────────── */

async function loadProducts() {
  const search   = document.getElementById("search-input").value.trim();
  const category = document.getElementById("category-filter").value;
  const params   = new URLSearchParams();
  if (search)   params.set("search",   search);
  if (category) params.set("category", category);
  const qs = params.toString() ? "?" + params : "";
  state.products = await GET("/products" + qs);
  renderProductList();
}

function renderProductList() {
  const list = document.getElementById("product-list");
  if (!state.products.length) {
    list.innerHTML = `<div class="empty-state">No products found.<br><small>Add one with the button above.</small></div>`;
    return;
  }
  list.innerHTML = state.products.map(p => `
    <div class="product-card${p.id === state.selectedId ? " active" : ""}" data-id="${p.id}">
      <div class="product-card-name">${esc(p.name)}</div>
      <div class="product-card-meta">
        <span class="product-card-category">${esc(p.brand || p.category)}</span>
        <span class="product-card-price">${fmt(p.latest_price)}</span>
      </div>
    </div>
  `).join("");

  list.querySelectorAll(".product-card").forEach(card => {
    card.addEventListener("click", () => selectProduct(+card.dataset.id));
  });
}

/* ── Product detail ──────────────────────────────────────────────────────── */

async function selectProduct(id) {
  state.selectedId = id;
  renderProductList();
  const panel = document.getElementById("detail-panel");
  panel.innerHTML = `<div class="empty-state">Loading…</div>`;

  try {
    const [product, priceData] = await Promise.all([
      GET(`/products/${id}`),
      GET(`/products/${id}/prices`),
    ]);
    renderDetail(product, priceData.items);
  } catch (e) {
    panel.innerHTML = `<div class="empty-state">Error: ${esc(e.message)}</div>`;
  }
}

function renderDetail(product, prices) {
  const panel = document.getElementById("detail-panel");

  const latest = prices[0];
  const prev   = prices[1];
  let changeHtml = "";
  if (latest && prev) {
    const diff = latest.price - prev.price;
    const pct  = ((diff / prev.price) * 100).toFixed(1);
    if (diff !== 0) {
      const cls  = diff > 0 ? "up" : "down";
      const sign = diff > 0 ? "+" : "";
      changeHtml = `<span class="price-change-badge ${cls}">${sign}${fmt(diff)} (${sign}${pct}%)</span>`;
    }
  }

  const low  = prices.length ? Math.min(...prices.map(p => p.price)) : null;
  const high = prices.length ? Math.max(...prices.map(p => p.price)) : null;

  panel.innerHTML = `
    <div class="detail-header">
      <div class="detail-title-block">
        <h2>${esc(product.name)}</h2>
        ${product.brand ? `<div class="detail-brand">${esc(product.brand)}</div>` : ""}
        <div class="detail-badges">
          <span class="badge">${esc(product.category)}</span>
        </div>
      </div>
      <div class="detail-actions">
        <button class="btn btn-ghost btn-sm" id="btn-edit-product">Edit</button>
        <button class="btn btn-primary btn-sm" id="btn-add-price">+ Price</button>
        <button class="btn btn-danger btn-sm" id="btn-delete-product">Delete</button>
      </div>
    </div>

    <!-- Price summary -->
    <div class="detail-section">
      <h3>Price Summary</h3>
      <div class="price-summary">
        <div class="price-stat">
          <span class="price-stat-label">Latest</span>
          <span class="price-stat-value">${latest ? fmt(latest.price) : "—"}</span>
          ${changeHtml}
        </div>
        <div class="price-stat">
          <span class="price-stat-label">Lowest</span>
          <span class="price-stat-value">${fmt(low)}</span>
        </div>
        <div class="price-stat">
          <span class="price-stat-label">Highest</span>
          <span class="price-stat-value muted">${fmt(high)}</span>
        </div>
        <div class="price-stat">
          <span class="price-stat-label">Entries</span>
          <span class="price-stat-value muted">${prices.length}</span>
        </div>
      </div>
    </div>

    <!-- Price history chart -->
    ${prices.length >= 2 ? `
    <div class="detail-section">
      <h3>Price History</h3>
      <div class="chart-container">
        <canvas id="price-chart"></canvas>
      </div>
    </div>` : ""}

    <!-- Price history table -->
    <div class="detail-section">
      <h3>Price Entries</h3>
      ${prices.length ? `
      <table class="price-table">
        <thead>
          <tr>
            <th>Date</th>
            <th>Price</th>
            <th>Retailer</th>
            <th>Notes</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          ${prices.map((p, i) => {
            const next = prices[i + 1];
            let changeBadge = "";
            if (next) {
              const diff = p.price - next.price;
              if (diff !== 0) {
                const cls  = diff > 0 ? "up" : "down";
                const sign = diff > 0 ? "▲" : "▼";
                changeBadge = `<span class="price-change-badge ${cls}">${sign} ${fmt(Math.abs(diff))}</span>`;
              }
            }
            return `<tr>
              <td>${fmtDate(p.recorded_at)}</td>
              <td class="price-cell">${fmt(p.price)} ${changeBadge}</td>
              <td>${esc(p.retailer || "—")}</td>
              <td>${esc(p.notes || "—")}</td>
              <td><button class="del-btn" data-price-id="${p.id}" title="Delete entry">×</button></td>
            </tr>`;
          }).join("")}
        </tbody>
      </table>` : `
      <div class="empty-state">No prices recorded yet.<br>
        <button class="btn btn-primary btn-sm" style="margin-top:12px" id="btn-add-price-empty">+ Add First Price</button>
      </div>`}
    </div>

    <!-- Product info -->
    <div class="detail-section">
      <h3>Product Info</h3>
      <div class="info-grid">
        <div class="info-item">
          <span class="info-label">Brand</span>
          <span class="info-value">${esc(product.brand || "—")}</span>
        </div>
        <div class="info-item">
          <span class="info-label">Category</span>
          <span class="info-value">${esc(product.category)}</span>
        </div>
        <div class="info-item">
          <span class="info-label">Added</span>
          <span class="info-value">${fmtDate(product.created_at)}</span>
        </div>
        <div class="info-item">
          <span class="info-label">Product URL</span>
          <span class="info-value">${product.url
            ? `<a class="info-link" href="${esc(product.url)}" target="_blank" rel="noopener">View ↗</a>`
            : "—"}</span>
        </div>
        ${product.description ? `
        <div class="info-item" style="grid-column:1/-1">
          <span class="info-label">Description</span>
          <span class="info-value">${esc(product.description)}</span>
        </div>` : ""}
      </div>
    </div>
  `;

  // Render chart
  if (prices.length >= 2) {
    renderChart(prices);
  }

  // Wire up buttons
  document.getElementById("btn-edit-product").addEventListener("click", () => openEditProduct(product));
  document.getElementById("btn-add-price").addEventListener("click", () => openAddPrice(product.id));
  document.getElementById("btn-delete-product").addEventListener("click", () => confirmDeleteProduct(product));

  const emptyPriceBtn = document.getElementById("btn-add-price-empty");
  if (emptyPriceBtn) emptyPriceBtn.addEventListener("click", () => openAddPrice(product.id));

  panel.querySelectorAll(".del-btn[data-price-id]").forEach(btn => {
    btn.addEventListener("click", () => confirmDeletePrice(+btn.dataset.priceId, product.id));
  });
}

/* ── Chart ───────────────────────────────────────────────────────────────── */

function renderChart(prices) {
  if (state.chart) { state.chart.destroy(); state.chart = null; }
  // prices are newest-first; reverse for chronological
  const sorted = [...prices].reverse();
  const labels = sorted.map(p => fmtDateShort(p.recorded_at));
  const data   = sorted.map(p => p.price);

  const ctx = document.getElementById("price-chart").getContext("2d");
  state.chart = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [{
        label: "Price",
        data,
        borderColor: "#52b788",
        backgroundColor: "rgba(82,183,136,.12)",
        borderWidth: 2,
        pointRadius: 4,
        pointBackgroundColor: "#2d6a4f",
        fill: true,
        tension: 0.3,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: ctx => fmt(ctx.parsed.y),
          },
        },
      },
      scales: {
        y: {
          ticks: { callback: v => "$" + v.toLocaleString() },
          grid: { color: "rgba(0,0,0,.05)" },
        },
        x: { grid: { display: false } },
      },
    },
  });
}

/* ── Add / Edit Product modal ────────────────────────────────────────────── */

document.getElementById("btn-add-product").addEventListener("click", () => openAddProduct());

function openAddProduct() {
  document.getElementById("modal-product-title").textContent = "Add Product";
  document.getElementById("product-id").value        = "";
  document.getElementById("product-name").value      = "";
  document.getElementById("product-brand").value     = "";
  document.getElementById("product-category").value  = "Other";
  document.getElementById("product-url").value       = "";
  document.getElementById("product-description").value = "";
  openModal("modal-product");
}

function openEditProduct(product) {
  document.getElementById("modal-product-title").textContent = "Edit Product";
  document.getElementById("product-id").value           = product.id;
  document.getElementById("product-name").value         = product.name;
  document.getElementById("product-brand").value        = product.brand || "";
  document.getElementById("product-category").value     = product.category;
  document.getElementById("product-url").value          = product.url || "";
  document.getElementById("product-description").value  = product.description || "";
  openModal("modal-product");
}

document.getElementById("form-product").addEventListener("submit", async e => {
  e.preventDefault();
  const id       = document.getElementById("product-id").value;
  const payload  = {
    name:        document.getElementById("product-name").value.trim(),
    brand:       document.getElementById("product-brand").value.trim(),
    category:    document.getElementById("product-category").value,
    url:         document.getElementById("product-url").value.trim(),
    description: document.getElementById("product-description").value.trim(),
  };

  try {
    if (id) {
      await PUT(`/products/${id}`, payload);
      toast("Product updated");
    } else {
      const created = await POST("/products", payload);
      state.selectedId = created.id;
      toast("Product added");
    }
    closeModal("modal-product");
    await Promise.all([loadProducts(), loadStats()]);
    if (state.selectedId) selectProduct(state.selectedId);
  } catch (e) {
    toast(e.message, true);
  }
});

/* ── Add Price modal ─────────────────────────────────────────────────────── */

function openAddPrice(productId) {
  document.getElementById("price-product-id").value = productId;
  document.getElementById("price-value").value      = "";
  document.getElementById("price-retailer").value   = "";
  document.getElementById("price-notes").value      = "";
  // Default date to now in local timezone
  const now = new Date();
  now.setMinutes(now.getMinutes() - now.getTimezoneOffset());
  document.getElementById("price-date").value = now.toISOString().slice(0, 16);
  openModal("modal-price");
}

document.getElementById("form-price").addEventListener("submit", async e => {
  e.preventDefault();
  const productId  = document.getElementById("price-product-id").value;
  const dateVal    = document.getElementById("price-date").value;
  const payload = {
    price:       +document.getElementById("price-value").value,
    retailer:    document.getElementById("price-retailer").value.trim(),
    notes:       document.getElementById("price-notes").value.trim(),
    recorded_at: dateVal ? new Date(dateVal).toISOString().replace("T", " ").slice(0, 19) : undefined,
  };

  try {
    await POST(`/products/${productId}/prices`, payload);
    toast("Price entry added");
    closeModal("modal-price");
    await Promise.all([loadStats(), selectProduct(+productId)]);
    await loadProducts();
  } catch (e) {
    toast(e.message, true);
  }
});

/* ── Delete confirmations ────────────────────────────────────────────────── */

let pendingDeleteFn = null;

function confirmDeleteProduct(product) {
  document.getElementById("confirm-message").textContent =
    `Delete "${product.name}" and all its price history? This cannot be undone.`;
  pendingDeleteFn = async () => {
    await DELETE(`/products/${product.id}`);
    toast("Product deleted");
    state.selectedId = null;
    document.getElementById("detail-panel").innerHTML = `
      <div class="empty-state large">
        <div class="empty-icon">⛳</div>
        <p>Select a product to see its price history,<br>or add a new one to get started.</p>
      </div>`;
    await Promise.all([loadProducts(), loadStats()]);
  };
  openModal("modal-confirm");
}

function confirmDeletePrice(priceId, productId) {
  document.getElementById("confirm-message").textContent = "Delete this price entry?";
  pendingDeleteFn = async () => {
    await DELETE(`/prices/${priceId}`);
    toast("Price entry deleted");
    await Promise.all([selectProduct(productId), loadProducts(), loadStats()]);
  };
  openModal("modal-confirm");
}

document.getElementById("btn-confirm-delete").addEventListener("click", async () => {
  closeModal("modal-confirm");
  if (pendingDeleteFn) {
    try {
      await pendingDeleteFn();
    } catch (e) {
      toast(e.message, true);
    }
    pendingDeleteFn = null;
  }
});

/* ── Search & filter ─────────────────────────────────────────────────────── */

let searchDebounce;
document.getElementById("search-input").addEventListener("input", () => {
  clearTimeout(searchDebounce);
  searchDebounce = setTimeout(loadProducts, 250);
});

document.getElementById("category-filter").addEventListener("change", loadProducts);

/* ── Utility ─────────────────────────────────────────────────────────────── */

function esc(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/* ── Boot ────────────────────────────────────────────────────────────────── */

(async () => {
  await loadCategories();
  await Promise.all([loadProducts(), loadStats()]);
})();
