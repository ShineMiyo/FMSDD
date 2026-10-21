/* FMSDD gift boutique: item purchases stay in the shared economy and Backpack. */
(() => {
  "use strict";

  const bridge = () => window.FMSDDLifeBridge;
  const t = (key, parameters = {}) => bridge()?.uiText(key, parameters) || key;
  const esc = (value) => bridge()?.escapeHtml
    ? bridge().escapeHtml(String(value ?? ""))
    : String(value ?? "");
  const compactMoney = (value) => bridge()?.formatCompactMoney?.(Number(value) || 0, 1)
    || bridge()?.formatFullMoney?.(Number(value) || 0)
    || String(Number(value) || 0);

  const CATEGORY_ICONS = Object.freeze({
    book: ["book-open", "book"],
    fashion: ["shirt", "fashion"],
    technology: ["headphones", "technology"],
    food: ["croissant", "food"],
    sport: ["volleyball", "sport"],
    music: ["disc", "music"],
    art: ["image", "art"],
    luxury: ["watch", "luxury"],
    romance: ["heart", "romance"],
    intimate: ["flame", "intimate"],
  });
  const SKU_ICONS = Object.freeze({
    gift_book: "book-open", gift_fashion: "shirt", gift_technology: "headphones",
    gift_food: "croissant", gift_sport: "volleyball", gift_music: "disc",
    gift_art: "image", gift_luxury: "watch",
    gift_poetry: "book-open", gift_first_edition: "book", gift_silk_scarf: "shirt",
    gift_cufflinks: "circle-dot", gift_earbuds: "headphones", gift_smartwatch: "watch",
    gift_truffle: "candy", gift_tea: "cup-soda", gift_signed_jersey: "shirt",
    gift_custom_boots: "footprints", gift_vinyl: "disc", gift_concert_ticket: "ticket",
    gift_limited_print: "image", gift_hand_sketch: "pen-tool",
    gift_fountain_pen: "pen-line", gift_cashmere: "shirt",
    gift_roses: "flower-2", gift_chocolate: "candy", gift_perfume: "spray-can",
    gift_necklace: "gem",
    intimate_condoms: "shield", intimate_pills: "pill", intimate_toy: "sparkles",
    intimate_lube: "droplets", intimate_dice: "dices", intimate_blindfold: "eye-off",
    wedding_ring: "gem",
  });
  const CATEGORY_ORDER = Object.freeze([
    "book", "fashion", "technology", "food", "sport", "music", "art", "luxury",
    "romance", "intimate",
  ]);
  const state = {category: "all", quantities: Object.create(null), cart: Object.create(null), busySku: "", bound: false};

  function pageRoot() { return document.getElementById("page-gift-shop"); }
  function catalog() {
    return (bridge()?.getState?.()?.economy?.catalog || [])
      .filter((item) => ["gift", "adult", "ring"].includes(String(item.family || "")) && item.gift_category)
      .sort((left, right) => (
        CATEGORY_ORDER.indexOf(String(left.gift_category || ""))
        - CATEGORY_ORDER.indexOf(String(right.gift_category || ""))
      ) || Number(left.price || 0) - Number(right.price || 0));
  }

  function localizedItem(item, field) {
    const key = `item.${String(item.sku || "")}.${field}`;
    const translated = t(key);
    return translated && translated !== key ? translated : String(item[field] || "");
  }

  function categoryLabel(category) {
    return category === "all"
      ? t("gift_shop.all")
      : t(`life.interactions.gift_category.${category}`);
  }

  function quantityFor(sku) {
    return Math.max(1, Math.min(99, Number(state.quantities[sku] || 1)));
  }

  function renderCategories() {
    const root = document.getElementById("gift-shop-categories");
    if (!root) return;
    root.innerHTML = ["all", ...CATEGORY_ORDER].map((category) => {
      const active = state.category === category;
      const icon = category === "all" ? "layout-grid" : CATEGORY_ICONS[category]?.[0] || "gift";
      return `<button type="button" class="gift-shop-category ${active ? "active" : ""}" data-gift-category="${category}" role="tab" aria-selected="${active}"><i data-lucide="${icon}"></i><span>${esc(categoryLabel(category))}</span></button>`;
    }).join("");
  }

  function cardMarkup(item) {
    const sku = String(item.sku || "");
    const category = String(item.gift_category || "luxury");
    const [fallbackIcon, artworkCategory] = CATEGORY_ICONS[category] || ["gift", "luxury"];
    const icon = SKU_ICONS[sku] || fallbackIcon;
    const quantity = quantityFor(sku);
    const total = Number(item.price || 0) * quantity;
    const economy = bridge()?.getState?.()?.economy || {};
    const affordable = total <= Number(economy.total_balance || 0);
    const busy = state.busySku === sku;
    return `<article class="gift-shop-card ${busy ? "is-busy" : ""}" data-gift-sku="${esc(sku)}">
      <div class="gift-shop-art gift-art-${artworkCategory}"><i data-lucide="${icon}"></i><span>${esc(categoryLabel(category))}</span></div>
      <div class="gift-shop-copy"><span class="gift-shop-kicker">${esc(t("gift_shop.item_kicker"))}</span><h2>${esc(localizedItem(item, "name"))}</h2><p>${esc(localizedItem(item, "description"))}</p></div>
      <div class="gift-shop-card-foot">
        <div class="gift-shop-price"><small>${esc(t("gift_shop.unit_price"))}</small><strong>${esc(compactMoney(item.price))}</strong></div>
        <div class="gift-shop-quantity" data-gift-quantity-control="${esc(sku)}"><button type="button" data-gift-quantity="-1" aria-label="${esc(t("gift_shop.decrease"))}" ${quantity <= 1 || busy ? "disabled" : ""}><i data-lucide="minus"></i></button><input type="text" inputmode="numeric" pattern="[0-9]*" value="${quantity}" data-gift-quantity-input aria-label="${esc(t("gift_shop.quantity", {name: localizedItem(item, "name")}))}" ${busy ? "disabled" : ""}><button type="button" data-gift-quantity="1" aria-label="${esc(t("gift_shop.increase"))}" ${quantity >= 99 || busy ? "disabled" : ""}><i data-lucide="plus"></i></button></div>
        <button type="button" class="gift-shop-buy" data-gift-add="${esc(sku)}" ${busy ? "disabled" : ""}><i data-lucide="shopping-cart"></i><span>${esc(t("gift_shop.add_to_cart"))}</span></button>
      </div>
      <small class="gift-shop-storage"><i data-lucide="package-open"></i>${esc(t("gift_shop.storage_note"))}</small>
    </article>`;
  }

  function render() {
    const root = pageRoot();
    const content = document.getElementById("gift-shop-content");
    if (!root || !content) return;
    const items = catalog().filter((item) => state.category === "all" || String(item.gift_category || "") === state.category);
    renderCategories();
    content.innerHTML = items.length
      ? items.map(cardMarkup).join("")
      : `<div class="gift-shop-empty"><i data-lucide="gift"></i><strong>${esc(t("gift_shop.empty"))}</strong><span>${esc(t("gift_shop.empty_detail"))}</span></div>`;
    bridge()?.renderFundingSummary?.("#gift-shop-balance");
    root.setAttribute("aria-busy", state.busySku ? "true" : "false");
    renderCart();
    bridge()?.renderIcons?.(root);
  }

  function setQuantity(sku, value) {
    const parsed = Number.parseInt(String(value || "").replace(/\D/g, ""), 10);
    state.quantities[sku] = Math.max(1, Math.min(99, Number.isFinite(parsed) ? parsed : 1));
    render();
  }

  function cartLines() {
    const bySku = new Map(catalog().map((item) => [String(item.sku || ""), item]));
    return Object.entries(state.cart)
      .filter(([sku, quantity]) => Number(quantity) > 0 && bySku.has(sku))
      .map(([sku, quantity]) => ({item: bySku.get(sku), sku, quantity: Number(quantity)}));
  }

  function renderCart() {
    const root = document.getElementById("gift-shop-cart");
    if (!root) return;
    const lines = cartLines();
    const count = lines.reduce((sum, line) => sum + line.quantity, 0);
    const total = lines.reduce((sum, line) => sum + Number(line.item.price || 0) * line.quantity, 0);
    if (!lines.length) {
      root.innerHTML = "";
      root.hidden = true;
      return;
    }
    root.hidden = false;
    root.innerHTML = `<div class="gift-shop-cart-head"><div><small>${esc(t("shop.cart.title"))}</small><strong>${esc(t("shop.cart.items", {count}))}</strong></div><b>${esc(compactMoney(total))}</b><button type="button" class="gift-shop-cart-checkout" data-gift-checkout ${state.busySku ? "disabled" : ""}><i data-lucide="${state.busySku ? "loader-circle" : "shopping-bag"}"></i>${esc(state.busySku ? t("gift_shop.buying") : t("shop.cart.confirm"))}</button></div><div class="gift-shop-cart-lines">${lines.map(({item, sku, quantity}) => `<div class="gift-shop-cart-line"><span>${esc(localizedItem(item, "name"))}</span><div class="gift-shop-cart-quantity"><button type="button" data-gift-cart-delta="-1" data-sku="${esc(sku)}" ${quantity <= 1 ? "disabled" : ""}>−</button><b>${quantity}</b><button type="button" data-gift-cart-delta="1" data-sku="${esc(sku)}" ${quantity >= 99 ? "disabled" : ""}>＋</button></div><strong>${esc(compactMoney(Number(item.price || 0) * quantity))}</strong><button type="button" class="gift-shop-cart-remove" data-gift-cart-remove="${esc(sku)}" aria-label="${esc(t("shop.delete_label", {name: localizedItem(item, "name")}))}"><i data-lucide="trash-2"></i></button></div>`).join("")}</div>`;
    bridge()?.renderIcons?.(root);
  }

  function addToCart(sku) {
    const item = catalog().find((row) => String(row.sku || "") === sku);
    if (!item) return;
    state.cart[sku] = Math.max(0, Math.min(99, Number(state.cart[sku] || 0) + quantityFor(sku)));
    state.quantities[sku] = 1;
    render();
    bridge()?.toast?.(t("gift_shop.added_to_cart", {name: localizedItem(item, "name")}));
  }

  async function checkout() {
    if (state.busySku) return;
    const lines = cartLines();
    if (!lines.length) return;
    const items = lines.map((line) => ({sku: line.sku, quantity: line.quantity}));
    const total = lines.reduce((sum, line) => sum + Number(line.item.price || 0) * line.quantity, 0);
    const accepted = await bridge()?.fmoddConfirm?.(
      t("gift_shop.confirm_body", {name: t("shop.cart.title"), quantity: lines.reduce((sum, line) => sum + line.quantity, 0), total: compactMoney(total)}),
      t("shop.cart.confirm"),
      t("shop.cart.title"),
    );
    if (!accepted) return;
    state.busySku = "checkout";
    render();
    try {
      const response = await bridge().request("/api/shop/buy-batch", {
        method: "POST", headers: {"Content-Type": "application/json"},
        body: JSON.stringify({items, free_purchase: false}),
      });
      const economy = response?.state_patch?.economy;
      if (economy) bridge().applyEconomy(economy);
      state.cart = Object.create(null);
      bridge()?.toast?.(t("gift_shop.purchased", {name: t("shop.cart.title"), quantity: items.reduce((sum, row) => sum + row.quantity, 0)}));
    } catch (error) {
      bridge()?.toast?.(String(error?.message || error || t("gift_shop.failed")));
    } finally {
      state.busySku = "";
      render();
    }
  }

  function handleClick(event) {
    if (!pageRoot()?.contains(event.target)) return;
    const category = event.target.closest("[data-gift-category]");
    if (category) {
      state.category = String(category.dataset.giftCategory || "all");
      render();
      return;
    }
    const delta = event.target.closest("[data-gift-quantity]");
    if (delta) {
      const sku = String(delta.closest("[data-gift-quantity-control]")?.dataset.giftQuantityControl || "");
      setQuantity(sku, quantityFor(sku) + Number(delta.dataset.giftQuantity || 0));
      return;
    }
    const addButton = event.target.closest("[data-gift-add]");
    if (addButton && !addButton.disabled) {
      addToCart(String(addButton.dataset.giftAdd || ""));
      return;
    }
    const cartDelta = event.target.closest("[data-gift-cart-delta]");
    if (cartDelta) {
      const sku = String(cartDelta.dataset.sku || "");
      const next = Number(state.cart[sku] || 0) + Number(cartDelta.dataset.giftCartDelta || 0);
      if (next > 0) state.cart[sku] = Math.min(99, next);
      else delete state.cart[sku];
      render();
      return;
    }
    const remove = event.target.closest("[data-gift-cart-remove]");
    if (remove) {
      delete state.cart[String(remove.dataset.giftCartRemove || "")];
      render();
      return;
    }
    const checkoutButton = event.target.closest("[data-gift-checkout]");
    if (checkoutButton && !checkoutButton.disabled) void checkout();
  }

  function handleChange(event) {
    const input = event.target.closest?.("[data-gift-quantity-input]");
    if (!input || !pageRoot()?.contains(input)) return;
    const sku = String(input.closest("[data-gift-quantity-control]")?.dataset.giftQuantityControl || "");
    setQuantity(sku, input.value);
  }

  function bind() {
    if (state.bound) return;
    state.bound = true;
    document.addEventListener("click", handleClick);
    document.addEventListener("change", handleChange);
    document.addEventListener("fmodd:localechange", () => {
      if (!pageRoot()?.hidden) render();
    });
    document.addEventListener("fmodd:settings-changed", () => {
      if (!pageRoot()?.hidden) render();
    });
  }

  window.FMSDDGiftShop = Object.freeze({
    render() {
      bind();
      render();
    },
  });
})();
