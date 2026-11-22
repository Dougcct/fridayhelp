(() => {
  const STORAGE_KEY = "blackfriday_tracker_v1";

  const FALLBACK_DATA = {
    meta: { title: "Friday Help", updatedAt: new Date().toISOString(), currency: "BRL" },
    items: [],
    history: []
  };

  const CATEGORY_COLORS = {
    "Hardware": "#38bdf8",
    "Periféricos": "#a78bfa",
    "Notebooks & PCs": "#60a5fa",
    "Celulares & Tablets": "#2dd4bf",
    "TV & Vídeo": "#f472b6",
    "Áudio & Som": "#fb923c",
    "Som Automotivo": "#f59e0b",
    "Games": "#c084fc",
    "Eletrônicos": "#818cf8",
    "Casa & Eletrodomésticos": "#34d399",
    "Ferramentas": "#facc15",
    "Automotivo": "#f87171",
    "Moda & Beleza": "#ec4899",
    "Esporte & Lazer": "#22c55e",
    "Outros": "#94a3b8"
  };

  const KNOWN_BRANDS = [
    "Western Digital", "Rise Mode", "O Boticário", "Kingston", "Crucial", "SanDisk",
    "Spectrum", "Futuretech", "KeepData", "Masterdrive", "Hiksemi", "Patriot",
    "Corsair", "Samsung", "Logitech", "Redragon", "HyperX", "Pioneer", "Taramps",
    "Stetsom", "Bomber", "Spyder", "Detoner", "Oestesom", "Falcon", "Mondial",
    "Electrolux", "Brastemp", "Motorola", "Xiaomi", "Apple", "Lenovo", "Acer",
    "Asus", "Dell", "Sony", "AIWA", "Philco", "Midea", "Consul", "Makita",
    "Bosch", "DeWalt", "Nike", "Adidas", "Puma", "Natura", "L'Oréal", "ADATA",
    "Lexar", "Duex", "Ceamere", "Razer", "JBL", "MSI", "LG", "HP", "WD"
  ];

  const GENERIC_PREFIXES = new Set([
    "ssd", "hd", "kit", "som", "caixa", "trio", "monitor", "gamer", "notebook",
    "smartphone", "celular", "fone", "ouvido", "mouse", "teclado", "memoria",
    "placa", "fonte", "smart", "tv", "interno", "externo", "automotivo",
    "portatil", "de", "para", "com", "line", "carro"
  ]);

  function extractBrand(rawTitle, fallback = "") {
    const clean = String(rawTitle || "").split(" — Vendedor:")[0].trim();
    if (!clean) return fallback;

    for (const brand of KNOWN_BRANDS) {
      const escaped = brand.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      if (new RegExp(`\\b${escaped}\\b`, "i").test(clean)) {
        return brand === "WD" ? "WD" : brand;
      }
    }

    const words = clean.replace(/[,;|•()[\]"]/g, " ").split(/\s+/).filter(Boolean);
    for (const w of words) {
      const low = w.toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "");
      if (GENERIC_PREFIXES.has(low)) continue;
      if (/^\d+(gb|tb|mb|pol|w|hz|v|mm)?$/i.test(low)) continue;
      if (/^sata/i.test(low) || low === "iii" || low === "ii") continue;
      return w;
    }
    return fallback || clean.split(/\s+/)[0];
  }

  function getCategoryColor(category) {
    if (!category) return CATEGORY_COLORS.Outros;
    if (CATEGORY_COLORS[category]) return CATEGORY_COLORS[category];
    const palette = Object.values(CATEGORY_COLORS);
    let hash = 0;
    for (let i = 0; i < category.length; i += 1) {
      hash = (hash * 31 + category.charCodeAt(i)) >>> 0;
    }
    return palette[hash % palette.length];
  }

  const OFFERS_PER_PAGE = 3;
  const offerPages = new Map();

  let state = structuredClone(FALLBACK_DATA);
  let serverAvailable = false;
  let authMode = "local";
  let currentUser = null;

  const el = {
    syncStatus: document.getElementById("syncStatus"),
    userBadge: document.getElementById("userBadge"),
    btnAuth: document.getElementById("btnAuth"),
    btnLogout: document.getElementById("btnLogout"),
    authModal: document.getElementById("authModal"),
    authForm: document.getElementById("authForm"),
    authEmail: document.getElementById("authEmail"),
    authPassword: document.getElementById("authPassword"),
    authFeedback: document.getElementById("authFeedback"),
    btnAuthSignup: document.getElementById("btnAuthSignup"),
    kpiTargetTotal: document.getElementById("kpiTargetTotal"),
    kpiItemCount: document.getElementById("kpiItemCount"),
    kpiBestTotal: document.getElementById("kpiBestTotal"),
    kpiOffersCount: document.getElementById("kpiOffersCount"),
    kpiSavings: document.getElementById("kpiSavings"),
    kpiGoals: document.getElementById("kpiGoals"),
    kpiPurchased: document.getElementById("kpiPurchased"),
    filterSearch: document.getElementById("filterSearch"),
    filterCategory: document.getElementById("filterCategory"),
    categoryPills: document.getElementById("categoryPills"),
    filterStatus: document.getElementById("filterStatus"),
    filterPriority: document.getElementById("filterPriority"),
    sortBy: document.getElementById("sortBy"),
    itemsList: document.getElementById("itemsList"),
    historyList: document.getElementById("historyList"),
    itemModal: document.getElementById("itemModal"),
    itemForm: document.getElementById("itemForm"),
    offerModal: document.getElementById("offerModal"),
    offerForm: document.getElementById("offerForm")
  };

  function escapeHtml(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function safeUrl(url) {
    if (!url) return "";
    try {
      const parsed = new URL(url);
      return parsed.protocol === "http:" || parsed.protocol === "https:" ? parsed.href : "";
    } catch {
      return "";
    }
  }

  function formatBRL(value) {
    return Number(value || 0).toLocaleString("pt-BR", {
      style: "currency",
      currency: "BRL"
    });
  }

  function formatDate(iso) {
    if (!iso) return "-";
    const date = new Date(iso);
    if (Number.isNaN(date.getTime())) return iso;
    return date.toLocaleString("pt-BR", { dateStyle: "short", timeStyle: "short" });
  }

  function uid(prefix) {
    return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
  }

  function setSyncBadge(online, text) {
    el.syncStatus.textContent = text;
    el.syncStatus.className = `sync-pill ${online ? "sync-online" : "sync-offline"}`;
  }

  function updateAuthUI() {
    if (authMode !== "supabase") {
      el.userBadge.hidden = true;
      el.btnAuth.hidden = true;
      el.btnLogout.hidden = true;
      return;
    }
    if (currentUser) {
      el.userBadge.textContent = currentUser.email || "Conectado";
      el.userBadge.hidden = false;
      el.btnAuth.hidden = true;
      el.btnLogout.hidden = false;
    } else {
      el.userBadge.hidden = true;
      el.btnAuth.hidden = false;
      el.btnLogout.hidden = true;
    }
  }

  async function loadData() {
    if (window.location.protocol.startsWith("http")) {
      try {
        const authRes = await fetch("/api/auth/status", { cache: "no-store" });
        if (authRes.ok) {
          const auth = await authRes.json();
          authMode = auth.mode || "local";
          currentUser = auth.user || null;
          updateAuthUI();

          if (authMode === "supabase" && !currentUser) {
            serverAvailable = true;
            state = structuredClone(FALLBACK_DATA);
            setSyncBadge(false, "Faça login para carregar seus itens");
            render();
            el.authModal.showModal();
            return;
          }
        }

        const res = await fetch("/api/deals", { cache: "no-store" });
        if (res.ok) {
          state = await res.json();
          serverAvailable = true;
          localStorage.setItem(STORAGE_KEY, JSON.stringify(state));
          setSyncBadge(true, authMode === "supabase" ? "Sincronizado (Nuvem)" : "Sincronizado com deals.json");
          render();
          return;
        }
      } catch {
        // Fallback para localStorage abaixo
      }
    }

    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved) {
      try {
        state = JSON.parse(saved);
      } catch {
        state = structuredClone(FALLBACK_DATA);
      }
    }
    serverAvailable = false;
    setSyncBadge(false, "Modo local (navegador)");
    render();
  }

  async function saveData() {
    state.meta = state.meta || {};
    state.meta.updatedAt = new Date().toISOString();
    localStorage.setItem(STORAGE_KEY, JSON.stringify(state));

    if (serverAvailable) {
      try {
        const res = await fetch("/api/deals", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(state)
        });
        if (!res.ok) throw new Error("Erro HTTP");
        setSyncBadge(true, authMode === "supabase" ? "Salvo na nuvem" : "Salvo em deals.json");
      } catch {
        setSyncBadge(false, "Erro ao salvar no servidor (salvo local)");
      }
    }
  }

  function addHistory(action, itemName, details) {
    state.history = state.history || [];
    state.history.unshift({
      id: uid("hist"),
      timestamp: new Date().toISOString(),
      action,
      itemName,
      details
    });
  }

  function getBestOffer(item) {
    if (!item.offers || item.offers.length === 0) return null;
    return item.offers.reduce((best, curr) => (curr.price < best.price ? curr : best), item.offers[0]);
  }

  function getDiscountPct(offer) {
    if (!offer || !offer.originalPrice || offer.originalPrice <= offer.price) return 0;
    return Math.round(((offer.originalPrice - offer.price) / offer.originalPrice) * 100);
  }

  function updateCategoryFilter() {
    const current = el.filterCategory.value;
    const categories = Array.from(new Set(state.items.map((i) => i.category).filter(Boolean))).sort();
    el.filterCategory.innerHTML = `<option value="all">Todas as categorias</option>` +
      categories.map((c) => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join("");
    if (categories.includes(current)) {
      el.filterCategory.value = current;
    }

    if (el.categoryPills) {
      const selected = el.filterCategory.value;
      const pills = [
        `<button class="cat-pill ${selected === "all" ? "active" : ""}" data-cat="all" type="button">Todas (${state.items.length})</button>`
      ];
      for (const cat of categories) {
        const count = state.items.filter((i) => i.category === cat).length;
        const color = getCategoryColor(cat);
        pills.push(
          `<button class="cat-pill ${selected === cat ? "active" : ""}" data-cat="${escapeHtml(cat)}" style="--cat-color:${color}" type="button">` +
          `<span class="cat-dot"></span>${escapeHtml(cat)} (${count})</button>`
        );
      }
      el.categoryPills.innerHTML = pills.join("");
    }
  }

  function renderKPIs() {
    const activeItems = state.items.filter((i) => i.status !== "Descartado");
    const targetTotal = activeItems.reduce((sum, i) => sum + Number(i.targetPrice || 0), 0);

    let bestTotal = 0;
    let savings = 0;
    let offersCount = 0;
    let goalsMet = 0;
    let purchased = 0;

    for (const item of state.items) {
      offersCount += (item.offers || []).length;
      if (item.status === "Comprado") purchased += 1;

      const best = getBestOffer(item);
      if (item.status !== "Descartado" && best) {
        bestTotal += Number(best.price || 0);
        if (best.originalPrice && best.originalPrice > best.price) {
          savings += best.originalPrice - best.price;
        }
        if (best.price <= item.targetPrice) {
          goalsMet += 1;
        }
      }
    }

    el.kpiTargetTotal.textContent = formatBRL(targetTotal);
    el.kpiItemCount.textContent = `${activeItems.length} itens ativos`;
    el.kpiBestTotal.textContent = formatBRL(bestTotal);
    el.kpiOffersCount.textContent = `${offersCount} ofertas registradas`;
    el.kpiSavings.textContent = formatBRL(savings);
    el.kpiGoals.textContent = `${goalsMet} / ${activeItems.length}`;
    el.kpiPurchased.textContent = `${purchased} comprados`;
  }

  function getFilteredItems() {
    const search = el.filterSearch.value.trim().toLowerCase();
    const cat = el.filterCategory.value;
    const status = el.filterStatus.value;
    const prio = el.filterPriority.value;
    const sort = el.sortBy.value;

    const prioRank = { Alta: 1, "Média": 2, Baixa: 3 };

    return state.items
      .filter((item) => {
        if (cat !== "all" && item.category !== cat) return false;
        if (status !== "all" && item.status !== status) return false;
        if (prio !== "all" && item.priority !== prio) return false;
        if (search) {
          const hay = [
            item.name,
            item.category,
            item.notes,
            ...(item.offers || []).map((o) => `${o.store} ${o.coupon} ${o.notes}`)
          ].join(" ").toLowerCase();
          if (!hay.includes(search)) return false;
        }
        return true;
      })
      .sort((a, b) => {
        const bestA = getBestOffer(a);
        const bestB = getBestOffer(b);
        if (sort === "bestPriceAsc") {
          return (bestA ? bestA.price : Infinity) - (bestB ? bestB.price : Infinity);
        }
        if (sort === "discountDesc") {
          return getDiscountPct(bestB) - getDiscountPct(bestA);
        }
        if (sort === "nameAsc") {
          return a.name.localeCompare(b.name, "pt-BR");
        }
        return (prioRank[a.priority] || 9) - (prioRank[b.priority] || 9);
      });
  }

  function renderItems() {
    const items = getFilteredItems();
    if (items.length === 0) {
      el.itemsList.innerHTML = `<div class="empty-state">Nenhum item encontrado. Clique em <strong>+ Novo Item</strong> para começar!</div>`;
      return;
    }

    el.itemsList.innerHTML = items.map((item) => {
      const best = getBestOffer(item);
      const goalMet = best && best.price <= item.targetPrice;
      const discount = getDiscountPct(best);
      const offersSorted = [...(item.offers || [])].sort((a, b) => a.price - b.price);
      const totalPages = Math.max(1, Math.ceil(offersSorted.length / OFFERS_PER_PAGE));
      const currentPage = Math.min(Math.max(1, offerPages.get(item.id) || 1), totalPages);
      offerPages.set(item.id, currentPage);
      const visibleOffers = offersSorted.slice(
        (currentPage - 1) * OFFERS_PER_PAGE,
        currentPage * OFFERS_PER_PAGE
      );

      const paginationHtml = totalPages > 1
        ? `<div class="offers-pagination" aria-label="Páginas de ofertas">
            ${Array.from({ length: totalPages }, (_, idx) => {
              const pageNum = idx + 1;
              return `<button class="page-btn ${pageNum === currentPage ? "active" : ""}" data-action="offer-page" data-item="${escapeHtml(item.id)}" data-page="${pageNum}" type="button">${pageNum}</button>`;
            }).join("")}
          </div>`
        : "";

      const offersHtml = offersSorted.length === 0
        ? `<p class="item-notes">Nenhuma oferta registrada ainda.</p>`
        : `<div class="offers-section">
            ${visibleOffers.map((offer) => {
              const pct = getDiscountPct(offer);
              const link = safeUrl(offer.url);
              const storeLabel = link
                ? `<a href="${escapeHtml(link)}" target="_blank" rel="noopener noreferrer">${escapeHtml(offer.store)} ↗</a>`
                : escapeHtml(offer.store);
              const metaParts = [
                offer.notes || "",
                offer.coupon ? `Cupom: ${offer.coupon}` : "",
                offer.cashback || "",
                offer.shipping && offer.shipping !== "A calcular" ? `Frete: ${offer.shipping}` : ""
              ].filter(Boolean).join(" • ");
              return `<div class="offer-row">
                <div class="offer-main">
                  <strong>${storeLabel}</strong>
                  ${metaParts ? `<span class="offer-meta" title="${escapeHtml(metaParts)}">${escapeHtml(metaParts)}</span>` : ""}
                </div>
                <div class="offer-right">
                  <div class="offer-price-line">
                    ${pct > 0 ? `<span class="text-success">-${pct}%</span>` : ""}
                    <strong>${formatBRL(offer.price)}</strong>
                  </div>
                  <button class="btn btn-danger btn-sm" data-action="delete-offer" data-item="${escapeHtml(item.id)}" data-offer="${escapeHtml(offer.id)}" type="button">Excluir</button>
                </div>
              </div>`;
            }).join("")}
            ${paginationHtml}
          </div>`;

      const catColor = getCategoryColor(item.category);
      const bestFullTitle = best
        ? (best.notes || best.store || "").split(" — Vendedor:")[0].trim()
        : "";
      const bestBrand = best ? extractBrand(bestFullTitle, best.store) : "";
      const historyHtml = (item.priceHistory || []).length > 0
        ? `<details class="price-history-box">
            <summary>Histórico de preços (${item.priceHistory.length} registros)</summary>
            <ul>
              ${item.priceHistory.slice().reverse().map((h) =>
                `<li><strong>${formatBRL(h.price)}</strong> em ${escapeHtml(h.store)} (${escapeHtml(formatDate(h.date))})${h.note ? ` — ${escapeHtml(h.note)}` : ""}</li>`
              ).join("")}
            </ul>
          </details>`
        : "";

      return `<article class="item-card ${goalMet ? "goal-met" : ""}" style="--cat-color:${catColor}">
        <div class="item-header">
          <div>
            <div class="item-title-row">
              <h3>${escapeHtml(item.name)}</h3>
              ${item.category ? `<span class="badge badge-category">${escapeHtml(item.category)}</span>` : ""}
              <span class="badge badge-${escapeHtml(item.priority.toLowerCase())}">${escapeHtml(item.priority)}</span>
              ${goalMet ? `<span class="badge badge-goal">Meta atingida!</span>` : ""}
            </div>
            ${item.notes ? `<p class="item-notes" title="${escapeHtml(item.notes)}">${escapeHtml(item.notes)}</p>` : ""}
          </div>

          <div class="item-actions">
            <select class="status-select" data-action="change-status" data-item="${escapeHtml(item.id)}">
              ${["Monitorando", "Meta atingida", "Comprado", "Descartado"].map((s) =>
                `<option value="${s}" ${item.status === s ? "selected" : ""}>${s}</option>`
              ).join("")}
            </select>
            <div class="item-action-icons">
              <button class="icon-action-btn" data-action="search-offers" data-item="${escapeHtml(item.id)}" type="button" title="Buscar ofertas" aria-label="Buscar ofertas">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
              </button>
              <button class="icon-action-btn" data-action="edit-item" data-item="${escapeHtml(item.id)}" type="button" title="Editar" aria-label="Editar">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/></svg>
              </button>
              <button class="icon-action-btn icon-action-danger" data-action="delete-item" data-item="${escapeHtml(item.id)}" type="button" title="Excluir" aria-label="Excluir">
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M18 6 6 18"/><path d="m6 6 12 12"/></svg>
              </button>
            </div>
          </div>
        </div>

        <div class="item-prices">
          <div class="price-block">
            <span>Preço-alvo</span>
            <strong>${formatBRL(item.targetPrice)}</strong>
          </div>
          <div class="price-block">
            <span>Melhor oferta</span>
            <strong class="${goalMet ? "text-success" : ""}">${best ? formatBRL(best.price) : "Sem ofertas"}</strong>
          </div>
          <div class="price-block">
            <span>Loja líder</span>
            <strong>${best ? escapeHtml(best.store) : "-"}</strong>
          </div>
          <div class="price-block">
            <span>Maior desconto</span>
            <strong class="${discount > 0 ? "text-accent" : ""}">${discount > 0 ? `-${discount}%` : "-"}</strong>
          </div>
          ${bestBrand ? `<div class="price-block price-block-full"><span>Melhor item</span><strong class="best-item-name text-success" title="${escapeHtml(bestFullTitle)}">${escapeHtml(bestBrand)}</strong></div>` : ""}
        </div>

        ${offersHtml}
        ${historyHtml}
      </article>`;
    }).join("");
  }

  function renderHistory() {
    const entries = state.history || [];
    if (entries.length === 0) {
      el.historyList.innerHTML = `<div class="empty-state">Nenhuma atividade registrada no histórico ainda.</div>`;
      return;
    }

    el.historyList.innerHTML = entries.map((entry) => `
      <div class="history-entry">
        <div>
          <strong>${escapeHtml(entry.action)}</strong> — ${escapeHtml(entry.itemName)}
          <div><small>${escapeHtml(entry.details || "")}</small></div>
        </div>
        <small>${escapeHtml(formatDate(entry.timestamp))}</small>
      </div>
    `).join("");
  }

  function render() {
    updateCategoryFilter();
    renderKPIs();
    renderItems();
    renderHistory();
  }

  function openItemModal(item = null) {
    document.getElementById("itemModalTitle").textContent = item ? "Editar Item" : "Novo Item";
    document.getElementById("itemId").value = item ? item.id : "";
    document.getElementById("itemName").value = item ? item.name : "";
    document.getElementById("itemCategory").value = item ? item.category || "" : "";
    document.getElementById("itemPriority").value = item ? item.priority || "Média" : "Média";
    document.getElementById("itemTargetPrice").value = item ? item.targetPrice : "";
    document.getElementById("itemStatus").value = item ? item.status || "Monitorando" : "Monitorando";
    document.getElementById("itemNotes").value = item ? item.notes || "" : "";
    el.itemModal.showModal();
  }

  function openOfferModal(itemId) {
    const item = state.items.find((i) => i.id === itemId);
    if (!item) return;
    document.getElementById("offerModalTitle").textContent = `Nova Oferta: ${item.name}`;
    document.getElementById("offerItemId").value = itemId;
    el.offerForm.reset();
    document.getElementById("offerItemId").value = itemId;
    el.offerModal.showModal();
  }

  // Eventos de abas
  document.querySelectorAll(".tab-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach((b) => b.classList.remove("active"));
      document.querySelectorAll(".tab-panel").forEach((p) => p.classList.remove("active"));
      btn.classList.add("active");
      document.getElementById(`tab-${btn.dataset.tab}`).classList.add("active");
    });
  });

  // Fechar modais
  document.querySelectorAll("[data-close-modal]").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.getElementById(btn.dataset.closeModal).close();
    });
  });

  document.getElementById("btnNewItem").addEventListener("click", () => openItemModal());

  async function fetchAndAttachOffers(item, { auto = false } = {}) {
    if (!serverAvailable || !item?.name) return 0;

    setSyncBadge(true, `Consultando lojas para "${item.name}"...`);
    try {
      const res = await fetch("/api/search", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: item.name,
          category: item.category || "",
          maxOffers: 6
        })
      });
      if (!res.ok) throw new Error("Falha na busca");

      const data = await res.json();
      const found = Array.isArray(data.offers) ? data.offers : [];
      const now = new Date().toISOString();

      item.offers = item.offers || [];
      item.priceHistory = item.priceHistory || [];

      let added = 0;
      for (const raw of found) {
        const existing = item.offers.find((o) => o.url === raw.url);
        if (existing) {
          existing.price = raw.price;
          existing.originalPrice = raw.originalPrice ?? existing.originalPrice;
          existing.foundAt = now;
        } else {
          item.offers.push({
            id: uid("offer"),
            store: raw.store,
            price: raw.price,
            originalPrice: raw.originalPrice ?? null,
            coupon: raw.coupon || "",
            cashback: raw.cashback || "",
            shipping: raw.shipping || "A calcular",
            url: raw.url,
            foundAt: now,
            notes: raw.notes || ""
          });
          added += 1;
        }
      }

      const best = getBestOffer(item);
      if (best) {
        item.priceHistory.push({
          date: now,
          store: best.store,
          price: best.price,
          note: auto ? "Busca automática ao criar item" : "Busca automática de ofertas"
        });
        if (best.price <= item.targetPrice && item.status === "Monitorando") {
          item.status = "Meta atingida";
        }
      }

      const sourcesLabel = (data.sources || []).join(", ") || "lojas";
      addHistory(
        auto ? "Busca automática" : "Ofertas atualizadas",
        item.name,
        found.length > 0
          ? `${found.length} ofertas encontradas (${sourcesLabel}); melhor: ${formatBRL(best.price)}`
          : `Nenhuma oferta exata encontrada em ${sourcesLabel}`
      );
      await saveData();
      render();
      return found.length;
    } catch {
      setSyncBadge(false, "Erro ao consultar lojas");
      return 0;
    }
  }

  // Salvar Item
  el.itemForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const id = document.getElementById("itemId").value;
    const payload = {
      name: document.getElementById("itemName").value.trim(),
      category: document.getElementById("itemCategory").value.trim() || "Outros",
      priority: document.getElementById("itemPriority").value,
      targetPrice: parseFloat(document.getElementById("itemTargetPrice").value) || 0,
      status: document.getElementById("itemStatus").value,
      notes: document.getElementById("itemNotes").value.trim()
    };

    let createdItem = null;
    if (id) {
      const idx = state.items.findIndex((i) => i.id === id);
      if (idx !== -1) {
        state.items[idx] = { ...state.items[idx], ...payload };
        addHistory("Item atualizado", payload.name, `Meta: ${formatBRL(payload.targetPrice)} | Status: ${payload.status}`);
      }
    } else {
      createdItem = {
        id: uid("item"),
        ...payload,
        offers: [],
        priceHistory: []
      };
      state.items.unshift(createdItem);
      addHistory("Item adicionado", payload.name, `Meta: ${formatBRL(payload.targetPrice)}`);
    }

    el.itemModal.close();
    await saveData();
    render();

    if (createdItem) {
      await fetchAndAttachOffers(createdItem, { auto: true });
    }
  });

  // Salvar Oferta
  el.offerForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const itemId = document.getElementById("offerItemId").value;
    const item = state.items.find((i) => i.id === itemId);
    if (!item) return;

    const price = parseFloat(document.getElementById("offerPrice").value);
    const originalPriceVal = parseFloat(document.getElementById("offerOriginalPrice").value);
    const store = document.getElementById("offerStore").value.trim();
    const now = new Date().toISOString();

    const offer = {
      id: uid("offer"),
      store,
      price,
      originalPrice: Number.isFinite(originalPriceVal) && originalPriceVal > 0 ? originalPriceVal : null,
      coupon: document.getElementById("offerCoupon").value.trim(),
      cashback: document.getElementById("offerCashback").value.trim(),
      shipping: document.getElementById("offerShipping").value.trim(),
      url: document.getElementById("offerUrl").value.trim(),
      foundAt: now,
      notes: document.getElementById("offerNotes").value.trim()
    };

    item.offers = item.offers || [];
    item.offers.push(offer);

    item.priceHistory = item.priceHistory || [];
    item.priceHistory.push({
      date: now,
      store,
      price,
      note: offer.coupon ? `Cupom ${offer.coupon}` : offer.notes || "Oferta registrada"
    });

    if (price <= item.targetPrice && item.status === "Monitorando") {
      item.status = "Meta atingida";
    }

    addHistory("Oferta registrada", item.name, `${store}: ${formatBRL(price)}`);
    el.offerModal.close();
    await saveData();
    render();
  });

  // Delegação de ações nos cards
  el.itemsList.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-action]");
    if (!btn) return;
    const { action, item: itemId, offer: offerId } = btn.dataset;
    const item = state.items.find((i) => i.id === itemId);
    if (!item) return;

    if (action === "offer-page") {
      offerPages.set(itemId, Number(btn.dataset.page) || 1);
      renderItems();
    } else if (action === "search-offers") {
      btn.disabled = true;
      await fetchAndAttachOffers(item, { auto: false });
      btn.disabled = false;
    } else if (action === "add-offer") {
      openOfferModal(itemId);
    } else if (action === "edit-item") {
      openItemModal(item);
    } else if (action === "delete-item") {
      if (!confirm(`Excluir "${item.name}"?`)) return;
      state.items = state.items.filter((i) => i.id !== itemId);
      addHistory("Item removido", item.name, "Excluído pelo usuário");
      await saveData();
      render();
    } else if (action === "delete-offer") {
      item.offers = (item.offers || []).filter((o) => o.id !== offerId);
      addHistory("Oferta removida", item.name, "Oferta excluída da comparação");
      await saveData();
      render();
    }
  });

  el.itemsList.addEventListener("change", async (e) => {
    const select = e.target.closest("[data-action='change-status']");
    if (!select) return;
    const item = state.items.find((i) => i.id === select.dataset.item);
    if (!item) return;
    item.status = select.value;
    addHistory("Status alterado", item.name, `Novo status: ${item.status}`);
    await saveData();
    render();
  });

  // Filtros
  [el.filterSearch, el.filterCategory, el.filterStatus, el.filterPriority, el.sortBy].forEach((ctrl) => {
    ctrl.addEventListener("input", () => {
      updateCategoryFilter();
      renderItems();
    });
    ctrl.addEventListener("change", () => {
      updateCategoryFilter();
      renderItems();
    });
  });

  if (el.categoryPills) {
    el.categoryPills.addEventListener("click", (e) => {
      const pill = e.target.closest("[data-cat]");
      if (!pill) return;
      el.filterCategory.value = pill.dataset.cat;
      updateCategoryFilter();
      renderItems();
    });
  }

  // Exportar / Importar / Limpar histórico
  document.getElementById("btnExport").addEventListener("click", () => {
    const blob = new Blob([JSON.stringify(state, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `blackfriday-deals-${new Date().toISOString().slice(0, 10)}.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  });

  document.getElementById("inputImport").addEventListener("change", async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const parsed = JSON.parse(await file.text());
      if (!Array.isArray(parsed.items)) throw new Error("Formato inválido");
      state = parsed;
      addHistory("Base importada", "JSON", `${state.items.length} itens carregados`);
      await saveData();
      render();
    } catch {
      alert("Arquivo JSON inválido. Verifique se possui a estrutura do Black Friday Tracker.");
    }
    e.target.value = "";
  });

  document.getElementById("btnClearHistory").addEventListener("click", async () => {
    if (!confirm("Limpar toda a linha do tempo?")) return;
    state.history = [];
    await saveData();
    renderHistory();
  });

  async function submitAuth(endpoint) {
    el.authFeedback.textContent = "Aguarde...";
    try {
      const res = await fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: el.authEmail.value.trim(),
          password: el.authPassword.value
        })
      });
      const data = await res.json();
      if (!res.ok) {
        el.authFeedback.textContent = data.error || "Falha na autenticação.";
        return;
      }
      if (data.needsConfirmation) {
        el.authFeedback.textContent = "Conta criada! Confirme seu e-mail e depois clique em Entrar.";
        return;
      }
      el.authFeedback.textContent = "";
      el.authModal.close();
      await loadData();
    } catch {
      el.authFeedback.textContent = "Erro de conexão com o servidor.";
    }
  }

  el.btnAuth.addEventListener("click", () => {
    el.authFeedback.textContent = "";
    el.authModal.showModal();
  });

  el.authForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    await submitAuth("/api/auth/login");
  });

  el.btnAuthSignup.addEventListener("click", async () => {
    await submitAuth("/api/auth/signup");
  });

  el.btnLogout.addEventListener("click", async () => {
    await fetch("/api/auth/logout", { method: "POST" });
    currentUser = null;
    state = structuredClone(FALLBACK_DATA);
    updateAuthUI();
    setSyncBadge(false, "Sessão encerrada");
    render();
    el.authModal.showModal();
  });

  loadData();
})();
