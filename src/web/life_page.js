/* FMSDD life system front end. The server owns every balance and asset value. */
(() => {
  "use strict";

  const TILE_SIZE = 256;
  const MIN_ZOOM = 3;
  const MAX_ZOOM = 15;
  const TRADE_MIN_ZOOM = 13;
  const TRADE_MAX_ZOOM = 15;
  const MAP_PROVIDER_KEY = "fmsdd-life-basemap-v4";
  const DEALER_PAGE_SIZE = 24;
  const VEHICLE_IMAGE_CACHE_NAME = "fmsdd-life-car-images-v1";
  const VEHICLE_IMAGE_CONCURRENCY = 5;
  const VEHICLE_IMAGE_WARM_CONCURRENCY = 2;
  const TRANSPARENT_IMAGE = "data:image/gif;base64,R0lGODlhAQABAAD/ACwAAAAAAQABAAACADs=";
  const bridge = () => window.FMSDDLifeBridge;
  const t = (key, parameters = {}) => bridge()?.uiText(key, parameters) || key;
  const esc = (value) => bridge()?.escapeHtml(String(value ?? "")) || String(value ?? "");
  const money = (value) => bridge()?.formatMoney(Number(value) || 0) || String(Number(value) || 0);
  const fullMoney = (value) => bridge()?.formatFullMoney(Number(value) || 0) || String(Number(value) || 0);
  const percent = (value, digits = 0) => `${(Number(value || 0) * 100).toFixed(digits)}%`;
  const VEHICLE_CLASS_KEYS = Object.freeze(["D", "C", "B", "A", "S1", "S2"]);
  const LIFE_DIALOG_IDS = Object.freeze([
    "life-collection-dialog",
    "life-storage-dialog",
    "life-gacha-history-dialog",
    "life-gacha-catalog-dialog",
    "life-map-bulk-dialog",
    "life-garage-bulk-dialog",
  ]);
  const vehicleImageObjectUrls = new Map();
  const vehicleImageCacheJobs = new Map();
  const vehicleImageResolveJobs = new Map();
  const vehicleImageQueue = [];
  let vehicleImageActive = 0;
  let vehicleImageObserver = null;
  let vehicleImageWarmStarted = false;
  let lifeRequestPromise = null;
  let lifeRequestFlags = {packs:false, catalog:false};
  let lifeRequestScope = "";
  let lifeRequestGeneration = 0;
  let lifePreloadPromise = null;
  let lifePreloadAnnounced = false;

  function vehicleClassKey(value) {
    const key = String(value || "").trim().toUpperCase();
    return VEHICLE_CLASS_KEYS.includes(key) ? key : "D";
  }

  function vehicleClassBadge(value, inline = false) {
    const key = vehicleClassKey(value);
    return `<span class="life-class-badge life-class-${key.toLowerCase()}${inline ? " is-inline" : ""}" data-vehicle-class="${esc(key)}">${esc(key)}</span>`;
  }

  function vehicleImageTag(image, name) {
    return `<img src="${TRANSPARENT_IMAGE}" data-life-vehicle-image="${esc(image)}" alt="${esc(name)}" loading="lazy" decoding="async">`;
  }

  function normalizedVehicleImageUrl(value) {
    try {
      return new URL(String(value || ""), window.location.href).href;
    } catch (_error) {
      return String(value || "");
    }
  }

  async function cacheVehicleImage(image) {
    const url = normalizedVehicleImageUrl(image);
    if (!url || !("caches" in window)) return false;
    if (vehicleImageCacheJobs.has(url)) return vehicleImageCacheJobs.get(url);
    const job = (async () => {
      const cache = await caches.open(VEHICLE_IMAGE_CACHE_NAME);
      let response = await cache.match(url);
      if (!response) {
        response = await fetch(url, {cache:"force-cache", credentials:"same-origin"});
        if (!response.ok) throw new Error(`Vehicle image ${response.status}`);
        await cache.put(url, response.clone());
      }
      return true;
    })().catch(() => false).finally(() => vehicleImageCacheJobs.delete(url));
    vehicleImageCacheJobs.set(url, job);
    return job;
  }

  async function resolveVehicleImage(image) {
    const url = normalizedVehicleImageUrl(image);
    if (!url) return "";
    if (vehicleImageObjectUrls.has(url)) return vehicleImageObjectUrls.get(url);
    if (vehicleImageResolveJobs.has(url)) return vehicleImageResolveJobs.get(url);
    const job = (async () => {
      const cached = await cacheVehicleImage(url);
      if (cached && "caches" in window) {
        const response = await (await caches.open(VEHICLE_IMAGE_CACHE_NAME)).match(url);
        if (response) {
          const objectUrl = URL.createObjectURL(await response.blob());
          vehicleImageObjectUrls.set(url, objectUrl);
          return objectUrl;
        }
      }
      return url;
    })().finally(() => vehicleImageResolveJobs.delete(url));
    vehicleImageResolveJobs.set(url, job);
    return job;
  }

  async function hydrateVehicleImage(image) {
    const source = image?.dataset?.lifeVehicleImage || "";
    if (!source || image.dataset.lifeVehicleLoaded === "true") return;
    image.dataset.lifeVehicleLoaded = "true";
    const resolved = await resolveVehicleImage(source);
    if (!image.isConnected || image.dataset.lifeVehicleImage !== source) return;
    image.src = resolved || source;
  }

  function pumpVehicleImageQueue() {
    while (vehicleImageActive < VEHICLE_IMAGE_CONCURRENCY && vehicleImageQueue.length) {
      const image = vehicleImageQueue.shift();
      vehicleImageActive += 1;
      void hydrateVehicleImage(image).finally(() => {
        vehicleImageActive -= 1;
        pumpVehicleImageQueue();
      });
    }
  }

  function queueVehicleImage(image) {
    if (!image || image.dataset.lifeVehicleQueued === "true") return;
    image.dataset.lifeVehicleQueued = "true";
    vehicleImageQueue.push(image);
    pumpVehicleImageQueue();
  }

  function scheduleVehicleImageHydration(root = document) {
    if (!root?.querySelectorAll) return;
    const images = [...root.querySelectorAll("img[data-life-vehicle-image]")]
      .filter((image) => image.dataset.lifeVehicleLoaded !== "true");
    if (!images.length) return;
    if (typeof IntersectionObserver !== "function") {
      images.forEach(queueVehicleImage);
      return;
    }
    if (!vehicleImageObserver) {
      vehicleImageObserver = new IntersectionObserver((entries, observer) => {
        for (const entry of entries) {
          if (!entry.isIntersecting) continue;
          observer.unobserve(entry.target);
          queueVehicleImage(entry.target);
        }
      }, {rootMargin:"260px 0px", threshold:0.01});
    }
    images.forEach((image) => vehicleImageObserver.observe(image));
  }

  function warmVehicleImageCache() {
    if (vehicleImageWarmStarted || !state.catalog || !("caches" in window)) return;
    vehicleImageWarmStarted = true;
    const urls = [...new Set(
      (state.catalog?.cars?.cars || []).map((car) => String(car.image || "")).filter(Boolean),
    )];
    const start = () => {
      let cursor = 0;
      const worker = async () => {
        while (cursor < urls.length) {
          if (state.busy) {
            await new Promise((resolve) => setTimeout(resolve, 240));
            continue;
          }
          await cacheVehicleImage(urls[cursor++]);
        }
      };
      void Promise.all(Array.from({length:VEHICLE_IMAGE_WARM_CONCURRENCY}, worker));
    };
    if (typeof requestIdleCallback === "function") requestIdleCallback(start, {timeout:10000});
    else setTimeout(start, 5000);
  }

  const state = {
    page: "",
    scopeId: "",
    data: null,
    catalog: null,
    packs: null,
    loading: false,
    error: "",
    loadedAt: 0,
    busy: "",
    lastGacha: null,
    assetFilter: "all",
    assetExpanded: new Set(), assetExpandAll: null,
    map: {
      countryCode: "", cityId: "", zoom: 13, center: null, kind: "all", parcelId: "", nodeId: "",
      provider: storedMapProvider(), fallbackProvider: "", tileError: false, leaseDays: 90,
      dragging: null, drawFrame: 0,
    },
    dealer: {
      query: "", manufacturer: "all", carClass: "all", rarity: "all",
      page: 0, garageId: "",
    },
    garage: {selectedId: ""},
    garageBulk: {
      selected: new Set(), targetId: "", searchTimer: null,
      query: "", manufacturer: "all", carClass: "all", rarity: "all",
    },
    mapBulk: {kind: "all"},
    storage: {
      selected: new Set(), targetId: "",
      query: "", manufacturer: "all", carClass: "all", rarity: "all", searchTimer: null,
    },
    collection: {
      tab: "overview", query: "", manufacturer: "all",
      carClass: "all", rarity: "all", owned: "all",
    },
    gacha: {garageId: "", multipliers: {}},
    gachaHistoryTier: "",
    gachaCatalog: {tier: "", query: "", carClass: "all", rarity: "all"},
  };

  const pageRoots = {
    "life-map": "life-map-content",
    "life-properties": "life-properties-content",
    "life-garage": "life-garage-content",
    "life-dealer": "life-dealer-content",
    "life-gacha": "life-gacha-content",
  };

  function pageRoot(page = state.page) {
    const id = pageRoots[page];
    return id ? document.getElementById(id) : null;
  }

  function anyLifeDialogOpen() {
    return LIFE_DIALOG_IDS.some((dialogId) => document.getElementById(dialogId)?.open);
  }

  function kindLabel(kind) {
    return t(`life.kind.${kind}`);
  }

  function rarityLabel(rarity) {
    const key = `life.rarity.${String(rarity || "").toLowerCase()}`;
    const value = t(key);
    return value === key ? String(rarity || "—") : value;
  }

  function garageLabel(value) {
    const garage = typeof value === "object" ? value : findGarage(value);
    const locale = window.FMODDI18n?.locale || "en-GB";
    if (garage) {
      const named = locale === "zh-CN" || locale === "zh-TW"
        ? garage.name_zh || garage.name_en
        : garage.name_en || garage.name_zh;
      if (named) return String(named);
      const kind = String(garage.kind || garage.category || "");
      const translated = t(`life.garage.${kind}`);
      return translated === `life.garage.${kind}` ? String(garage.id || "—") : translated;
    }
    const id = String(value || "");
    const translated = t(`life.garage.${id}`);
    return translated === `life.garage.${id}` ? (id || "—") : translated;
  }

  function garageCategory(garage) {
    return String(garage?.category || (garage?.kind === "club" ? "club" : "standalone"));
  }

  function garageCategoryLabel(garage) {
    return t(`life.garage.group_${garageCategory(garage)}`);
  }

  function garageIcon(garage) {
    const category = garageCategory(garage);
    if (category === "club") return "badge-check";
    if (category === "storage") return "archive";
    if (category === "property") return "house";
    if (category === "legacy") return "history";
    return "warehouse";
  }

  function garageLocation(garage) {
    const locale = window.FMODDI18n?.locale || "en-GB";
    const cityId = String(garage?.city_id || "");
    const city = cityPacks().find((row) => String(row.city_id) === cityId);
    const cityLabel = city ? cityName(city) : cityId;
    const district = locale === "zh-CN" || locale === "zh-TW"
      ? garage?.district_name_zh || garage?.district_name_en
      : garage?.district_name_en || garage?.district_name_zh;
    return [cityLabel, district].filter(Boolean).join(" · ");
  }

  function cityName(city) {
    const locale = window.FMODDI18n?.locale || "en-GB";
    return locale === "zh-CN" || locale === "zh-TW"
      ? String(city?.city_name_zh || city?.name_zh || city?.city_name_en || city?.name_en || city?.city_id || "")
      : String(city?.city_name_en || city?.name_en || city?.city_name_zh || city?.name_zh || city?.city_id || "");
  }

  function countryName(code) {
    const target = String(code || "").toUpperCase();
    const city = cityPacks().find((row) => String(row.country || "").toUpperCase() === target);
    const locale = window.FMODDI18n?.locale || "en-GB";
    return locale === "zh-CN" || locale === "zh-TW"
      ? String(city?.country_name_zh || city?.country_name_en || target)
      : String(city?.country_name_en || city?.country_name_zh || target);
  }

  function mapCountries() {
    const seen = new Set();
    const rows = [];
    for (const city of cityPacks()) {
      const code = String(city.country || "CN").toUpperCase();
      if (seen.has(code)) continue;
      seen.add(code);
      rows.push({code, name:countryName(code)});
    }
    return rows;
  }

  function mapCountryCities(code = state.map.countryCode) {
    const target = String(code || "").toUpperCase();
    return cityPacks().filter((row) => String(row.country || "CN").toUpperCase() === target);
  }

  function propertyName(record) {
    const locale = window.FMODDI18n?.locale || "en-GB";
    return locale === "zh-CN" || locale === "zh-TW"
      ? String(record?.name_zh || record?.name_en || record?.id || "")
      : String(record?.name_en || record?.name_zh || record?.id || "");
  }

  function districtName(record) {
    const locale = window.FMODDI18n?.locale || "en-GB";
    return locale === "zh-CN" || locale === "zh-TW"
      ? String(record?.district_name_zh || record?.district_name_en || "")
      : String(record?.district_name_en || record?.district_name_zh || "");
  }

  function dayDate(ordinal) {
    const value = Number(ordinal || 0);
    if (!value) return "—";
    const date = new Date(Date.UTC(2000, 0, 1));
    date.setUTCFullYear(1, 0, 1);
    date.setUTCDate(date.getUTCDate() + value - 1);
    return date.toISOString().slice(0, 10);
  }

  function formatBytes(value) {
    const bytes = Number(value || 0);
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  }

  function storedMapProvider() {
    try {
      const stored = localStorage.getItem(MAP_PROVIDER_KEY);
      return ["auto", "amap", "bing", "osm"].includes(stored) ? stored : "auto";
    } catch (_error) {
      return "auto";
    }
  }

  function saveMapProvider(provider) {
    try { localStorage.setItem(MAP_PROVIDER_KEY, provider); } catch (_error) { /* storage may be unavailable */ }
  }

  function mapLayerForZoom(value) {
    const zoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, Number(value) || MIN_ZOOM));
    if (zoom >= TRADE_MIN_ZOOM) return "parcel";
    if (zoom >= 10) return "city";
    if (zoom >= 6) return "country";
    return "world";
  }

  function currentMapLayer() {
    return mapLayerForZoom(state.map.zoom);
  }

  function mapLayerZoomRange(layer) {
    if (layer === "world") return [3, 5];
    if (layer === "country") return [6, 9];
    if (layer === "city") return [10, 12];
    return [TRADE_MIN_ZOOM, TRADE_MAX_ZOOM];
  }

  function canTradeMap() {
    const zoom = Number(state.map.zoom || 0);
    return currentMapLayer() === "parcel" && zoom >= TRADE_MIN_ZOOM && zoom <= TRADE_MAX_ZOOM;
  }

  function mapLayerLabel(layer) {
    return t(`life.map.layer_${layer}`);
  }

  function mapLayerSummary(layer) {
    if (layer === "parcel") {
      const city = selectedCity();
      return city ? {
        layer, installed: Boolean(city.installed), size_bytes: Number(city.size_bytes || 0),
        parcels: Number(city.parcels || 0),
      } : null;
    }
    if (layer === "city") return state.packs?.layers?.cities?.[state.map.cityId] || null;
    if (layer === "country") {
      return state.packs?.layers?.countries?.[state.map.countryCode]
        || (state.map.countryCode === "CN" ? state.packs?.layers?.country : null) || null;
    }
    return state.packs?.layers?.[layer] || null;
  }

  function aggregateNodes(layer = currentMapLayer()) {
    const aggregates = state.packs?.aggregates || {};
    if (layer === "world") return Array.isArray(aggregates.world) ? aggregates.world : [];
    if (layer === "country") {
      const rows = aggregates.countries?.[state.map.countryCode]
        || (state.map.countryCode === "CN" ? aggregates.country : null);
      return Array.isArray(rows) ? rows : [];
    }
    if (layer === "city") {
      return Array.isArray(aggregates.cities?.[state.map.cityId]) ? aggregates.cities[state.map.cityId] : [];
    }
    return [];
  }

  function aggregateName(node) {
    const locale = window.FMODDI18n?.locale || "en-GB";
    return locale === "zh-CN" || locale === "zh-TW"
      ? String(node?.name_zh || node?.name_en || node?.id || "")
      : String(node?.name_en || node?.name_zh || node?.id || "");
  }

  function aggregateTotals(nodes) {
    return (Array.isArray(nodes) ? nodes : []).reduce((total, node) => ({
      count: total.count + Number(node.asset_count || 0),
      value: total.value + Number(node.asset_value || 0),
    }), {count:0, value:0});
  }

  function bingQuadkey(x, y, zoom) {
    let key = "";
    for (let level = Number(zoom); level > 0; level -= 1) {
      let digit = 0;
      const mask = 1 << (level - 1);
      if ((x & mask) !== 0) digit += 1;
      if ((y & mask) !== 0) digit += 2;
      key += String(digit);
    }
    return key;
  }

  function mapTileUrl(provider, zoom, x, y) {
    if (provider === "amap") {
      const subdomain = ((Number(x) + Number(y)) % 4) + 1;
      return `https://webrd0${subdomain}.is.autonavi.com/appmaptile?lang=zh_cn&size=1&scale=1&style=8&x=${x}&y=${y}&z=${zoom}`;
    }
    if (provider === "bing") {
      const subdomain = ((Number(x) + Number(y)) % 4);
      return `https://ecn.t${subdomain}.tiles.virtualearth.net/tiles/r${bingQuadkey(Number(x), Number(y), Number(zoom))}?g=1`;
    }
    return `https://tile.openstreetmap.org/${zoom}/${x}/${y}.png`;
  }

  function outOfChina(lat, lng) {
    return lng < 72.004 || lng > 137.8347 || lat < 0.8293 || lat > 55.8271;
  }

  function wgs84ToGcj02(latValue, lngValue) {
    const lat = Number(latValue);
    const lng = Number(lngValue);
    if (!Number.isFinite(lat) || !Number.isFinite(lng) || outOfChina(lat, lng)) return {lat, lng};
    const a = 6378245.0;
    const ee = 0.00669342162296594323;
    const transformLat = (x, y) => {
      let result = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * Math.sqrt(Math.abs(x));
      result += (20.0 * Math.sin(6.0 * x * Math.PI) + 20.0 * Math.sin(2.0 * x * Math.PI)) * 2.0 / 3.0;
      result += (20.0 * Math.sin(y * Math.PI) + 40.0 * Math.sin(y / 3.0 * Math.PI)) * 2.0 / 3.0;
      result += (160.0 * Math.sin(y / 12.0 * Math.PI) + 320 * Math.sin(y * Math.PI / 30.0)) * 2.0 / 3.0;
      return result;
    };
    const transformLng = (x, y) => {
      let result = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * Math.sqrt(Math.abs(x));
      result += (20.0 * Math.sin(6.0 * x * Math.PI) + 20.0 * Math.sin(2.0 * x * Math.PI)) * 2.0 / 3.0;
      result += (20.0 * Math.sin(x * Math.PI) + 40.0 * Math.sin(x / 3.0 * Math.PI)) * 2.0 / 3.0;
      result += (150.0 * Math.sin(x / 12.0 * Math.PI) + 300.0 * Math.sin(x / 30.0 * Math.PI)) * 2.0 / 3.0;
      return result;
    };
    let dLat = transformLat(lng - 105.0, lat - 35.0);
    let dLng = transformLng(lng - 105.0, lat - 35.0);
    const radLat = lat / 180.0 * Math.PI;
    let magic = Math.sin(radLat);
    magic = 1 - ee * magic * magic;
    const sqrtMagic = Math.sqrt(magic);
    dLat = (dLat * 180.0) / ((a * (1 - ee)) / (magic * sqrtMagic) * Math.PI);
    dLng = (dLng * 180.0) / (a / sqrtMagic * Math.cos(radLat) * Math.PI);
    return {lat: lat + dLat, lng: lng + dLng};
  }

  function gcj02ToWgs84(latValue, lngValue) {
    const lat = Number(latValue);
    const lng = Number(lngValue);
    if (!Number.isFinite(lat) || !Number.isFinite(lng) || outOfChina(lat, lng)) return {lat, lng};
    let estimate = {lat, lng};
    for (let index = 0; index < 4; index += 1) {
      const converted = wgs84ToGcj02(estimate.lat, estimate.lng);
      estimate = {
        lat: estimate.lat + (lat - converted.lat),
        lng: estimate.lng + (lng - converted.lng),
      };
    }
    return estimate;
  }

  function providerCoordinate(lat, lng) {
    const provider = effectiveMapProvider();
    return provider === "amap" || provider === "bing"
      ? wgs84ToGcj02(lat, lng)
      : {lat:Number(lat), lng:Number(lng)};
  }

  function defaultGarageId() {
    const garages = state.data?.garages || [];
    return String(
      garages.find((garage) => Number(garage.free || 0) > 0)?.id
      || garages[0]?.id || "club",
    );
  }

  function syncGarageSelections() {
    const valid = new Set((state.data?.garages || []).map((garage) => String(garage.id)));
    if (!valid.has(state.dealer.garageId)) state.dealer.garageId = defaultGarageId();
    if (!valid.has(state.garage.selectedId)) {
      state.garage.selectedId = String(
        (state.data?.garages || []).find((garage) => garageCategory(garage) === "club")?.id
        || defaultGarageId(),
      );
    }
    if (!valid.has(state.gacha.garageId)) state.gacha.garageId = defaultGarageId();
  }

  function loadingMarkup() {
    return `<div class="life-state-card" role="status"><span class="spinner"></span><strong>${esc(t("life.loading"))}</strong></div>`;
  }

  function errorMarkup(message) {
    return `<div class="life-state-card life-error-card" role="alert"><i data-lucide="triangle-alert"></i><strong>${esc(t("life.error"))}</strong><p>${esc(message || "")}</p><button type="button" class="life-primary" data-life-action="refresh">${esc(t("world.refresh"))}</button></div>`;
  }

  function emptyMarkup(message, icon = "inbox") {
    return `<div class="life-empty-state"><i data-lucide="${icon}"></i><p>${esc(message || t("life.empty"))}</p></div>`;
  }

  function paintBalance() {
    const target = state.page ? `#${state.page}-balance` : "";
    if (target && document.querySelector(target)) bridge()?.renderFundingSummary(target);
  }

  function availableLifeFunds() {
    const economy = bridge()?.getState?.()?.economy || {};
    return Math.max(0, Number(economy.bank_balance || 0))
      + Math.max(0, Number(economy.casino_balance || 0));
  }

  async function requestJSON(path) {
    const response = await bridge().request(path);
    return response;
  }

  function applyLifeResponse(response) {
    if (response?.life) state.data = response.life;
    else if (response?.life_patch) mergeGachaLifePatch(response.life_patch, response);
    else if (response?.ready && Array.isArray(response.properties)) state.data = response;
    if (Array.isArray(response?.records)) {
      const fallbackValue = response.records.reduce(
        (sum, car) => sum + Number(car.value || car.base_price || 0),
        0,
      );
      state.lastGacha = {
        records: response.records,
        draw: response.draw || null,
        totalValue: Number(response.total_value ?? fallbackValue),
      };
    }
    if (response?.economy) bridge()?.applyEconomy(response.economy);
    if (response?.collection_warning) bridge()?.toast(response.collection_warning);
    syncGarageSelections();
    paintCollectionButton();
  }

  function mergeGachaLifePatch(patch, response) {
    if (!patch || !state.data) return false;
    const data = state.data;
    const added = Array.isArray(patch.vehicles_added) ? patch.vehicles_added : [];
    if (added.length) {
      const byId = new Map((data.vehicles || []).map((vehicle) => [String(vehicle.id), vehicle]));
      for (const vehicle of added) byId.set(String(vehicle.id), vehicle);
      data.vehicles = [...byId.values()].sort((left, right) => (
        String(left.garage_id || "").localeCompare(String(right.garage_id || ""))
          || String(left.name || "").localeCompare(String(right.name || ""))
      ));
      const addedValue = Number(patch.vehicles_added_value ?? added.reduce(
        (sum, vehicle) => sum + Number(vehicle.market_value || vehicle.value || 0), 0,
      ));
      const totals = {...(data.totals || {})};
      totals.vehicles = Number(totals.vehicles || 0) + added.length;
      totals.vehicle_value = Number(totals.vehicle_value || 0) + addedValue;
      totals.net_worth = Number(totals.net_worth || 0) + addedValue;
      data.totals = totals;
    }
    if (Array.isArray(patch.garages)) data.garages = patch.garages;
    if (patch.garage_summary) data.garage_summary = patch.garage_summary;
    if (patch.storage_rent) data.storage_rent = patch.storage_rent;
    if (patch.collection) data.collection = patch.collection;
    if (Array.isArray(patch.gacha_status) && Array.isArray(data.gacha_tiers)) {
      const byId = new Map(data.gacha_tiers.map((tier) => [String(tier.id), tier]));
      for (const status of patch.gacha_status) {
        const tier = byId.get(String(status.id));
        if (tier) Object.assign(tier, status);
      }
    }
    const tierId = String(response?.draw?.tier || "");
    const tier = (data.gacha_tiers || []).find((row) => String(row.id) === tierId);
    if (tier && Array.isArray(response?.draw?.history)) {
      tier.history = [...(tier.history || []), ...response.draw.history];
      tier.history_count = tier.history.length;
    }
    syncGarageSelections();
    paintCollectionButton();
    paintStorageButton();
    return true;
  }

  function currentLifeScope() {
    return String(bridge()?.getState?.()?.data_scope_id || "");
  }

  function currentLifeGameDate() {
    return String(bridge()?.getState?.()?.game_clock?.date || "");
  }

  function syncLifeScope() {
    const scope = currentLifeScope();
    if (scope === state.scopeId) return false;
    state.scopeId = scope;
    lifeRequestGeneration += 1;
    lifeRequestPromise = null;
    lifeRequestFlags = {packs:false, catalog:false};
    lifeRequestScope = "";
    lifePreloadPromise = null;
    lifePreloadAnnounced = false;
    state.data = null;
    state.packs = null;
    state.loading = false;
    state.error = "";
    state.loadedAt = 0;
    state.lastGacha = null;
    state.storage.selected.clear();
    state.storage.targetId = "";
    clearTimeout(state.storage.searchTimer);
    state.storage.searchTimer = null;
    state.storage.query = "";
    state.storage.manufacturer = "all";
    state.storage.carClass = "all";
    state.storage.rarity = "all";
    state.gachaCatalog = {tier:"", query:"", carClass:"all", rarity:"all"};
    state.gachaHistoryTier = "";
    state.gachaHistorySignature = "";
    state.garage.selectedId = "";
    state.dealer.garageId = "";
    state.gacha.garageId = "";
    return true;
  }

  async function refreshLife({packs = false, catalog = false} = {}) {
    if (!bridge()) return null;
    syncLifeScope();
    const scope = currentLifeScope();
    const needsPacks = Boolean(packs);
    const needsCatalog = Boolean(catalog);
    if (lifeRequestPromise) {
      const covered = lifeRequestScope === scope
        && (!needsPacks || lifeRequestFlags.packs)
        && (!needsCatalog || lifeRequestFlags.catalog);
      if (covered) return lifeRequestPromise;
      try {
        await lifeRequestPromise;
      } catch (_error) {
        // The retry below owns the visible error state.
      }
      syncLifeScope();
      if (currentLifeScope() !== scope) return null;
      return refreshLife({packs, catalog});
    }
    const token = ++lifeRequestGeneration;
    lifeRequestScope = scope;
    lifeRequestFlags = {packs:needsPacks, catalog:needsCatalog};
    state.loading = true;
    state.error = "";
    if (!state.data) paint();
    const job = (async () => {
      const jobs = [requestJSON("/api/life")];
      if (needsPacks) jobs.push(requestJSON("/api/life/city-packs"));
      if (needsCatalog) jobs.push(requestJSON("/api/life/catalog"));
      const results = await Promise.allSettled(jobs);
      if (token !== lifeRequestGeneration || scope !== currentLifeScope()) return null;
      const lifeResult = results[0];
      if (lifeResult.status === "fulfilled") applyLifeResponse(lifeResult.value);
      let cursor = 1;
      if (needsPacks) {
        const result = results[cursor++];
        if (result.status === "fulfilled") state.packs = result.value;
        else if (lifeResult.status === "fulfilled") state.error = result.reason?.message || String(result.reason || "");
      }
      if (needsCatalog) {
        const result = results[cursor++];
        if (result.status === "fulfilled") state.catalog = result.value;
        else if (lifeResult.status === "fulfilled") state.error = result.reason?.message || String(result.reason || "");
      }
      if (lifeResult.status === "rejected") {
        state.error = lifeResult.reason?.message || String(lifeResult.reason || t("life.error"));
      }
      if (!state.error) warmVehicleImageCache();
      state.loadedAt = Date.now();
      return state.data;
    })();
    lifeRequestPromise = job;
    try {
      return await job;
    } finally {
      if (token === lifeRequestGeneration) {
        state.loading = false;
        lifeRequestPromise = null;
        lifeRequestFlags = {packs:false, catalog:false};
        paint();
      }
    }
  }

  async function preload({announce = false} = {}) {
    const api = bridge();
    if (!api?.isSaveConnected?.() || !api?.isWalletReady?.()) return null;
    syncLifeScope();
    const scope = currentLifeScope();
    const gameDate = currentLifeGameDate();
    if (state.data && state.catalog && !state.error && (!gameDate || String(state.data.game_date || "") === gameDate)) {
      return state.data;
    }
    if (lifePreloadPromise) {
      if (announce && !lifePreloadAnnounced) {
        lifePreloadAnnounced = true;
        api.toast(t("life.preload.started"));
      }
      return lifePreloadPromise;
    }
    lifePreloadAnnounced = announce;
    if (announce) api.toast(t("life.preload.started"));
    const job = (async () => {
      let result = await refreshLife({catalog:true});
      if (scope === currentLifeScope() && result && gameDate && String(result.game_date || "") !== gameDate) {
        result = await refreshLife({});
      }
      if (scope !== currentLifeScope()) return null;
      const ready = Boolean(result && state.catalog && !state.error);
      if (lifePreloadAnnounced) {
        api.toast(ready ? t("life.preload.ready") : (state.error || t("life.preload.failed")));
      }
      return ready ? result : null;
    })();
    lifePreloadPromise = job;
    try {
      return await job;
    } finally {
      if (lifePreloadPromise === job) {
        lifePreloadPromise = null;
        lifePreloadAnnounced = false;
      }
    }
  }

  async function postLife(path, payload, busyLabel) {
    if (state.busy || !bridge()) return null;
    state.busy = busyLabel;
    paint();
    try {
      const response = await bridge().request(path, {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload || {}),
      });
      applyLifeResponse(response);
      return response;
    } catch (error) {
      if (path.includes("buy-batch") && typeof localStorage !== "undefined") {
        try {
          localStorage.setItem("fmodd:last-batch-error", JSON.stringify({
            at: new Date().toISOString(),
            path,
            payload: payload || {},
            message: String(error?.message || ""),
            server: error?.payload || null,
          }));
        } catch (_storageError) {}
      }
      bridge().toast(error.message || t("life.error"));
      return null;
    } finally {
      state.busy = "";
      paint();
    }
  }

  function paint() {
    const root = pageRoot();
    if (!root) return;
    paintBalance();
    paintCollectionButton();
    paintStorageButton();
    // The shell polls every few seconds. Rebuilding the page under an open
    // dialog resets scroll containers and image stages, which reads as a
    // flicker. Dialog actions repaint their own content explicitly instead.
    if (anyLifeDialogOpen()) return;
    if (!state.data && state.loading) {
      root.innerHTML = loadingMarkup();
      bridge()?.renderIcons(root);
      return;
    }
    if (!state.data) {
      root.innerHTML = errorMarkup(state.error);
      bridge()?.renderIcons(root);
      return;
    }
    const banner = state.error
      ? `<div class="life-inline-warning" role="status"><i data-lucide="wifi-off"></i><span>${esc(state.error)}</span></div>`
      : "";
    const renderer = {
      "life-map": renderMapPage,
      "life-properties": renderPropertiesPage,
      "life-garage": renderGaragePage,
      "life-dealer": renderDealerPage,
      "life-gacha": renderGachaPage,
    }[state.page];
    root.innerHTML = banner + (renderer ? renderer() : emptyMarkup());
    bridge()?.renderIcons(root);
    paintCollectionButton();
    paintStorageButton();
    scheduleVehicleImageHydration(root);
    if (state.page === "life-map") requestAnimationFrame(() => { bindMap(); drawMap(); });
    if (state.page === "life-dealer") requestAnimationFrame(paintDealerResults);
  }

  function render(page) {
    const next = pageRoots[page] ? page : "life-map";
    state.page = next;
    ensureEvents();
    const needsCatalog = next === "life-dealer" || next === "life-gacha" || next === "life-garage";
    const needsPacks = next === "life-map";
    syncLifeScope();
    const gameDate = currentLifeGameDate();
    const stale = !state.data || Boolean(gameDate && String(state.data.game_date || "") !== gameDate);
    paint();
    if (stale || (needsPacks && !state.packs) || (needsCatalog && !state.catalog)) {
      void refreshLife({packs: needsPacks, catalog: needsCatalog});
    }
  }

  function ensureEvents() {
    if (ensureEvents.ready) return;
    ensureEvents.ready = true;
    document.addEventListener("click", handleLifeClick);
    document.addEventListener("change", handleLifeChange);
    document.addEventListener("input", handleLifeInput);
    for (const [dialogId, close] of [
      ["life-collection-dialog", closeCollectionDialog],
      ["life-storage-dialog", closeStorageDialog],
      ["life-gacha-history-dialog", closeGachaHistoryDialog],
      ["life-gacha-catalog-dialog", closeGachaCatalogDialog],
      ["life-map-bulk-dialog", closeMapBulkDialog],
      ["life-garage-bulk-dialog", closeGarageBulkDialog],
    ]) {
      const dialog = document.getElementById(dialogId);
      if (!dialog) continue;
      dialog.addEventListener("click", (event) => {
        if (event.target === dialog) close();
      });
      dialog.addEventListener("cancel", (event) => {
        event.preventDefault();
        close();
      });
    }
    document.addEventListener("fmodd:localechange", () => {
      if (!state.page) return;
      state.catalog = null;
      paint();
      if (document.getElementById("life-map-bulk-dialog")?.open) renderMapBulkDialog();
      if (document.getElementById("life-garage-bulk-dialog")?.open) renderGarageBulkDialog();
      void refreshLife({catalog:true});
    });
    document.addEventListener("fmodd:life-assets-changed", () => {
      if (state.page) void refreshLife();
    });
    document.addEventListener("fmodd:game-clock-changed", (event) => {
      if (!state.page) return;
      if (event?.detail?.dateChanged) {
        // Game time advanced: re-read rent, construction, income and vehicle
        // values immediately instead of waiting for the next page visit.
        void refreshLife({packs: state.page === "life-map", catalog: false});
      }
    });
    window.addEventListener("resize", () => {
      if (state.page === "life-map") requestAnimationFrame(drawMap);
    });
  }

  function cityPacks() {
    return Array.isArray(state.packs?.packs) ? state.packs.packs : [];
  }

  function selectedCity() {
    return cityPacks().find((city) => String(city.city_id) === String(state.map.cityId)) || null;
  }

  function mapProviderMode() {
    return ["auto", "amap", "osm"].includes(state.map.provider) ? state.map.provider : "auto";
  }

  function effectiveMapProvider() {
    const mode = mapProviderMode();
    const country = String(selectedCity()?.country || state.map.countryCode || "CN").toUpperCase();
    const base = mode === "auto" ? (country === "CN" ? "amap" : "bing") : mode;
    return mode === "auto" && state.map.fallbackProvider ? state.map.fallbackProvider : base;
  }

  function ensureMapCity() {
    const packs = cityPacks();
    if (!packs.length) return;
    const countries = mapCountries();
    if (!state.map.countryCode || !countries.some((row) => row.code === state.map.countryCode)) {
      const selected = selectedCity();
      state.map.countryCode = String(selected?.country || countries[0]?.code || "CN").toUpperCase();
    }
    const scoped = mapCountryCities();
    let city = selectedCity();
    if (!city || String(city.country || "CN").toUpperCase() !== state.map.countryCode) {
      city = scoped.find((row) => row.installed) || scoped[0] || packs[0];
      state.map.countryCode = String(city.country || state.map.countryCode || "CN").toUpperCase();
      state.map.cityId = String(city.city_id);
      state.map.center = {lat: Number(city.lat), lng: Number(city.lng)};
      state.map.parcelId = "";
      state.map.fallbackProvider = "";
    }
    if (!state.map.center) state.map.center = {lat: Number(city.lat), lng: Number(city.lng)};
  }

  function mapParcels() {
    return Array.isArray(state.packs?.parcels?.[state.map.cityId])
      ? state.packs.parcels[state.map.cityId] : [];
  }

  function ownedParcelIds() {
    return new Set((state.data?.properties || []).map((row) => String(row.parcel_id || "")));
  }

  function propertyForParcel(parcelId) {
    return (state.data?.properties || []).find(
      (row) => String(row.parcel_id || "") === String(parcelId || ""),
    ) || null;
  }

  function renderMapPage() {
    ensureMapCity();
    const city = selectedCity();
    if (!city) return emptyMarkup(t("life.loading"), "map");
    const layer = currentMapLayer();
    const summary = mapLayerSummary(layer);
    const installed = Boolean(summary?.installed);
    const countries = mapCountries();
    const countryOptions = countries.map((row) => `<option value="${esc(row.code)}" ${row.code === state.map.countryCode ? "selected" : ""}>${esc(row.name)}</option>`).join("");
    const cityOptions = mapCountryCities().map((row) => `<option value="${esc(row.city_id)}" ${String(row.city_id) === String(state.map.cityId) ? "selected" : ""}>${esc(cityName(row))}${row.installed ? ` · ${esc(t("life.map.pack_ready", {count:row.parcels, size:formatBytes(row.size_bytes)}))}` : ""}</option>`).join("");
    const parcels = layer === "parcel" && installed
      ? mapParcels().filter((parcel) => state.map.kind === "all" || parcel.kind === state.map.kind)
      : [];
    const selected = parcels.find((parcel) => String(parcel.id) === String(state.map.parcelId)) || null;
    const nodes = installed && layer !== "parcel" ? aggregateNodes(layer) : [];
    const totals = aggregateTotals(nodes);
    const markers = installed
      ? layer === "parcel"
        ? parcels.map((parcel) => mapMarkerMarkup(parcel, selected?.id === parcel.id)).join("")
        : nodes.map((node) => mapClusterMarkup(node, layer)).join("")
      : "";
    const layerRange = mapLayerZoomRange(layer);
    const providerMode = mapProviderMode();
    const provider = effectiveMapProvider();
    const attribution = provider === "amap"
      ? `<a class="life-map-attribution" href="https://lbs.amap.com/" target="_blank" rel="noopener noreferrer">${esc(t("life.map.amap_attribution"))}</a>`
      : provider === "bing"
        ? `<a class="life-map-attribution" href="https://www.bing.com/maps" target="_blank" rel="noopener noreferrer">${esc(t("life.map.bing_attribution"))}</a>`
        : `<a class="life-map-attribution" href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">${esc(t("life.map.osm_attribution"))}</a>`;
    const packTitle = layer === "parcel" || layer === "city" ? cityName(city)
      : layer === "country" ? `${countryName(state.map.countryCode)} · ${mapLayerLabel(layer)}`
      : mapLayerLabel(layer);
    const packCopy = layer === "parcel"
      ? installed ? t("life.map.pack_ready", {count:city.parcels, size:formatBytes(city.size_bytes)}) : t("life.map.install_hint")
      : installed ? t("life.map.layer_ready", {size:formatBytes(summary.size_bytes)}) : t("life.map.layer_missing");
    const countCopy = layer === "parcel"
      ? t("life.map.plot_count", {count:mapParcels().length})
      : t("life.map.layer_assets", {count:totals.count, value:money(totals.value)});
    return `
      <div class="life-map-toolbar">
        <label class="life-field life-map-country-field"><span>${esc(t("life.map.country"))}</span><select data-life-map-country>${countryOptions}</select></label>
        <label class="life-field life-map-city-field"><span>${esc(t("life.city"))}</span><select data-life-map-city>${cityOptions}</select></label>
        <label class="life-field life-map-provider-field"><span>${esc(t("life.map.basemap"))}</span><select data-life-map-provider><option value="auto" ${providerMode === "auto" ? "selected" : ""}>${esc(t("life.map.basemap_auto"))}</option><option value="amap" ${providerMode === "amap" ? "selected" : ""}>${esc(t("life.map.basemap_amap"))}</option><option value="bing" ${providerMode === "bing" ? "selected" : ""}>${esc(t("life.map.basemap_bing"))}</option><option value="osm" ${providerMode === "osm" ? "selected" : ""}>${esc(t("life.map.basemap_osm"))}</option></select></label>
        <div class="life-map-pack-copy"><strong>${esc(packTitle)}</strong><span>${esc(packCopy)}</span></div>
        <button type="button" class="life-primary" data-life-action="download-map-layer" ${installed || state.busy === "map-layer" ? "disabled" : ""}><i data-lucide="${state.busy === "map-layer" ? "loader-circle" : "package-plus"}"></i>${esc(state.busy === "map-layer" ? t("life.map.layer_downloading") : installed ? t("life.map.layer_owned") : t("life.map.download_layer"))}</button>
        <button type="button" class="life-secondary" data-life-action="open-map-bulk" ${installed && layer === "parcel" ? "" : "disabled"}><i data-lucide="shopping-basket"></i>${esc(t("life.map.bulk_open"))}</button>
        <button type="button" class="life-icon-button" data-life-action="refresh" aria-label="${esc(t("world.refresh"))}" title="${esc(t("world.refresh"))}"><i data-lucide="refresh-cw"></i></button>
      </div>
      <div class="life-map-grid">
        <div class="life-map-stage">
          <div class="life-map-viewport" data-life-map viewport role="application" aria-label="${esc(t("life.map.title"))}">
            <div class="life-map-tiles" data-life-map-tiles aria-hidden="true"></div>
            <div class="life-map-markers" data-life-map-markers>${markers}</div>
            <div class="life-map-layer-chip"><span>${esc(mapLayerLabel(layer))}</span><small>${esc(t("life.map.zoom_range", {min:layerRange[0], max:layerRange[1]}))}</small></div>
            ${installed ? "" : `<div class="life-map-empty-overlay"><i data-lucide="package-plus"></i><strong>${esc(layer === "parcel" ? t("life.map.no_pack") : t("life.map.no_layer"))}</strong><span>${esc(t("life.map.download_hint", {layer:mapLayerLabel(layer)}))}</span></div>`}
            <div class="life-map-controls" aria-label="${esc(t("life.map.drag_hint"))}">
              <button type="button" data-life-action="map-zoom" data-direction="1" aria-label="${esc(t("life.map.zoom_in"))}" title="${esc(t("life.map.zoom_in"))}"><i data-lucide="plus"></i></button>
              <span>${state.map.zoom}</span>
              <button type="button" data-life-action="map-zoom" data-direction="-1" aria-label="${esc(t("life.map.zoom_out"))}" title="${esc(t("life.map.zoom_out"))}"><i data-lucide="minus"></i></button>
            </div>
            <div class="life-map-drag-hint"><i data-lucide="hand"></i><span>${esc(t("life.map.drag_hint"))}</span></div>
            ${attribution}
            <div class="life-map-tile-error" id="life-map-tile-error" ${state.map.tileError ? "" : "hidden"}><i data-lucide="wifi-off"></i><span>${esc(t("life.map.tile_error"))}</span></div>
          </div>
          <div class="life-map-underbar"><span><i data-lucide="layers-3"></i>${esc(layer === "parcel" ? t("life.map.parcel_trade_note") : t("life.map.aggregate_note"))}</span><strong>${esc(countCopy)}</strong></div>
        </div>
        <aside class="life-map-panel">
          ${layer === "parcel" ? `
            <div class="life-kind-tabs" role="tablist" aria-label="${esc(t("life.map.all_kinds"))}">
              ${["all", "residential", "commercial", "industrial", "garage"].map((kind) => `<button type="button" role="tab" aria-selected="${state.map.kind === kind}" class="${state.map.kind === kind ? "active" : ""}" data-life-action="map-kind" data-kind="${kind}">${esc(kind === "all" ? t("life.map.all_kinds") : kindLabel(kind))}</button>`).join("")}
            </div>
            ${installed ? selected ? mapParcelDetail(selected) : `<div class="life-map-list-head"><strong>${esc(t("life.map.plot_count", {count:parcels.length}))}</strong><span>${esc(t("life.map.choose_plot"))}</span></div><div class="life-map-plot-list">${parcels.length ? parcels.map(mapPlotRow).join("") : emptyMarkup(t("life.map.no_pack"), "map-pin-off")}</div>` : emptyMarkup(t("life.map.no_pack"), "package-open")}
          ` : mapAggregatePanel(layer, nodes, installed)}
        </aside>
      </div>`;
  }

  function mapBulkCandidates(kind = state.mapBulk.kind) {
    const owned = ownedParcelIds();
    return mapParcels().filter((parcel) => (
      !owned.has(String(parcel.id))
      && (kind === "all" || String(parcel.kind || "") === kind)
    ));
  }

  function mapBulkTotal(parcels) {
    return parcels.reduce(
      (total, parcel) => total + Number(parcel.buy_total || parcel.quote || 0),
      0,
    );
  }

  function renderMapBulkDialog() {
    const host = document.getElementById("life-map-bulk-content");
    if (!host) return;
    const city = selectedCity();
    if (!city) {
      host.innerHTML = emptyMarkup(t("life.loading"), "map");
      return;
    }
    const kinds = ["all", "residential", "commercial", "industrial", "garage"];
    const allUnowned = mapParcels().filter((parcel) => !ownedParcelIds().has(String(parcel.id)));
    const counts = Object.fromEntries(kinds.map((kind) => [
      kind,
      kind === "all"
        ? allUnowned.length
        : allUnowned.filter((parcel) => String(parcel.kind || "") === kind).length,
    ]));
    const candidates = mapBulkCandidates();
    const total = mapBulkTotal(candidates);
    const available = availableLifeFunds();
    const shortfall = Math.max(0, total - available);
    const preview = candidates.slice(0, 8).map((parcel) => `<div class="life-bulk-row"><span><strong>${esc(propertyName(parcel))}</strong><small>${esc(kindLabel(parcel.kind))} · ${Number(parcel.area_sqm || 0).toLocaleString()} m²</small></span><b>${esc(money(Number(parcel.buy_total || parcel.quote || 0)))}</b></div>`).join("");
    host.innerHTML = `<div class="life-bulk-summary"><span><small>${esc(t("life.map.bulk_city"))}</small><strong>${esc(cityName(city))}</strong></span><span><small>${esc(t("life.map.bulk_available"))}</small><strong>${Number(allUnowned.length)}</strong></span><span><small>${esc(t("life.map.bulk_selected"))}</small><strong>${Number(candidates.length)}</strong></span></div>
      <div class="life-kind-tabs" role="tablist" aria-label="${esc(t("life.map.all_kinds"))}">${kinds.map((kind) => `<button type="button" role="tab" aria-selected="${state.mapBulk.kind === kind}" class="${state.mapBulk.kind === kind ? "active" : ""}" data-life-action="map-bulk-kind" data-kind="${kind}">${esc(kind === "all" ? t("life.map.all_kinds") : kindLabel(kind))}<b>${Number(counts[kind] || 0)}</b></button>`).join("")}</div>
      <div class="life-bulk-metrics"><span><small>${esc(t("life.map.bulk_count"))}</small><strong>${Number(candidates.length)}</strong></span><span><small>${esc(t("life.map.bulk_total"))}</small><strong>${esc(money(total))}</strong></span><span><small>${esc(t("life.map.bulk_available_funds"))}</small><strong class="${shortfall > 0 ? "is-short" : ""}">${esc(money(available))}</strong></span></div>
      <div class="life-bulk-list">${preview || emptyMarkup(t("life.map.bulk_empty"), "land-plot")}${candidates.length > 8 ? `<small class="life-bulk-more">${esc(t("life.map.bulk_more", {count: candidates.length - 8}))}</small>` : ""}</div>
      <p class="life-bulk-note"><i data-lucide="info"></i>${esc(t("life.map.bulk_note"))}</p>
      ${shortfall > 0 ? `<p class="life-storage-warning"><i data-lucide="triangle-alert"></i>${esc(t("life.map.bulk_shortfall", {amount:money(shortfall)}))}</p>` : ""}
      <footer class="life-bulk-footer"><button type="button" class="life-primary" data-life-action="confirm-map-bulk" ${!candidates.length ? "disabled" : ""}><i data-lucide="land-plot"></i><span>${esc(t("life.map.bulk_buy", {count: candidates.length}))}</span></button></footer>`;
    bridge()?.renderIcons(host);
  }

  function openMapBulkDialog() {
    const dialog = document.getElementById("life-map-bulk-dialog");
    if (!dialog) return;
    if (dialog.parentElement !== document.body) {
      dialog.classList.add("life-page");
      document.body.appendChild(dialog);
    }
    renderMapBulkDialog();
    if (!dialog.open) {
      if (typeof dialog.showModal === "function") dialog.showModal();
      else dialog.setAttribute("open", "");
    }
  }

  function closeMapBulkDialog() {
    const dialog = document.getElementById("life-map-bulk-dialog");
    if (!dialog) return;
    if (typeof dialog.close === "function") dialog.close();
    else dialog.removeAttribute("open");
  }

  function mapMarkerMarkup(parcel, selected) {
    const owned = ownedParcelIds().has(String(parcel.id));
    return `<button type="button" class="life-map-marker life-kind-${esc(parcel.kind)} ${selected ? "selected" : ""} ${owned ? "owned" : ""}" data-life-action="map-marker" data-parcel-id="${esc(parcel.id)}" data-map-lat="${esc(parcel.lat)}" data-map-lng="${esc(parcel.lng)}" title="${esc(propertyName(parcel))}" aria-label="${esc(propertyName(parcel))}"><span></span></button>`;
  }

  function mapClusterMarkup(node, layer) {
    const selected = String(state.map.nodeId || "") === String(node.id);
    return `<button type="button" class="life-map-cluster layer-${esc(layer)} ${selected ? "selected" : ""} ${Number(node.asset_count || 0) ? "" : "empty"}" data-life-action="map-aggregate" data-node-id="${esc(node.id)}" data-map-lat="${esc(node.lat)}" data-map-lng="${esc(node.lng)}" title="${esc(aggregateName(node))}"><strong>${Number(node.asset_count || 0)}</strong><span>${esc(money(node.asset_value || 0))}</span><small>${esc(aggregateName(node))}</small></button>`;
  }

  function mapAggregatePanel(layer, nodes, installed) {
    const totals = aggregateTotals(nodes);
    if (!installed) {
      return `<div class="life-map-list-head"><strong>${esc(mapLayerLabel(layer))}</strong><span>${esc(t("life.map.layer_missing"))}</span></div>${emptyMarkup(t("life.map.download_hint", {layer:mapLayerLabel(layer)}), "layers")}`;
    }
    const rows = nodes.length ? nodes.map((node) => `<button type="button" class="life-map-aggregate-row ${String(state.map.nodeId || "") === String(node.id) ? "selected" : ""}" data-life-action="map-aggregate" data-node-id="${esc(node.id)}" data-map-lat="${esc(node.lat)}" data-map-lng="${esc(node.lng)}"><span class="life-map-aggregate-icon"><i data-lucide="${layer === "world" ? "globe-2" : layer === "country" ? "building-2" : "map-pinned"}"></i></span><span><strong>${esc(aggregateName(node))}</strong><small>${esc(node.region || t("life.map.city_focus"))}</small></span><b>${Number(node.asset_count || 0)}</b><em>${esc(money(node.asset_value || 0))}</em></button>`).join("") : emptyMarkup(t("life.map.no_assets"), "house");
    return `<div class="life-map-list-head"><strong>${esc(mapLayerLabel(layer))}</strong><span>${esc(t("life.map.aggregate_note"))}</span></div><div class="life-map-aggregate-total"><span>${esc(t("life.map.assets_total", {count:totals.count}))}</span><strong>${esc(money(totals.value))}</strong></div><div class="life-map-aggregate-list">${rows}</div>`;
  }

  function mapPlotRow(parcel) {
    const existing = propertyForParcel(parcel.id);
    const occupied = Boolean(existing);
    const leased = String(existing?.tenure || "") === "lease";
    const constructing = Boolean(existing?.is_construction);
    const parking = Number(parcel.parking_spaces || 0);
    const status = constructing ? t("life.properties.construction") : leased ? t("life.properties.tenure_lease") : t("life.map.owned");
    return `<button type="button" class="life-map-plot-row ${String(parcel.id) === String(state.map.parcelId) ? "selected" : ""} ${occupied ? "occupied" : ""}" data-life-action="map-marker" data-parcel-id="${esc(parcel.id)}" data-map-focus="true"><span class="life-kind-dot life-kind-${esc(parcel.kind)}"></span><span><strong>${esc(propertyName(parcel))}</strong><small>${esc(kindLabel(parcel.kind))} · ${Number(parcel.area_sqm).toLocaleString()} m²${parking ? ` · ${parking} ${esc(t("life.garage.parking_spaces"))}` : ""}</small></span><b>${esc(money(parcel.quote || parcel.base_price))}</b>${occupied ? `<em class="${leased ? "lease" : constructing ? "construction" : "owned"}">${esc(status)}</em>` : ""}</button>`;
  }

  function mapParcelDetail(parcel) {
    if (!canTradeMap()) {
      return `<article class="life-map-detail life-map-locked"><i data-lucide="lock-keyhole"></i><strong>${esc(t("life.map.parcel_locked"))}</strong><span>${esc(t("life.map.zoom_range", {min:TRADE_MIN_ZOOM, max:TRADE_MAX_ZOOM}))}</span></article>`;
    }
    const existing = propertyForParcel(parcel.id);
    const occupied = Boolean(existing);
    const parking = Number(parcel.parking_spaces || 0);
    const leaseOptions = Array.isArray(parcel.lease_options) ? parcel.lease_options : [];
    const selectedLease = leaseOptions.find((row) => Number(row.days) === Number(state.map.leaseDays)) || leaseOptions[0] || null;
    const occupancy = occupied
      ? `<div class="life-map-occupancy"><span class="life-kind-pill">${esc(String(existing.tenure || "owned") === "lease" ? t("life.properties.tenure_lease") : t("life.properties.tenure_owned"))}</span><strong>${esc(t("life.map.occupied"))}</strong><small>${esc(t("life.map.occupied_hint"))}</small></div>`
      : "";
    return `<article class="life-map-detail">
      <header><span class="life-kind-pill life-kind-${esc(parcel.kind)}">${esc(kindLabel(parcel.kind))}</span><button type="button" class="life-icon-button" data-life-action="map-close" aria-label="${esc(t("common.close"))}" title="${esc(t("common.close"))}"><i data-lucide="x"></i></button></header>
      <h3>${esc(propertyName(parcel))}</h3>
      <p class="life-map-detail-location"><i data-lucide="map-pin"></i>${esc(cityName(selectedCity()))} · ${esc(districtName(parcel))}</p>
      <dl class="life-detail-grid">
        <div><dt>${esc(t("life.area"))}</dt><dd>${Number(parcel.area_sqm).toLocaleString()} m²</dd></div>
        <div><dt>${esc(t("life.garage.parking_spaces"))}</dt><dd>${parking}</dd></div>
        <div><dt>${esc(t("life.map.unit_price"))}</dt><dd>${esc(money(parcel.unit_price))}</dd></div>
        <div><dt>${esc(t("life.map.buy_plot"))}</dt><dd>${esc(money(parcel.quote || parcel.base_price))}</dd></div>
        <div><dt>${esc(t("life.map.buy_cost"))}</dt><dd>${esc(money(parcel.buy_fee || 0))}</dd></div>
        <div class="wide"><dt>${esc(t("life.monthly"))} · ${esc(t("life.properties.mode_rent"))}</dt><dd>${esc(money(parcel.monthly_rent))}</dd></div>
        <div class="wide"><dt>${esc(t("life.monthly"))} · ${esc(t("life.properties.mode_operate"))}</dt><dd>${esc(money(parcel.monthly_operating_net))}</dd></div>
      </dl>
      ${occupancy}
      <div class="life-map-purchase-grid">
        <section class="life-map-purchase-option">
          <header><i data-lucide="land-plot"></i><span>${esc(t("life.map.buy_plot"))}</span></header>
          <div class="life-map-total"><span>${esc(t("life.total"))}</span><strong>${esc(money(parcel.buy_total || ((Number(parcel.quote || parcel.base_price) || 0) * 1.025)))}</strong></div>
          <button type="button" class="life-primary life-wide-button" data-life-action="buy-plot" data-parcel-id="${esc(parcel.id)}" ${occupied || state.busy === "buy-plot" ? "disabled" : ""}><i data-lucide="${state.busy === "buy-plot" ? "loader-circle" : occupied ? "badge-check" : "land-plot"}"></i>${esc(occupied ? t("life.map.occupied") : state.busy === "buy-plot" ? t("life.map.buying") : t("life.map.buy_plot"))}</button>
        </section>
        <section class="life-map-purchase-option lease">
          <header><i data-lucide="file-signature"></i><span>${esc(t("life.map.lease_plot"))}</span></header>
          <label class="life-field"><span>${esc(t("life.map.lease_terms"))}</span><select data-life-lease-days ${occupied ? "disabled" : ""}>${leaseOptions.map((row) => `<option value="${Number(row.days)}" ${selectedLease && Number(row.days) === Number(selectedLease.days) ? "selected" : ""}>${esc(t("life.days", {count:Number(row.days)}))}</option>`).join("")}</select></label>
          ${selectedLease ? `<div class="life-lease-facts compact"><span><small>${esc(t("life.map.prepaid_rent"))}</small><b>${esc(money(selectedLease.prepaid_rent))}</b></span><span><small>${esc(t("life.map.deposit"))}</small><b>${esc(money(selectedLease.deposit))}</b></span></div><div class="life-map-total"><span>${esc(t("life.total"))}</span><strong>${esc(money(selectedLease.total))}</strong></div>` : ""}
          <button type="button" class="life-secondary life-wide-button" data-life-action="lease-plot" data-parcel-id="${esc(parcel.id)}" ${occupied || state.busy === "lease-plot" ? "disabled" : ""}><i data-lucide="${state.busy === "lease-plot" ? "loader-circle" : occupied ? "badge-check" : "file-signature"}"></i>${esc(occupied ? t("life.map.occupied") : state.busy === "lease-plot" ? t("life.map.leasing") : t("life.map.lease_plot"))}</button>
        </section>
      </div>
    </article>`;
  }

  function project(lat, lng, zoom) {
    const size = TILE_SIZE * (2 ** zoom);
    const clamped = Math.max(-85.05112878, Math.min(85.05112878, Number(lat)));
    const sin = Math.sin(clamped * Math.PI / 180);
    return {
      x: (Number(lng) + 180) / 360 * size,
      y: (0.5 - Math.log((1 + sin) / (1 - sin)) / (4 * Math.PI)) * size,
      size,
    };
  }

  function unproject(x, y, zoom) {
    const size = TILE_SIZE * (2 ** zoom);
    const lng = x / size * 360 - 180;
    const n = Math.PI - 2 * Math.PI * y / size;
    const lat = 180 / Math.PI * Math.atan(Math.sinh(n));
    return {lat, lng};
  }

  function scheduleMapDraw() {
    if (state.map.drawFrame) return;
    state.map.drawFrame = requestAnimationFrame(() => {
      state.map.drawFrame = 0;
      drawMap();
    });
  }

  function drawMap() {
    const viewport = document.querySelector("[data-life-map]");
    if (!viewport || !state.map.center) return;
    const provider = effectiveMapProvider();
    const canFallbackToOsm = mapProviderMode() === "auto" && (provider === "amap" || provider === "bing");
    const rect = viewport.getBoundingClientRect();
    if (rect.width < 20 || rect.height < 20) return;
    const zoom = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, state.map.zoom));
    state.map.zoom = zoom;
    const centerCoordinate = providerCoordinate(state.map.center.lat, state.map.center.lng);
    const center = project(centerCoordinate.lat, centerCoordinate.lng, zoom);
    const left = center.x - rect.width / 2;
    const top = center.y - rect.height / 2;
    const startX = Math.floor(left / TILE_SIZE);
    const endX = Math.floor((left + rect.width) / TILE_SIZE);
    const startY = Math.floor(top / TILE_SIZE);
    const endY = Math.floor((top + rect.height) / TILE_SIZE);
    const maxTile = (2 ** zoom) - 1;
    const tiles = [];
    for (let x = startX; x <= endX; x += 1) {
      for (let y = startY; y <= endY; y += 1) {
        if (y < 0 || y > maxTile) continue;
        const wrappedX = ((x % (maxTile + 1)) + maxTile + 1) % (maxTile + 1);
        const source = mapTileUrl(provider, zoom, wrappedX, y).replaceAll("&", "&amp;");
        tiles.push(`<img src="${source}" alt="" draggable="false" decoding="async" referrerpolicy="no-referrer" data-tile-x="${x}" data-tile-y="${y}" style="left:${x * TILE_SIZE - left}px;top:${y * TILE_SIZE - top}px;width:${TILE_SIZE}px;height:${TILE_SIZE}px">`);
      }
    }
    const host = viewport.querySelector("[data-life-map-tiles]");
    if (host) {
      state.map.tileError = false;
      const warning = document.getElementById("life-map-tile-error");
      if (warning) warning.hidden = true;
      host.innerHTML = tiles.join("");
      const images = Array.from(host.querySelectorAll("img"));
      let loadedTiles = 0;
      let failedTiles = 0;
      let fallbackScheduled = false;
      const fallbackToOsm = () => {
        if (!host.isConnected || !canFallbackToOsm || loadedTiles > 0) return;
        state.map.fallbackProvider = "osm";
        bridge()?.toast(t("life.map.basemap_fallback_generic"));
        paint();
      };
      const scheduleAmapFallback = () => {
        if (fallbackScheduled || !canFallbackToOsm) return;
        fallbackScheduled = true;
        window.setTimeout(() => {
          fallbackScheduled = false;
          if (!host.isConnected || !canFallbackToOsm || loadedTiles > 0) return;
          if (failedTiles < Math.min(3, images.length)) return;
          fallbackToOsm();
        }, 900);
      };
      images.forEach((image) => {
        if (image.complete) {
          if (image.naturalWidth > 0) {
            loadedTiles += 1;
          } else {
            failedTiles += 1;
            scheduleAmapFallback();
          }
          return;
        }
        image.addEventListener("load", () => { loadedTiles += 1; }, {once: true});
        image.addEventListener("error", () => {
          failedTiles += 1;
          if (canFallbackToOsm) {
            scheduleAmapFallback();
            return;
          }
          state.map.tileError = true;
          const currentWarning = document.getElementById("life-map-tile-error");
          if (currentWarning) currentWarning.hidden = false;
        }, {once: true});
      });
      window.setTimeout(() => {
        if (!host.isConnected || !canFallbackToOsm || loadedTiles > 0) return;
        fallbackToOsm();
      }, 3000);
    }
    viewport.querySelectorAll("[data-map-lat][data-map-lng]").forEach((marker) => {
      const coordinate = providerCoordinate(Number(marker.dataset.mapLat), Number(marker.dataset.mapLng));
      const point = project(coordinate.lat, coordinate.lng, zoom);
      const x = point.x - left;
      const y = point.y - top;
      const margin = marker.classList.contains("life-map-cluster") ? 80 : 24;
      const visible = x > -margin && y > -margin && x < rect.width + margin && y < rect.height + margin;
      marker.hidden = !visible;
      marker.style.transform = `translate3d(${x}px, ${y}px, 0) translate(-50%, ${marker.classList.contains("life-map-cluster") ? "-50%" : "-100%"})`;
    });
  }

  function bindMap() {
    const viewport = document.querySelector("[data-life-map]");
    if (!viewport || viewport.dataset.lifeMapBound === "true") {
      scheduleMapDraw();
      return;
    }
    viewport.dataset.lifeMapBound = "true";
    viewport.addEventListener("pointerdown", (event) => {
      if (event.button !== 0 || event.target.closest("[data-life-action], a, button, select")) return;
      state.map.dragging = {
        pointerId: event.pointerId,
        startX: event.clientX,
        startY: event.clientY,
        center: {...state.map.center},
      };
      viewport.setPointerCapture?.(event.pointerId);
      viewport.classList.add("dragging");
    });
    viewport.addEventListener("pointermove", (event) => {
      const drag = state.map.dragging;
      if (!drag || drag.pointerId !== event.pointerId) return;
      const startCoordinate = providerCoordinate(drag.center.lat, drag.center.lng);
      const start = project(startCoordinate.lat, startCoordinate.lng, state.map.zoom);
      const next = unproject(
        start.x - (event.clientX - drag.startX),
        start.y - (event.clientY - drag.startY),
        state.map.zoom,
      );
      state.map.center = effectiveMapProvider() === "amap" ? gcj02ToWgs84(next.lat, next.lng) : next;
      scheduleMapDraw();
    });
    const finishDrag = (event) => {
      if (!state.map.dragging || state.map.dragging.pointerId !== event.pointerId) return;
      state.map.dragging = null;
      viewport.classList.remove("dragging");
      try { viewport.releasePointerCapture?.(event.pointerId); } catch (_error) { /* released */ }
    };
    viewport.addEventListener("pointerup", finishDrag);
    viewport.addEventListener("pointercancel", finishDrag);
    viewport.addEventListener("wheel", (event) => {
      if (event.target.closest("a, select")) return;
      event.preventDefault();
      setMapZoom(state.map.zoom + (event.deltaY < 0 ? 1 : -1));
    }, {passive:false});
    scheduleMapDraw();
  }

  function setMapZoom(value) {
    const next = Math.max(MIN_ZOOM, Math.min(MAX_ZOOM, Number(value) || MIN_ZOOM));
    if (next === state.map.zoom) return;
    const previousLayer = currentMapLayer();
    state.map.zoom = next;
    if (mapLayerForZoom(next) !== previousLayer) {
      state.map.parcelId = "";
      state.map.nodeId = "";
    }
    paint();
  }

  function setMapProvider(value) {
    const provider = ["auto", "amap", "bing", "osm"].includes(value) ? value : "auto";
    if (provider === state.map.provider) return;
    state.map.provider = provider;
    state.map.fallbackProvider = "";
    state.map.tileError = false;
    saveMapProvider(provider);
    paint();
  }

  function selectMapCity(cityId) {
    const city = cityPacks().find((row) => String(row.city_id) === String(cityId));
    if (!city) return;
    state.map.countryCode = String(city.country || state.map.countryCode || "CN").toUpperCase();
    state.map.cityId = String(city.city_id);
    state.map.center = {lat: Number(city.lat), lng: Number(city.lng)};
    state.map.parcelId = "";
    state.map.nodeId = "";
    state.map.kind = "all";
    state.map.fallbackProvider = "";
    state.map.tileError = false;
    paint();
  }

  function selectMapCountry(countryCode) {
    const code = String(countryCode || "").toUpperCase();
    if (!mapCountries().some((row) => row.code === code)) return;
    const scoped = mapCountryCities(code);
    const city = selectedCity()?.country === code
      ? selectedCity()
      : scoped.find((row) => row.installed) || scoped[0];
    if (!city) return;
    state.map.countryCode = code;
    state.map.cityId = String(city.city_id);
    state.map.center = {lat: Number(city.lat), lng: Number(city.lng)};
    state.map.parcelId = "";
    state.map.nodeId = "";
    state.map.kind = "all";
    state.map.fallbackProvider = "";
    state.map.tileError = false;
    paint();
  }

  function propertyBusinessEntries(kind) {
    const rows = state.data?.business_catalog?.[kind] || state.catalog?.businesses?.[kind] || [];
    return Array.isArray(rows) ? rows : [];
  }

  function businessName(row) {
    const locale = window.FMODDI18n?.locale || "en-GB";
    return locale === "zh-CN" || locale === "zh-TW"
      ? String(row?.name_zh || row?.name_en || row?.id || "")
      : String(row?.name_en || row?.name_zh || row?.id || "");
  }

  function propertyModeChoices(kind, property = null) {
    const leased = String(property?.tenure || "owned") === "lease";
    if (kind === "residential" || kind === "garage") {
      return leased ? ["self"] : ["self", "rent"];
    }
    return leased ? ["vacant", "operate"] : ["vacant", "rent", "operate"];
  }

  function propertyModeLabel(mode) {
    const key = `life.properties.mode_${mode}`;
    const value = t(key);
    return value === key ? String(mode || "") : value;
  }

  function renderPropertiesPage() {
    const data = state.data;
    const properties = data.properties || [];
    const pendingDays = properties.reduce(
      (highest, property) => Math.max(highest, Number(property.pending_days || 0)), 0,
    );
    const pendingCopy = pendingDays > 0
      ? t("life.properties.pending_for", {days:pendingDays})
      : t("life.properties.collect_hint");
    const summary = `
      <div class="life-metric-grid life-property-metrics">
        <article class="life-metric life-metric-gold"><small>${esc(t("life.properties.pending"))}</small><strong>${esc(money(data.income?.pending || 0))}</strong><span>${esc(t("life.properties.lifetime"))} · ${esc(money(data.income?.lifetime || 0))}</span></article>
        <article class="life-metric"><small>${esc(t("life.properties.portfolio"))}</small><strong>${esc(money(data.totals?.property_value || 0))}</strong><span>${esc(t("life.properties.count"))} · ${Number(data.totals?.properties || 0).toLocaleString()}</span></article>
        <article class="life-metric life-metric-action"><button type="button" class="life-primary" data-life-action="collect-income" ${Number(data.income?.pending || 0) <= 0 || state.busy === "collect" ? "disabled" : ""}><i data-lucide="${state.busy === "collect" ? "loader-circle" : "hand-coins"}"></i>${esc(state.busy === "collect" ? t("life.properties.collecting") : t("life.properties.collect"))}</button><span>${esc(pendingCopy)}</span></article>
      </div>`;
    if (!properties.length) {
      return summary + `<div class="life-section-card">${emptyMarkup(t("life.properties.empty_hint"), "house")}</div>`;
    }
    const counts = {
      all: properties.length,
      residential: properties.filter((row) => row.kind === "residential").length,
      commercial: properties.filter((row) => row.kind === "commercial").length,
      industrial: properties.filter((row) => row.kind === "industrial").length,
      garage: properties.filter((row) => row.kind === "garage").length,
      owned: properties.filter((row) => String(row.tenure || "owned") === "owned").length,
      lease: properties.filter((row) => String(row.tenure || "") === "lease").length,
      construction: properties.filter((row) => Boolean(row.is_construction)).length,
    };
    const filters = [
      ["all", t("life.properties.filter_all")],
      ["residential", kindLabel("residential")],
      ["commercial", kindLabel("commercial")],
      ["industrial", kindLabel("industrial")],
      ["garage", kindLabel("garage")],
      ["owned", t("life.properties.tenure_owned")],
      ["lease", t("life.properties.tenure_lease")],
      ["construction", t("life.properties.construction")],
    ];
    const filterMarkup = `<div class="life-asset-filter" role="group" aria-label="${esc(t("life.properties.filters"))}">
      ${filters.map(([value, label]) => `<button type="button" class="${state.assetFilter === value ? "active" : ""}" data-life-action="asset-filter" data-filter="${esc(value)}">${esc(label)}<em>${Number(counts[value] || 0).toLocaleString()}</em></button>`).join("")}
    </div>`;
    const visibleProperties = properties.filter((property) => {
      if (state.assetFilter === "all") return true;
      if (state.assetFilter === "owned") return String(property.tenure || "owned") === "owned";
      if (state.assetFilter === "lease") return String(property.tenure || "") === "lease";
      if (state.assetFilter === "construction") return Boolean(property.is_construction);
      return String(property.kind || "") === state.assetFilter;
    });
    if (!visibleProperties.length) {
      return summary + filterMarkup + `<div class="life-section-card">${emptyMarkup(t("life.properties.filter_empty"), "house")}</div>`;
    }
    const cards = visibleProperties.map((property) => {
      const kind = String(property.kind || "residential");
      const modes = propertyModeChoices(kind, property);
      const mode = modes.includes(String(property.mode || "")) ? String(property.mode) : modes[0];
      const income = property.income_breakdown || {};
      const pending = Number(property.pending_income || 0);
      const parking = kind === "garage";
      const managed = kind === "commercial" || kind === "industrial";
      const icon = parking ? "warehouse" : kind === "industrial" ? "factory" : kind === "commercial" ? "store" : "house";
      const level = Math.max(1, Number(property.level || income.level || 1));
      const monthly = Number(income.monthly_income ?? property.monthly_income ?? 0);
      const daily = Number(income.daily_income ?? property.daily_income ?? 0);
      const gross = Number(income.monthly_gross || 0);
      const payroll = Number(income.monthly_payroll || 0);
      const employees = Number(income.employees ?? property.employees ?? 0);
      const employeeMin = Number(income.employee_min || 0);
      const employeeMax = Number(income.employee_max || 0);
      const employeeOptimal = Number(income.employee_optimal || 0);
      const upgradeCost = Number(property.upgrade_cost || 0);
      const garageRented = parking && mode === "rent";
      const tenure = String(property.tenure || "owned");
      const leased = tenure === "lease";
      const acquisitionLabel = leased ? t("life.properties.lease_prepaid") : t("life.purchase_value");
      const acquisitionAmount = leased ? Number(property.lease?.prepaid_rent || 0) : Number(property.purchase_price || 0);
      const leaseStatus = String(property.lease?.status || (leased ? "active" : ""));
      const leaseExpired = leased && leaseStatus !== "active";
      const isConstruction = Boolean(property.is_construction);
      const construction = property.construction || null;
      const constructionKind = String(construction?.kind || "");
      const constructionDays = Number(property.construction_days_remaining || 0);
      const constructionTotal = Math.max(1, Number(construction?.duration_days || constructionDays || 1));
      const constructionProgress = Math.max(0, Math.min(100, ((constructionTotal - constructionDays) / constructionTotal) * 100));
      const frozen = isConstruction || leaseExpired;
      const modeBusy = state.busy === `mode:${property.id}`;
      const configBusy = state.busy === `config:${property.id}`;
      const upgradeBusy = state.busy === `upgrade:${property.id}`;
      const renewBusy = state.busy === `renew:${property.id}`;
      const releaseBusy = state.busy === `release:${property.id}`;
      const businessQuotes = new Map((property.business_setup_quotes || []).map((row) => [String(row.id), row]));
      const selectedQuote = businessQuotes.get(String(property.business_type || "")) || {cost:0, days:0};
      const businessOptions = managed ? propertyBusinessEntries(kind).map((row) => {
        const quote = businessQuotes.get(String(row.id)) || {cost:0, days:0};
        return `<option value="${esc(row.id)}" data-setup-cost="${Number(quote.cost || 0)}" data-setup-days="${Number(quote.days || 0)}" ${String(row.id) === String(property.business_type) ? "selected" : ""}>${esc(businessName(row))}</option>`;
      }).join("") : "";
      const employeeHint = employeeMax > 0
        ? t("life.properties.employee_range", {min:employeeMin, max:employeeMax, optimal:employeeOptimal})
        : t("life.properties.employee_none");
      const stats = parking
        ? `<div><small>${esc(t("life.market_value"))}</small><strong>${esc(money(property.market_value))}</strong></div>
          <div><small>${esc(t("life.monthly"))} · ${esc(propertyModeLabel(mode))}</small><strong>${esc(money(monthly))}</strong></div>
          <div><small>${esc(t("life.garage.parking_spaces"))}</small><strong>${garageRented ? 0 : Number(property.parking_spaces || 0)}</strong></div>
          <div><small>${esc(acquisitionLabel)}</small><strong>${esc(money(acquisitionAmount))}</strong></div>`
        : `<div><small>${esc(t("life.market_value"))}</small><strong>${esc(money(property.market_value))}</strong></div>
          <div><small>${esc(t("life.monthly"))} · ${esc(propertyModeLabel(mode))}</small><strong>${esc(money(monthly))}</strong></div>
          <div><small>${esc(t("life.properties.level"))}</small><strong>LV.${level}</strong></div>
          <div><small>${esc(acquisitionLabel)}</small><strong>${esc(money(acquisitionAmount))}</strong></div>`;
      const modeMarkup = modes.length > 1 ? `<div class="life-mode-switch" role="group" aria-label="${esc(t("life.properties.management"))}">
            ${modes.map((choice) => `<button type="button" class="${mode === choice ? "active" : ""}" data-life-action="property-mode" data-asset-id="${esc(property.id)}" data-mode="${esc(choice)}" ${frozen || modeBusy || configBusy ? "disabled" : ""}>${esc(propertyModeLabel(choice))}</button>`).join("")}
          </div>` : "";
      const configMarkup = managed ? `<section class="life-property-config">
          <header class="life-config-head">
            <div class="life-config-title"><i data-lucide="clipboard-list"></i><span>${esc(t("life.properties.business_plan"))}</span></div>
            <p>${esc(t("life.properties.business_plan_note"))}</p>
          </header>
          <div class="life-config-fields">
            <label class="life-field"><span>${esc(kind === "commercial" ? t("life.properties.business_type") : t("life.properties.industry_type"))}</span><select data-life-property-business="${esc(property.id)}" ${!configBusy && !frozen ? "" : "disabled"}>${businessOptions}</select></label>
            <label class="life-field"><span>${esc(t("life.properties.employees"))}</span><input type="number" min="${employeeMin}" max="${Math.max(employeeMin, employeeMax)}" step="1" value="${employees}" data-life-property-employees="${esc(property.id)}" ${!configBusy && !frozen ? "" : "disabled"}><small>${esc(employeeHint)}</small></label>
          </div>
          <div class="life-config-submit">
            <div class="life-business-quote"><span><small>${esc(t("life.properties.business_setup_cost"))}</small><b data-life-business-cost>${esc(money(selectedQuote.cost || 0))}</b></span><span><small>${esc(t("life.properties.business_setup_days"))}</small><b data-life-business-days>${Number(selectedQuote.days || 0)}</b></span></div>
            <button type="button" class="life-primary" data-life-action="save-property-config" data-asset-id="${esc(property.id)}" ${!frozen && !configBusy ? "" : "disabled"}><i data-lucide="${configBusy ? "loader-circle" : "briefcase-business"}"></i>${esc(configBusy ? t("life.properties.saving_config") : t("life.properties.submit_business"))}</button>
          </div>
        </section>` : "";
      const incomeMarkup = isConstruction ? `<div class="life-property-mode-note warning"><i data-lucide="hard-hat"></i><span>${esc(t("life.properties.construction_income_paused"))}</span></div>`
        : mode === "self" ? `<div class="life-property-mode-note"><i data-lucide="home"></i><span>${esc(parking ? t("life.properties.garage_self_note") : t("life.properties.self_use_note"))}</span></div>`
        : mode === "vacant" ? `<div class="life-property-mode-note warning"><i data-lucide="store"></i><span>${esc(t("life.properties.vacant_note"))}</span></div>`
        : `<div class="life-income-breakdown">
            <span><small>${esc(t("life.properties.gross_income"))}</small><b>${esc(money(gross))}</b></span>
            <span><small>${esc(t("life.properties.payroll"))}</small><b>${esc(money(payroll))}</b></span>
            <span class="net"><small>${esc(t("life.properties.net_income"))}</small><b>${esc(money(monthly))}</b></span>
            <span class="daily"><small>${esc(t("life.daily"))}</small><b>${esc(money(daily))}</b></span>
          </div>`;
      const garageNote = garageRented ? `<div class="life-property-mode-note warning"><i data-lucide="lock-keyhole"></i><span>${esc(t("life.properties.garage_rented"))}</span></div>` : "";
      const upgradeMarkup = parking ? "" : `<button type="button" class="life-secondary" data-life-action="upgrade-property" data-asset-id="${esc(property.id)}" ${upgradeCost <= 0 || upgradeBusy || frozen ? "disabled" : ""}><i data-lucide="${upgradeBusy ? "loader-circle" : upgradeCost > 0 ? "hammer" : "badge-check"}"></i>${esc(upgradeCost > 0 ? t("life.properties.upgrade_cost_days", {cost:money(upgradeCost), days:Number(property.upgrade_days || 0)}) : t("life.properties.max_level"))}</button>`;
      const constructionMarkup = isConstruction ? `<section class="life-construction-panel">
          <header><span><i data-lucide="hard-hat"></i>${esc(constructionKind === "upgrade" ? t("life.properties.construction_upgrade") : t("life.properties.construction_business"))}</span><b>${esc(t("life.properties.construction_remaining", {days:constructionDays}))}</b></header>
          <div class="life-construction-track"><span style="width:${constructionProgress.toFixed(1)}%"></span></div>
          <small>${esc(t("life.properties.construction_until", {date:dayDate(construction?.end_day)}))}</small>
        </section>` : "";
      const leaseStatusLabel = leaseExpired ? t("life.properties.lease_expired") : t("life.properties.lease_active");
      const renewOptions = (property.lease_renew_options || []).map((row) => `<option value="${Number(row.days)}">${esc(t("life.days", {count:Number(row.days)}))} · ${esc(money(row.amount))}</option>`).join("");
      const leaseMarkup = leased ? `<section class="life-lease-panel ${leaseExpired ? "expired" : ""}">
          <header><span><i data-lucide="${leaseExpired ? "calendar-x" : "file-signature"}"></i>${esc(leaseStatusLabel)}</span><b>${esc(t("life.properties.lease_remaining", {days:Number(property.lease_days_remaining || 0)}))}</b></header>
          <div class="life-lease-facts">
            <span><small>${esc(t("life.properties.lease_end"))}</small><b>${esc(dayDate(property.lease?.end_day))}</b></span>
            <span><small>${esc(t("life.properties.lease_deposit"))}</small><b>${esc(money(property.lease?.deposit || 0))}</b></span>
            <span><small>${esc(t("life.properties.lease_prepaid"))}</small><b>${esc(money(property.lease?.prepaid_rent || 0))}</b></span>
          </div>
          <div class="life-lease-actions">
            <label class="life-field"><span>${esc(t("life.properties.lease_renew_days"))}</span><select data-life-lease-renew-days="${esc(property.id)}">${renewOptions}</select></label>
            <button type="button" class="life-secondary" data-life-action="renew-lease" data-asset-id="${esc(property.id)}" ${renewBusy ? "disabled" : ""}><i data-lucide="${renewBusy ? "loader-circle" : "calendar-plus"}"></i>${esc(t("life.properties.lease_renew"))}</button>
            <button type="button" class="life-danger-button" data-life-action="release-lease" data-asset-id="${esc(property.id)}" ${releaseBusy || isConstruction ? "disabled" : ""}><i data-lucide="${releaseBusy ? "loader-circle" : "log-out"}"></i>${esc(t("life.properties.lease_release"))}</button>
          </div>
        </section>` : "";
      const footerMeta = leased
        ? `<span class="life-acquired">${esc(t("life.properties.lease_started"))} ${esc(dayDate(property.lease?.start_day))}</span>`
        : `<span class="life-acquired">${esc(t("life.acquired"))} ${esc(dayDate(property.acquired_day))}</span>`;
      const sellButton = leased ? "" : `<button type="button" class="life-danger-button" data-life-action="sell-property" data-asset-id="${esc(property.id)}" ${state.busy === `sell:${property.id}` || frozen ? "disabled" : ""}><i data-lucide="${state.busy === `sell:${property.id}` ? "loader-circle" : "banknote-arrow-up"}"></i>${esc(t("life.sell"))}</button>`;
      return {property, html: `<article class="life-property-card ${isConstruction ? "under-construction" : ""} ${leased ? "leased-asset" : ""}">
        <header><span class="life-property-icon life-kind-${esc(kind)}"><i data-lucide="${icon}"></i></span><div><small>${esc(kindLabel(kind))} · ${esc(leased ? t("life.properties.tenure_lease") : t("life.properties.tenure_owned"))}</small><h3>${esc(propertyName(property))}</h3><p><i data-lucide="map-pin"></i>${esc(cityName(property))} · ${esc(districtName(property))}</p></div><div class="life-property-badges"><span class="life-kind-pill life-kind-${esc(kind)}">${Number(property.area_sqm).toLocaleString()} m²</span>${isConstruction ? `<span class="life-status-pill construction">${esc(t("life.properties.construction"))}</span>` : leaseExpired ? `<span class="life-status-pill expired">${esc(t("life.properties.lease_expired"))}</span>` : ""}</div></header>
        <div class="life-property-stats">${stats}</div>
        ${constructionMarkup}
        ${leaseMarkup}
        ${configMarkup}
        ${incomeMarkup}
        ${garageNote}
        ${!parking && pending > 0 ? `<div class="life-pending-income"><i data-lucide="coins"></i><span>${esc(t("life.properties.pending"))}</span><strong>${esc(money(pending))}</strong><small>${esc(t("life.properties.pending_for", {days:Number(property.pending_days || 0)}))}</small></div>` : ""}
        <footer class="life-property-footer">
          <div class="life-property-actions">${modeMarkup}${upgradeMarkup}</div>
          <div class="life-property-deed">${footerMeta}${sellButton}</div>
        </footer>
      </article>`};
    });
    const cityGroups = new Map();
    for (const card of cards) {
      const property = card.property || {};
      const cityKey = String(property.city_id || cityName(property) || "unknown");
      const districtKey = String(property.district_id || districtName(property) || "unknown");
      let city = cityGroups.get(cityKey);
      if (!city) {
        city = {
          key: cityKey, label: cityName(property) || t("life.properties.unknown_city"),
          count: 0, value: 0, districts: new Map(),
        };
        cityGroups.set(cityKey, city);
      }
      let district = city.districts.get(districtKey);
      if (!district) {
        district = {
          key: districtKey, label: districtName(property) || t("life.properties.unknown_district"),
          count: 0, value: 0, cards: [],
        };
        city.districts.set(districtKey, district);
      }
      const value = Number(property.market_value || 0);
      city.count += 1; city.value += value;
      district.count += 1; district.value += value; district.cards.push(card.html);
    }
    const expanded = state.assetExpanded;
    const manyAssets = visibleProperties.length > 24;
    const isOpen = (key) => {
      if (state.assetExpandAll === true) return true;
      if (state.assetExpandAll === false) return false;
      if (expanded.has(key) || expanded.has(`open:${key}`)) return true;
      if (expanded.has(`closed:${key}`)) return false;
      return !manyAssets;
    };
    const cityMarkup = [...cityGroups.values()].map((city) => {
      const cityKey = `city:${city.key}`;
      const cityOpen = isOpen(cityKey);
      const districts = [...city.districts.values()].map((district) => {
        const districtKey = `${cityKey}:district:${district.key}`;
        const districtOpen = cityOpen && isOpen(districtKey);
        return `<section class="life-asset-district ${districtOpen ? "is-open" : ""}">
          <button type="button" class="life-asset-district-head" data-life-action="asset-toggle-group" data-group="${esc(districtKey)}" aria-expanded="${districtOpen}">
            <i data-lucide="${districtOpen ? "chevron-down" : "chevron-right"}"></i>
            <span>${esc(district.label)}</span><b>${Number(district.count).toLocaleString()}</b><small>${esc(money(district.value))}</small>
          </button>
          ${districtOpen ? `<div class="life-property-grid life-asset-district-grid">${district.cards.join("")}</div>` : ""}
        </section>`;
      }).join("");
      return `<section class="life-asset-city ${cityOpen ? "is-open" : ""}">
        <button type="button" class="life-asset-city-head" data-life-action="asset-toggle-group" data-group="${esc(cityKey)}" aria-expanded="${cityOpen}">
          <i data-lucide="${cityOpen ? "chevron-down" : "chevron-right"}"></i>
          <span><small>${esc(t("life.properties.city_group"))}</small><strong>${esc(city.label)}</strong></span>
          <b>${Number(city.count).toLocaleString()}</b><small>${esc(money(city.value))}</small>
        </button>
        ${cityOpen ? `<div class="life-asset-districts">${districts}</div>` : ""}
      </section>`;
    }).join("");
    const allExpanded = [...cityGroups.values()].every((city) => isOpen(`city:${city.key}`));
    return summary + filterMarkup + `<div class="life-asset-group-toolbar"><span>${esc(t("life.properties.grouped_by_city", {cities: cityGroups.size, properties: visibleProperties.length}))}</span><button type="button" class="life-secondary" data-life-action="asset-toggle-all" data-expand="${allExpanded ? "0" : "1"}"><i data-lucide="${allExpanded ? "chevrons-up" : "chevrons-down"}"></i>${esc(allExpanded ? t("life.properties.collapse_all") : t("life.properties.expand_all"))}</button></div><div class="life-asset-city-list">${cityMarkup}</div>`;
  }

  function renderGaragePage() {
    const data = state.data;
    const vehicles = data.vehicles || [];
    const garages = data.garages || [];
    const selected = findGarage(state.garage.selectedId) || garages[0] || null;
    const selectedRows = selected
      ? vehicles.filter((vehicle) => String(vehicle.garage_id) === String(selected.id))
      : [];
    const groupOrder = [
      ["club", "club"], ["storage", "storage"], ["standalone", "standalone"], ["property", "property"], ["legacy", "legacy"],
    ];
    const directory = groupOrder.map(([category]) => {
      const rows = garages.filter((garage) => garageCategory(garage) === category);
      if (!rows.length) return "";
      const buttons = rows.map((garage) => {
        const usage = Math.min(100, Number(garage.used || 0) / Math.max(1, Number(garage.capacity || 0)) * 100);
        const place = garageLocation(garage);
        return `<button type="button" class="life-garage-nav ${String(garage.id) === String(selected?.id) ? "active" : ""}" data-life-action="select-garage" data-garage-id="${esc(garage.id)}">
          <span class="life-garage-nav-icon"><i data-lucide="${garageIcon(garage)}"></i></span>
          <span class="life-garage-nav-copy"><small>${esc(garageCategoryLabel(garage))}</small><strong>${esc(garageLabel(garage))}</strong>${place ? `<em>${esc(place)}</em>` : ""}</span>
          <b>${Number(garage.used || 0)} / ${Number(garage.capacity || 0)}</b>
          <span class="life-garage-nav-track"><i style="width:${usage}%"></i></span>
        </button>`;
      }).join("");
      return `<section class="life-garage-group"><header><span>${esc(t(`life.garage.group_${category}`))}</span><b>${rows.length}</b></header>${buttons}</section>`;
    }).join("");
    let detail = `<section class="life-garage-detail">${emptyMarkup(t("life.garage.no_selection"), "warehouse")}</section>`;
    if (selected) {
      const capacity = Math.max(0, Number(selected.capacity || 0));
      const used = Math.max(0, Number(selected.used || 0));
      const free = Math.max(0, capacity - used);
      const shownSlots = Math.min(capacity, 48);
      const bays = Array.from({length: shownSlots}, (_unused, index) => `<span class="life-parking-bay ${index < used ? "occupied" : "empty"}" title="${esc(index < used ? t("life.used") : t("life.free"))}">${index < used ? '<i data-lucide="car-front"></i>' : ""}</span>`).join("");
      const overflow = capacity > shownSlots
        ? `<span class="life-parking-overflow">+${capacity - shownSlots}</span>`
        : "";
      const place = garageLocation(selected);
      const source = selected.property_id
        ? t("life.garage.source_asset", {kind:kindLabel(findProperty(selected.property_id)?.kind || "garage")})
        : garageCategoryLabel(selected);
      const carList = selectedRows.length
        ? selectedRows.map(vehicleCard).join("")
        : `<div class="life-garage-empty">${emptyMarkup(t("life.garage.no_vehicles"), "car-front")}</div>`;
      const duplicateCandidates = duplicateVehicleCandidates(selectedRows);
      detail = `<section class="life-garage-detail">
        <header class="life-garage-detail-head">
          <span class="life-garage-badge"><i data-lucide="${garageIcon(selected)}"></i></span>
          <div><small>${esc(source)}</small><h2>${esc(garageLabel(selected))}</h2>${place ? `<p><i data-lucide="map-pin"></i>${esc(place)}</p>` : ""}</div>
          <div class="life-garage-capacity"><strong>${used} / ${capacity}</strong><span>${free} ${esc(t("life.free"))}</span></div>
          <div class="life-garage-detail-actions">
            <button type="button" class="life-secondary life-garage-bulk-open" data-life-action="open-garage-bulk"><i data-lucide="list-checks"></i>${esc(t("life.garage.bulk_open"))}</button>
            <button type="button" class="life-secondary life-garage-duplicate-open" data-life-action="sell-duplicates" data-garage-id="${esc(selected.id)}" ${duplicateCandidates.length && !state.busy ? "" : "disabled"} title="${esc(t("life.garage.duplicate_hint"))}"><i data-lucide="copy-check"></i>${esc(t("life.garage.duplicate_sell", {count:duplicateCandidates.length}))}</button>
          </div>
        </header>
        <div class="life-capacity-track"><span style="width:${Math.min(100, used / Math.max(1, capacity) * 100)}%"></span></div>
        <div class="life-parking-overview"><div class="life-parking-bays">${bays}${overflow}</div><small>${esc(t("life.garage.bay_hint", {capacity, free}))}</small></div>
        <div class="life-vehicle-list">${carList}</div>
      </section>`;
    }
    return `
      <div class="life-garage-workspace">
        <aside class="life-garage-directory"><div class="life-garage-directory-head"><small>${esc(t("life.garage.overview"))}</small><strong>${Number(data.garage_summary?.used || 0)} / ${Number(data.garage_summary?.capacity || 0)}</strong><span>${esc(t("life.garage.empty_hint"))}</span></div>${directory}</aside>
        ${detail}
      </div>`;
  }

  function rarityClass(value) {
    return String(value || "common").trim().toLowerCase().replace(/\s+/g, "-");
  }

  function collectionOwnedMap() {
    return new Map((state.data?.collection?.cars || []).map((row) => [String(row.catalog_id), row]));
  }

  function collectionTabCounts() {
    const cars = dealerCatalog();
    const owned = collectionOwnedMap();
    const legendary = cars.filter((car) => ["legendary", "forza edition", "donut edition"].includes(String(car.rarity || "").toLowerCase()));
    return {
      all: cars.length,
      manufacturers: new Set(cars.map((car) => String(car.manufacturer || "")).filter(Boolean)).size,
      legendary: legendary.length,
      owned: owned.size,
    };
  }

  function paintCollectionButton() {
    const unique = Number(state.data?.collection?.summary?.unique || 0);
    const total = Number(state.data?.collection?.summary?.catalog_size || dealerCatalog().length || 0);
    for (const buttonId of ["life-collection-open", "life-gacha-collection-open"]) {
      const button = document.getElementById(buttonId);
      if (button) button.disabled = !state.data;
    }
    for (const countId of ["life-collection-open-count", "life-gacha-collection-open-count"]) {
      const count = document.getElementById(countId);
      if (count) count.textContent = total ? `${unique} / ${total}` : "—";
    }
  }

  async function openCollectionDialog() {
    const dialog = document.getElementById("life-collection-dialog");
    if (!dialog) return;
    if (!state.catalog) await refreshLife({catalog: true});
    for (const dialogId of ["life-storage-dialog", "life-gacha-history-dialog"]) {
      const other = document.getElementById(dialogId);
      if (other?.open) other.close();
    }
    paintCollectionDialog();
    if (dialog.open) return;
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
  }

  function closeCollectionDialog() {
    const dialog = document.getElementById("life-collection-dialog");
    if (!dialog) return;
    if (typeof dialog.close === "function") dialog.close();
    else dialog.removeAttribute("open");
  }

  function paintStorageButton() {
    const storage = findGarage("storage");
    const countText = storage
      ? `${Number(storage.used || 0)} / ${Number(storage.capacity || 10000)}`
      : "—";
    for (const buttonId of ["life-storage-open", "life-gacha-storage-open"]) {
      const button = document.getElementById(buttonId);
      if (button) button.disabled = !state.data;
    }
    for (const countId of ["life-storage-open-count", "life-gacha-storage-open-count"]) {
      const count = document.getElementById(countId);
      if (count) count.textContent = countText;
    }
    const daily = Number(state.data?.storage_rent?.daily_amount || 0);
    document.querySelectorAll("[data-life-storage-rent]").forEach((node) => {
      node.textContent = t("life.storage.daily_short", {amount:money(daily)});
    });
  }

  function storageGarageVehicles() {
    return (state.data?.vehicles || []).filter(
      (vehicle) => String(vehicle.garage_id) === "storage",
    );
  }

  function filteredStorageVehicles(vehicles = storageGarageVehicles()) {
    const query = String(state.storage.query || "").trim().toLocaleLowerCase();
    const specialRarities = new Set(["legendary", "forza edition", "donut edition"]);
    return vehicles.filter((vehicle) => {
      if (state.storage.manufacturer !== "all" && String(vehicle.manufacturer || "") !== state.storage.manufacturer) return false;
      if (state.storage.carClass !== "all" && String(vehicle.class || "") !== state.storage.carClass) return false;
      const rarity = String(vehicle.rarity || "").toLowerCase();
      if (state.storage.rarity === "special" && !specialRarities.has(rarity)) return false;
      if (state.storage.rarity !== "all" && state.storage.rarity !== "special" && rarity !== state.storage.rarity) return false;
      if (!query) return true;
      return `${vehicle.name || ""} ${vehicle.manufacturer || ""} ${Number(vehicle.year || 0)}`
        .toLocaleLowerCase().includes(query);
    }).sort((left, right) => (
      (CLASS_SORT[right.class] || 0) - (CLASS_SORT[left.class] || 0)
      || (RARITY_SORT[right.rarity] || 0) - (RARITY_SORT[left.rarity] || 0)
      || String(left.manufacturer || "").localeCompare(String(right.manufacturer || ""), window.FMODDI18n?.locale || "en-GB")
      || String(left.name || "").localeCompare(String(right.name || ""), window.FMODDI18n?.locale || "en-GB")
    ));
  }

  function storageVehicleRows(vehicles, allVehicles) {
    if (!allVehicles.length) return emptyMarkup(t("life.storage.empty"), "archive");
    if (!vehicles.length) return emptyMarkup(t("life.collection.no_matches"), "search-x");
    return `<div class="life-storage-list">${vehicles.map((vehicle) => `<label class="life-storage-row">
      <input type="checkbox" data-life-storage-select="${esc(vehicle.id)}" ${state.storage.selected.has(String(vehicle.id)) ? "checked" : ""}>
      <span class="life-storage-photo">${vehicleImageTag(vehicle.image, vehicle.name)}${vehicleClassBadge(vehicle.class)}</span>
      <span class="life-storage-copy"><small>${esc(vehicle.manufacturer)} · ${esc(rarityLabel(vehicle.rarity))}</small><strong>${esc(vehicle.name)}</strong><em>${Number(vehicle.year || 0)} · ${Number(vehicle.mileage_km || 0).toLocaleString()} km · ${esc(percent(vehicle.condition, 0))}</em></span>
      <strong class="life-storage-value">${esc(money(vehicle.market_value))}</strong>
    </label>`).join("")}</div>`;
  }

  function paintStorageResults() {
    const host = document.getElementById("life-storage-results");
    if (!host) return;
    const allVehicles = storageGarageVehicles();
    const vehicles = filteredStorageVehicles(allVehicles);
    host.innerHTML = storageVehicleRows(vehicles, allVehicles);
    const count = document.getElementById("life-storage-filter-count");
    if (count) count.textContent = `${vehicles.length} / ${allVehicles.length} ${t("life.vehicle")}`;
    bridge()?.renderIcons(host);
    scheduleVehicleImageHydration(host);
  }

  function paintStorageDialog() {
    const host = document.getElementById("life-storage-dialog-content");
    if (!host) return;
    const previousScrollTop = host.scrollTop;
    if (!state.data) {
      host.innerHTML = loadingMarkup();
      bridge()?.renderIcons(host);
      return;
    }
    const storage = findGarage("storage");
    const vehicles = storageGarageVehicles();
    const visibleVehicles = filteredStorageVehicles(vehicles);
    const vehicleIds = new Set(vehicles.map((vehicle) => String(vehicle.id)));
    for (const selectedId of state.storage.selected) {
      if (!vehicleIds.has(selectedId)) state.storage.selected.delete(selectedId);
    }
    const targets = (state.data.garages || []).filter(
      (garage) => String(garage.id) !== "storage",
    );
    if (!targets.some((garage) => String(garage.id) === String(state.storage.targetId))) {
      state.storage.targetId = String(
        (targets.find((garage) => Number(garage.free || 0) > 0) || targets[0] || {}).id || "",
      );
    }
    const target = findGarage(state.storage.targetId);
    const targetFree = Number(target?.free || 0);
    const selectedIds = [...state.storage.selected];
    const selectedVehicles = vehicles.filter((vehicle) => state.storage.selected.has(String(vehicle.id)));
    const allVisibleSelected = visibleVehicles.length > 0 && visibleVehicles.every(
      (vehicle) => state.storage.selected.has(String(vehicle.id)),
    );
    const selectedValue = selectedVehicles.reduce(
      (total, vehicle) => total + Math.max(0, Number(vehicle.market_value || 0)), 0,
    );
    const selectedFee = Math.round(selectedValue * 0.03 * 100) / 100;
    const selectedNet = Math.max(0, selectedValue - selectedFee);
    const storageDuplicates = duplicateVehicleCandidates(vehicles);
    const used = Number(storage?.used || vehicles.length);
    const capacity = Number(storage?.capacity || 10000);
    const rent = state.data?.storage_rent || {};
    const dailyRent = Number(rent.daily_amount || 0);
    const storedValue = Number(rent.stored_value || 0);
    const paidLifetime = Number(rent.paid_lifetime || 0);
    const targetOptions = targets.map((garage) => {
      const location = garageLocation(garage);
      const label = `${garageLabel(garage)}${location ? ` · ${location}` : ""}`;
      return `<option value="${esc(garage.id)}" ${String(garage.id) === String(state.storage.targetId) ? "selected" : ""}>${esc(label)} · ${Number(garage.free || 0)} ${esc(t("life.free"))}</option>`;
    }).join("");
    const manufacturers = [...new Set(vehicles.map((vehicle) => String(vehicle.manufacturer || "").trim()).filter(Boolean))]
      .sort((left, right) => left.localeCompare(right, window.FMODDI18n?.locale || "en-GB"));
    if (state.storage.manufacturer !== "all" && !manufacturers.includes(state.storage.manufacturer)) {
      state.storage.manufacturer = "all";
    }
    const manufacturerOptions = manufacturers.map((value) => `<option value="${esc(value)}" ${state.storage.manufacturer === value ? "selected" : ""}>${esc(value)}</option>`).join("");
    const classOptions = ["S2", "S1", "A", "B", "C", "D"].map((value) => `<option value="${value}" ${state.storage.carClass === value ? "selected" : ""}>${value}</option>`).join("");
    const rarityOptions = ["common", "rare", "epic", "legendary", "forza edition", "donut edition"].map((value) => `<option value="${esc(value)}" ${state.storage.rarity === value ? "selected" : ""}>${esc(rarityLabel(value))}</option>`).join("");
    host.innerHTML = `<div class="life-storage-overview"><div><small>${esc(t("life.storage.capacity"))}</small><strong>${used} / ${capacity}</strong><span>${esc(t("life.storage.capacity_hint"))}</span></div><div><small>${esc(t("life.storage.stored_value"))}</small><strong>${esc(money(storedValue))}</strong><span>${esc(t("life.storage.settled", {date:dayDate(rent.settled_day)}))}</span></div><div><small>${esc(t("life.storage.daily_rent"))}</small><strong>${esc(money(dailyRent))}</strong><span>${esc(t("life.storage.rent_hint", {rate:"1%"}))} · ${esc(t("life.storage.paid_lifetime", {amount:money(paidLifetime)}))}</span></div><div><small>${esc(t("life.storage.selected"))}</small><strong data-life-storage-selected-count>${selectedVehicles.length}</strong><span data-life-storage-selection-preview>${esc(t("life.storage.selection_preview", {value:money(selectedValue), net:money(selectedNet)}))}</span></div></div>
      <div class="life-storage-filterbar">
        <label class="life-search-field"><i data-lucide="search"></i><input type="search" data-life-storage-search value="${esc(state.storage.query)}" placeholder="${esc(t("life.collection.search"))}" aria-label="${esc(t("life.collection.search"))}" autocomplete="off"></label>
        <label class="life-field"><span>${esc(t("life.collection.manufacturers"))}</span><select data-life-storage-filter="manufacturer"><option value="all">${esc(t("life.collection.all_brands"))}</option>${manufacturerOptions}</select></label>
        <label class="life-field"><span>${esc(t("life.class"))}</span><select data-life-storage-filter="class"><option value="all">${esc(t("life.collection.all_classes"))}</option>${classOptions}</select></label>
        <label class="life-field"><span>${esc(t("life.rarity"))}</span><select data-life-storage-filter="rarity"><option value="all">${esc(t("life.collection.all_rarities"))}</option><option value="special" ${state.storage.rarity === "special" ? "selected" : ""}>${esc(t("life.collection.tab_legendary"))}</option>${rarityOptions}</select></label>
        <span id="life-storage-filter-count" class="life-storage-filter-count">${visibleVehicles.length} / ${vehicles.length} ${esc(t("life.vehicle"))}</span>
      </div>
      <div class="life-storage-toolbar">
        <button type="button" class="life-secondary" data-life-action="storage-select-all" data-life-storage-select-all ${visibleVehicles.length ? "" : "disabled"}><i data-lucide="${allVisibleSelected ? "square-x" : "list-checks"}"></i><span data-life-storage-select-all-label>${esc(allVisibleSelected ? t("life.storage.clear_selection") : t("life.storage.select_all"))}</span></button>
        <button type="button" class="life-secondary life-garage-duplicate-open" data-life-action="sell-duplicates" data-garage-id="storage" ${storageDuplicates.length && !state.busy ? "" : "disabled"} title="${esc(t("life.garage.duplicate_hint"))}"><i data-lucide="copy-check"></i><span data-life-duplicate-label>${esc(t("life.garage.duplicate_sell", {count:storageDuplicates.length}))}</span></button>
        <label class="life-field"><span>${esc(t("life.storage.target"))}</span><select data-life-storage-target ${targets.length ? "" : "disabled"}>${targetOptions || `<option value="">${esc(t("life.storage.no_target"))}</option>`}</select></label>
        <button type="button" class="life-primary" data-life-action="storage-move-selected" data-life-storage-move ${!selectedIds.length || !target || selectedIds.length > targetFree || state.busy ? "disabled" : ""}><i data-lucide="${state.busy === "storage-move" ? "loader-circle" : "move-right"}"></i><span data-life-storage-move-label>${esc(state.busy === "storage-move" ? t("life.loading") : t("life.storage.move_selected", {count:selectedVehicles.length}))}</span></button>
        <button type="button" class="life-danger-button" data-life-action="storage-sell-selected" data-life-storage-sell ${!selectedIds.length || state.busy ? "disabled" : ""}><i data-lucide="${state.busy === "storage-sell" ? "loader-circle" : "banknote-arrow-up"}"></i><span data-life-storage-sell-label>${esc(state.busy === "storage-sell" ? t("life.loading") : t("life.storage.sell_selected", {count:selectedVehicles.length}))}</span></button>
      </div>
      <p class="life-storage-warning" data-life-storage-warning ${target && selectedVehicles.length > targetFree ? "" : "hidden"}><i data-lucide="triangle-alert"></i><span data-life-storage-warning-label>${target && selectedVehicles.length > targetFree ? esc(t("life.storage.target_shortage", {count:selectedVehicles.length - targetFree})) : ""}</span></p>
      <div id="life-storage-results" class="life-storage-results"></div>`;
    host.scrollTop = previousScrollTop;
    bridge()?.renderIcons(host);
    paintStorageResults();
  }

  function refreshStorageSelectionUi() {
    const host = document.getElementById("life-storage-dialog-content");
    if (!host || !state.data) return;
    const scrollTop = host.scrollTop;
    const vehicles = storageGarageVehicles();
    const visible = filteredStorageVehicles(vehicles);
    const vehicleIds = new Set(vehicles.map((vehicle) => String(vehicle.id)));
    for (const selectedId of state.storage.selected) {
      if (!vehicleIds.has(selectedId)) state.storage.selected.delete(selectedId);
    }
    const selectedVehicles = vehicles.filter((vehicle) => state.storage.selected.has(String(vehicle.id)));
    const selectedValue = selectedVehicles.reduce(
      (total, vehicle) => total + Math.max(0, Number(vehicle.market_value || 0)), 0,
    );
    const selectedNet = Math.max(0, selectedValue - Math.round(selectedValue * 0.03 * 100) / 100);
    const target = findGarage(state.storage.targetId);
    const targetFree = Number(target?.free || 0);
    const allVisibleSelected = visible.length > 0 && visible.every(
      (vehicle) => state.storage.selected.has(String(vehicle.id)),
    );
    const count = host.querySelector("[data-life-storage-selected-count]");
    if (count) count.textContent = String(selectedVehicles.length);
    const preview = host.querySelector("[data-life-storage-selection-preview]");
    if (preview) preview.textContent = t("life.storage.selection_preview", {
      value:money(selectedValue), net:money(selectedNet),
    });
    const selectAll = host.querySelector("[data-life-storage-select-all]");
    if (selectAll) {
      selectAll.disabled = !visible.length;
      selectAll.innerHTML = `<i data-lucide="${allVisibleSelected ? "square-x" : "list-checks"}"></i><span data-life-storage-select-all-label>${esc(allVisibleSelected ? t("life.storage.clear_selection") : t("life.storage.select_all"))}</span>`;
      bridge()?.renderIcons(selectAll);
    }
    const move = host.querySelector("[data-life-storage-move]");
    if (move) {
      move.disabled = !selectedVehicles.length || !target
        || selectedVehicles.length > targetFree || Boolean(state.busy);
      const label = move.querySelector("[data-life-storage-move-label]");
      if (label) label.textContent = state.busy === "storage-move"
        ? t("life.loading") : t("life.storage.move_selected", {count:selectedVehicles.length});
    }
    const sell = host.querySelector("[data-life-storage-sell]");
    if (sell) {
      sell.disabled = !selectedVehicles.length || Boolean(state.busy);
      const label = sell.querySelector("[data-life-storage-sell-label]");
      if (label) label.textContent = state.busy === "storage-sell"
        ? t("life.loading") : t("life.storage.sell_selected", {count:selectedVehicles.length});
    }
    const warning = host.querySelector("[data-life-storage-warning]");
    if (warning) {
      const shortage = Boolean(target && selectedVehicles.length > targetFree);
      warning.hidden = !shortage;
      const label = warning.querySelector("[data-life-storage-warning-label]");
      if (label) label.textContent = shortage
        ? t("life.storage.target_shortage", {count:selectedVehicles.length - targetFree}) : "";
    }
    host.scrollTop = scrollTop;
  }

  async function openStorageDialog() {
    const dialog = document.getElementById("life-storage-dialog");
    if (!dialog) return;
    if (dialog.parentElement !== document.body) {
      dialog.classList.add("life-page");
      document.body.appendChild(dialog);
    }
    paintStorageDialog();
    if (dialog.open) return;
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
  }

  function closeStorageDialog() {
    const dialog = document.getElementById("life-storage-dialog");
    if (!dialog) return;
    if (typeof dialog.close === "function") dialog.close();
    else dialog.removeAttribute("open");
    // Moving cars out of storage changes free garage spaces behind the dialog.
    // Repaint now so gacha draw buttons update without waiting for the next poll.
    paint();
  }

  function garageBulkSource() {
    return findGarage(state.garage.selectedId)
      || (state.data?.garages || []).find((garage) => garageCategory(garage) === "club")
      || (state.data?.garages || [])[0]
      || null;
  }

  function garageBulkVehicles(source = garageBulkSource()) {
    if (!source) return [];
    return (state.data?.vehicles || []).filter(
      (vehicle) => String(vehicle.garage_id) === String(source.id),
    );
  }

  function duplicateVehicleCandidates(vehicles) {
    const groups = new Map();
    for (const vehicle of vehicles || []) {
      const catalogId = String(vehicle.catalog_id || "").trim();
      const key = catalogId || [
        String(vehicle.manufacturer || "").trim().toLocaleLowerCase(),
        String(vehicle.name || "").trim().toLocaleLowerCase(),
        String(vehicle.year || ""),
      ].join("|");
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(vehicle);
    }
    const duplicates = [];
    for (const group of groups.values()) {
      if (group.length < 2) continue;
      const ranked = [...group].sort((left, right) => (
        Number(right.market_value || right.value || 0) - Number(left.market_value || left.value || 0)
        || Number(right.purchase_day || 0) - Number(left.purchase_day || 0)
        || String(left.id || "").localeCompare(String(right.id || ""))
      ));
      duplicates.push(...ranked.slice(1));
    }
    return duplicates;
  }

  function filteredGarageBulkVehicles(vehicles = garageBulkVehicles()) {
    const query = String(state.garageBulk.query || "").trim().toLocaleLowerCase();
    return vehicles.filter((vehicle) => {
      if (state.garageBulk.manufacturer !== "all"
        && String(vehicle.manufacturer || "") !== state.garageBulk.manufacturer) return false;
      if (state.garageBulk.carClass !== "all"
        && String(vehicle.class || "") !== state.garageBulk.carClass) return false;
      if (state.garageBulk.rarity !== "all"
        && String(vehicle.rarity || "").toLowerCase() !== state.garageBulk.rarity) return false;
      if (!query) return true;
      return `${vehicle.name || ""} ${vehicle.manufacturer || ""} ${Number(vehicle.year || 0)}`
        .toLocaleLowerCase().includes(query);
    }).sort((left, right) => (
      (CLASS_SORT[right.class] || 0) - (CLASS_SORT[left.class] || 0)
      || (RARITY_SORT[right.rarity] || 0) - (RARITY_SORT[left.rarity] || 0)
      || String(left.manufacturer || "").localeCompare(String(right.manufacturer || ""), window.FMODDI18n?.locale || "en-GB")
      || String(left.name || "").localeCompare(String(right.name || ""), window.FMODDI18n?.locale || "en-GB")
    ));
  }

  function renderGarageBulkDialog() {
    const host = document.getElementById("life-garage-bulk-content");
    const source = garageBulkSource();
    if (!host || !source) return;
    const shell = host.closest(".life-collection-dialog-shell");
    shell?.querySelectorAll(".life-garage-bulk-footer").forEach((node) => node.remove());
    const vehicles = garageBulkVehicles(source);
    const visible = filteredGarageBulkVehicles(vehicles);
    const bulkDuplicates = duplicateVehicleCandidates(vehicles);
    const ids = new Set(vehicles.map((vehicle) => String(vehicle.id)));
    for (const selectedId of state.garageBulk.selected) {
      if (!ids.has(selectedId)) state.garageBulk.selected.delete(selectedId);
    }
    const selectedVehicles = vehicles.filter(
      (vehicle) => state.garageBulk.selected.has(String(vehicle.id)),
    );
    const allVisibleSelected = visible.length > 0 && visible.every(
      (vehicle) => state.garageBulk.selected.has(String(vehicle.id)),
    );
    const targets = (state.data?.garages || []).filter(
      (garage) => String(garage.id) !== String(source.id),
    );
    if (!targets.some((garage) => String(garage.id) === String(state.garageBulk.targetId))) {
      state.garageBulk.targetId = String(
        (targets.find((garage) => Number(garage.free || 0) > 0) || targets[0] || {}).id || "",
      );
    }
    const target = findGarage(state.garageBulk.targetId);
    const targetFree = Number(target?.free || 0);
    const selectedValue = selectedVehicles.reduce(
      (total, vehicle) => total + Math.max(0, Number(vehicle.market_value || 0)), 0,
    );
    const selectedFee = Math.round(selectedValue * 0.03 * 100) / 100;
    const selectedNet = Math.max(0, selectedValue - selectedFee);
    const manufacturers = [...new Set(vehicles.map((vehicle) => String(vehicle.manufacturer || "").trim()).filter(Boolean))]
      .sort((left, right) => left.localeCompare(right, window.FMODDI18n?.locale || "en-GB"));
    const classes = [...new Set(vehicles.map((vehicle) => String(vehicle.class || "").trim()).filter(Boolean))]
      .sort((left, right) => (CLASS_SORT[right] || 0) - (CLASS_SORT[left] || 0));
    const rarities = [...new Set(vehicles.map((vehicle) => String(vehicle.rarity || "").trim().toLowerCase()).filter(Boolean))]
      .sort((left, right) => (RARITY_SORT[right] || 0) - (RARITY_SORT[left] || 0));
    const targetOptions = targets.map((garage) => {
      const location = garageLocation(garage);
      const label = `${garageLabel(garage)}${location ? ` · ${location}` : ""}`;
      return `<option value="${esc(garage.id)}" ${String(garage.id) === String(state.garageBulk.targetId) ? "selected" : ""} ${Number(garage.free || 0) <= 0 ? "disabled" : ""}>${esc(label)} · ${Number(garage.free || 0)} ${esc(t("life.free"))}</option>`;
    }).join("");
    const rows = visible.map((vehicle) => `<label class="life-storage-row">
      <input type="checkbox" data-life-garage-bulk-select="${esc(vehicle.id)}" ${state.garageBulk.selected.has(String(vehicle.id)) ? "checked" : ""}>
      <span class="life-storage-photo">${vehicleImageTag(vehicle.image, vehicle.name)}${vehicleClassBadge(vehicle.class)}</span>
      <span class="life-storage-copy"><small>${esc(vehicle.manufacturer)} · ${esc(rarityLabel(vehicle.rarity))}</small><strong>${esc(vehicle.name)}</strong><em>${Number(vehicle.year || 0)} · ${Number(vehicle.mileage_km || 0).toLocaleString()} km · ${esc(percent(vehicle.condition, 0))}</em></span>
      <strong class="life-storage-value">${esc(money(vehicle.market_value))}</strong>
    </label>`).join("");
    host.innerHTML = `<div class="life-bulk-summary"><span><small>${esc(t("life.garage.bulk_source"))}</small><strong>${esc(garageLabel(source))}</strong></span><span><small>${esc(t("life.garage.bulk_in_garage"))}</small><strong>${vehicles.length}</strong></span><span><small>${esc(t("life.garage.bulk_selected"))}</small><strong data-life-garage-bulk-selected-count>${selectedVehicles.length}</strong></span></div>
      <div class="life-garage-bulk-filters">
        <label class="life-search-field"><i data-lucide="search"></i><input type="search" data-life-garage-bulk-search value="${esc(state.garageBulk.query)}" placeholder="${esc(t("life.collection.search"))}" aria-label="${esc(t("life.collection.search"))}" autocomplete="off"></label>
        <label class="life-field"><span>${esc(t("life.collection.manufacturers"))}</span><select data-life-garage-bulk-filter="manufacturer"><option value="all">${esc(t("life.collection.all_brands"))}</option>${manufacturers.map((value) => `<option value="${esc(value)}" ${state.garageBulk.manufacturer === value ? "selected" : ""}>${esc(value)}</option>`).join("")}</select></label>
        <label class="life-field"><span>${esc(t("life.class"))}</span><select data-life-garage-bulk-filter="class"><option value="all">${esc(t("life.collection.all_classes"))}</option>${classes.map((value) => `<option value="${value}" ${state.garageBulk.carClass === value ? "selected" : ""}>${value}</option>`).join("")}</select></label>
        <label class="life-field"><span>${esc(t("life.rarity"))}</span><select data-life-garage-bulk-filter="rarity"><option value="all">${esc(t("life.collection.all_rarities"))}</option>${rarities.map((value) => `<option value="${esc(value)}" ${state.garageBulk.rarity === value ? "selected" : ""}>${esc(rarityLabel(value))}</option>`).join("")}</select></label>
      </div>
      <div class="life-garage-bulk-toolbar"><button type="button" class="life-secondary" data-life-action="garage-bulk-select-all" data-life-garage-bulk-select-all ${visible.length ? "" : "disabled"}><i data-lucide="${allVisibleSelected ? "square-x" : "list-checks"}"></i><span data-life-garage-bulk-select-label>${esc(allVisibleSelected ? t("life.storage.clear_selection") : t("life.storage.select_all"))}</span></button><button type="button" class="life-secondary life-garage-duplicate-open" data-life-action="sell-duplicates" data-garage-id="${esc(source.id)}" ${bulkDuplicates.length && !state.busy ? "" : "disabled"} title="${esc(t("life.garage.duplicate_hint"))}"><i data-lucide="copy-check"></i><span>${esc(t("life.garage.duplicate_sell", {count:bulkDuplicates.length}))}</span></button><span class="life-storage-filter-count">${visible.length} / ${vehicles.length} ${esc(t("life.vehicle"))}</span></div>
      <div class="life-garage-bulk-list-scroll"><div class="life-storage-results"><div class="life-storage-list">${rows || emptyMarkup(t("life.collection.no_matches"), "search-x")}</div></div></div>
      <div class="life-garage-bulk-footer">
        <div class="life-bulk-metrics"><span><small>${esc(t("life.garage.bulk_value"))}</small><strong data-life-garage-bulk-value>${esc(money(selectedValue))}</strong></span><span><small>${esc(t("life.garage.bulk_net"))}</small><strong data-life-garage-bulk-net>${esc(money(selectedNet))}</strong></span></div>
        <div class="life-garage-bulk-toolbar"><label class="life-field"><span>${esc(t("life.storage.target"))}</span><select data-life-garage-bulk-target ${targets.length ? "" : "disabled"}>${targetOptions || `<option value="">${esc(t("life.storage.no_target"))}</option>`}</select></label><button type="button" class="life-primary" data-life-action="garage-bulk-move" data-life-garage-bulk-move ${!selectedVehicles.length || !target || selectedVehicles.length > targetFree || selectedVehicles.length > 100 || state.busy ? "disabled" : ""}><i data-lucide="move-right"></i><span data-life-garage-bulk-move-label>${esc(t("life.storage.move_selected", {count:selectedVehicles.length}))}</span></button><button type="button" class="life-danger-button" data-life-action="garage-bulk-sell" data-life-garage-bulk-sell ${!selectedVehicles.length || selectedVehicles.length > 100 || state.busy ? "disabled" : ""}><i data-lucide="banknote-arrow-up"></i><span data-life-garage-bulk-sell-label>${esc(t("life.storage.sell_selected", {count:selectedVehicles.length}))}</span></button></div>
        <p class="life-storage-warning" data-life-garage-bulk-shortage ${target && selectedVehicles.length > targetFree ? "" : "hidden"}><i data-lucide="triangle-alert"></i><span data-life-garage-bulk-shortage-label>${target && selectedVehicles.length > targetFree ? esc(t("life.storage.target_shortage", {count: selectedVehicles.length - targetFree})) : ""}</span></p>
        <p class="life-storage-warning" data-life-garage-bulk-limit ${selectedVehicles.length > 100 ? "" : "hidden"}><i data-lucide="triangle-alert"></i>${esc(t("life.storage.batch_limit", {count: 100}))}</p>
      </div>`;
    bridge()?.renderIcons(host);
    scheduleVehicleImageHydration(host);
    const footer = host.querySelector(".life-garage-bulk-footer");
    if (shell && footer) shell.appendChild(footer);
    requestAnimationFrame(() => {
      host.style.paddingBottom = footer ? `${footer.offsetHeight + 18}px` : "";
    });
  }

  function refreshGarageBulkSelectionUi() {
    const host = document.getElementById("life-garage-bulk-content");
    const source = garageBulkSource();
    if (!host || !source || !state.data) return;
    const ui = host.closest(".life-garage-bulk-dialog") || host;
    const scroller = host.querySelector(".life-garage-bulk-list-scroll");
    const scrollTop = scroller ? scroller.scrollTop : 0;
    const vehicles = garageBulkVehicles(source);
    const visible = filteredGarageBulkVehicles(vehicles);
    const selectedVehicles = vehicles.filter(
      (vehicle) => state.garageBulk.selected.has(String(vehicle.id)),
    );
    const allVisibleSelected = visible.length > 0 && visible.every(
      (vehicle) => state.garageBulk.selected.has(String(vehicle.id)),
    );
    const target = findGarage(state.garageBulk.targetId);
    const targetFree = Number(target?.free || 0);
    const selectedValue = selectedVehicles.reduce(
      (total, vehicle) => total + Math.max(0, Number(vehicle.market_value || 0)), 0,
    );
    const selectedNet = Math.max(0, selectedValue - Math.round(selectedValue * 0.03 * 100) / 100);
    const count = ui.querySelector("[data-life-garage-bulk-selected-count]");
    if (count) count.textContent = String(selectedVehicles.length);
    const value = ui.querySelector("[data-life-garage-bulk-value]");
    if (value) value.textContent = money(selectedValue);
    const net = ui.querySelector("[data-life-garage-bulk-net]");
    if (net) net.textContent = money(selectedNet);
    const selectAll = ui.querySelector("[data-life-garage-bulk-select-all]");
    if (selectAll) {
      selectAll.disabled = !visible.length;
      selectAll.innerHTML = `<i data-lucide="${allVisibleSelected ? "square-x" : "list-checks"}"></i><span data-life-garage-bulk-select-label>${esc(allVisibleSelected ? t("life.storage.clear_selection") : t("life.storage.select_all"))}</span>`;
      bridge()?.renderIcons(selectAll);
    }
    const move = ui.querySelector("[data-life-garage-bulk-move]");
    if (move) {
      move.disabled = !selectedVehicles.length || !target
        || selectedVehicles.length > targetFree || selectedVehicles.length > 100
        || Boolean(state.busy);
      const label = move.querySelector("[data-life-garage-bulk-move-label]");
      if (label) label.textContent = t("life.storage.move_selected", {count:selectedVehicles.length});
    }
    const sell = ui.querySelector("[data-life-garage-bulk-sell]");
    if (sell) {
      sell.disabled = !selectedVehicles.length || selectedVehicles.length > 100 || Boolean(state.busy);
      const label = sell.querySelector("[data-life-garage-bulk-sell-label]");
      if (label) label.textContent = t("life.storage.sell_selected", {count:selectedVehicles.length});
    }
    const shortage = ui.querySelector("[data-life-garage-bulk-shortage]");
    if (shortage) {
      const active = Boolean(target && selectedVehicles.length > targetFree);
      shortage.hidden = !active;
      const label = shortage.querySelector("[data-life-garage-bulk-shortage-label]");
      if (label) label.textContent = active
        ? t("life.storage.target_shortage", {count:selectedVehicles.length - targetFree}) : "";
    }
    const limit = ui.querySelector("[data-life-garage-bulk-limit]");
    if (limit) limit.hidden = selectedVehicles.length <= 100;
    if (scroller) scroller.scrollTop = scrollTop;
  }

  function openGarageBulkDialog() {
    const dialog = document.getElementById("life-garage-bulk-dialog");
    if (!dialog) return;
    if (dialog.parentElement !== document.body) {
      dialog.classList.add("life-page");
      document.body.appendChild(dialog);
    }
    renderGarageBulkDialog();
    if (!dialog.open) {
      if (typeof dialog.showModal === "function") dialog.showModal();
      else dialog.setAttribute("open", "");
    }
  }

  function closeGarageBulkDialog() {
    const dialog = document.getElementById("life-garage-bulk-dialog");
    if (!dialog) return;
    if (typeof dialog.close === "function") dialog.close();
    else dialog.removeAttribute("open");
    paint();
  }

  function paintGachaHistoryDialog() {
    const host = document.getElementById("life-gacha-history-content");
    if (!host) return;
    const previousScrollTop = host.scrollTop;
    const tiers = state.data?.gacha_tiers || [];
    const tier = tiers.find((row) => String(row.id) === String(state.gachaHistoryTier)) || tiers[0] || null;
    if (!tier) {
      host.innerHTML = emptyMarkup(t("life.gacha.history_empty"), "history");
      bridge()?.renderIcons(host);
      return;
    }
    state.gachaHistoryTier = String(tier.id);
    const stats = tier.stats || {};
    const history = [...(tier.history || [])].reverse();
    const trackedPulls = Number(stats.tracked_pulls || 0);
    const luckMinPulls = Number(stats.luck_min_pulls || 20);
    const luck = stats.luck || {};
    const luckKeys = ["fei_3", "fei_2", "fei_1", "balanced", "ou_1", "ou_2", "ou_3"];
    const luckScale = luckKeys.map((key) => `<span class="${key === luck.key ? "active" : ""}"${key === luck.key ? ' aria-current="true"' : ""}><b>${esc(t("life.gacha.luck_" + key))}</b></span>`).join("");
    const started = Number(stats.stats_started_pull || 0);
    const trackingNote = trackedPulls > 0
      ? esc(started > 0 ? t("life.gacha.stats_started", {pull:started + 1}) : t("life.gacha.stats_complete"))
      : esc(Number(tier.pulls || 0) > 0 ? t("life.gacha.stats_pending", {pull:Number(tier.pulls || 0) + 1}) : t("life.gacha.stats_empty"));
    const luckLabel = trackedPulls >= luckMinPulls
      ? t("life.gacha.luck_" + (luck.key || "balanced"))
      : trackedPulls > 0 ? t("life.gacha.luck_provisional") : t("life.gacha.luck_empty");
    const statCards = `<div class="life-gacha-history-summary">
      <span><small>${esc(t("life.gacha.tier_label"))}</small><strong>${esc(t("life.gacha.tier_" + tier.id))}</strong></span>
      <span><small>${esc(t("life.gacha.history_count"))}</small><strong>${history.length}</strong></span>
      <span><small>${esc(t("life.gacha.pulls_total"))}</small><strong>${Number(tier.pulls || 0)}</strong></span>
      <span><small>${esc(t("life.gacha.stats_spent"))}</small><strong>${trackedPulls > 0 ? esc(money(stats.spent)) : "—"}</strong></span>
      <span><small>${esc(t("life.gacha.stats_gold"))}</small><strong>${trackedPulls > 0 ? Number(stats.gold_count || 0) : "—"}</strong></span>
      <span><small>${esc(t("life.gacha.stats_value"))}</small><strong>${trackedPulls > 0 ? esc(money(stats.total_value)) : "—"}</strong></span>
      <span><small>${esc(t("life.gacha.stats_tracked"))}</small><strong>${trackedPulls}</strong></span>
      <span><small>${esc(t("life.gacha.stats_observed"))}</small><strong>${trackedPulls > 0 ? gachaRate(stats.observed_gold_rate, 3) : "—"}</strong></span>
      <span><small>${esc(t("life.gacha.stats_expected"))}</small><strong>${gachaRate(stats.expected_gold_rate, 3)}</strong></span>
    </div>`;
    const luckPanel = `<section class="life-gacha-luck">
      <header><span><i data-lucide="sparkles"></i>${esc(t("life.gacha.luck_title"))}</span><strong>${esc(luckLabel)}</strong></header>
      <div class="life-gacha-luck-scale">${luckScale}</div>
      <p>${trackedPulls >= luckMinPulls ? `${esc(t("life.gacha.luck_score", {score:Number(luck.score || 1).toFixed(2)}))} · ` : ""}${esc(t("life.gacha.luck_hint", {pulls:Math.max(1, Math.round(Number(stats.expected_pulls_per_gold || 1)))}))}</p>
    </section>`;
    const rows = history.map((row, index) => {
      const car = findCar(row.catalog_id);
      const rarity = String(row.rarity || car?.rarity || "common");
      const economics = [
        Object.prototype.hasOwnProperty.call(row, "cost") ? `${t("life.gacha.history_cost")} ${money(row.cost)}` : "",
        Object.prototype.hasOwnProperty.call(row, "value") ? `${t("life.gacha.history_value")} ${money(row.value)}` : "",
      ].filter(Boolean).join(" · ");
      return `<article class="life-gacha-history-row rarity-${esc(rarityClass(rarity))}">
        ${car ? `<span class="life-gacha-history-photo">${vehicleImageTag(car.image, row.name)}</span>` : ""}
        <span class="life-gacha-history-copy"><small>${esc(dayDate(row.day))} · ${esc(garageLabel(row.garage_id))}</small><strong>${esc(row.name || "")}</strong><em>${esc(car?.manufacturer || "")} · ${esc(rarityLabel(rarity))}</em>${gachaTopHit(row) ? gachaTopBadge(row) : ""}</span>
        <span class="life-gacha-history-economics">${economics ? esc(economics) : "—"}</span>
        ${vehicleClassBadge(row.class || car?.class, true)}<small>#${history.length - index}</small>
      </article>`;
    }).join("");
    host.innerHTML = `${statCards}${luckPanel}<p class="life-gacha-tracking-note">${trackingNote}</p>${history.length ? `<div class="life-gacha-history-list">${rows}</div>` : emptyMarkup(t("life.gacha.history_empty"), "history")}`;
    host.scrollTop = previousScrollTop;
    bridge()?.renderIcons(host);
    scheduleVehicleImageHydration(host);
  }

  function openGachaHistoryDialog(tierId) {
    const dialog = document.getElementById("life-gacha-history-dialog");
    if (!dialog) return;
    state.gachaHistoryTier = String(tierId || "");
    paintGachaHistoryDialog();
    const content = document.getElementById("life-gacha-history-content");
    if (content) content.scrollTop = 0;
    if (dialog.open) return;
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
  }

  function closeGachaHistoryDialog() {
    const dialog = document.getElementById("life-gacha-history-dialog");
    if (!dialog) return;
    if (typeof dialog.close === "function") dialog.close();
    else dialog.removeAttribute("open");
  }

  function gachaPoolTier(tierId = state.gachaCatalog.tier) {
    return (state.data?.gacha_tiers || []).find(
      (row) => String(row.id) === String(tierId || ""),
    ) || null;
  }

  function gachaPoolCars(tier = gachaPoolTier()) {
    if (!tier) return [];
    const byId = new Map(dealerCatalog().map((car) => [String(car.catalog_id), car]));
    return (tier.car_ids || [])
      .map((id) => byId.get(String(id)))
      .filter(Boolean);
  }

  function gachaGoldEligible(car, tier) {
    const rarity = String(car?.rarity || "").toLowerCase();
    const rules = Array.isArray(tier?.gold_rules) && tier.gold_rules.length
      ? tier.gold_rules
      : [{class:tier?.top_class || "", rarities:tier?.top_rarities || []}];
    return rules.some((rule) => {
      const rarities = (rule.rarities || []).map((value) => String(value).toLowerCase());
      if (!rarities.includes(rarity)) return false;
      return !rule.class || String(car?.class || "") === String(rule.class);
    });
  }

  function filteredGachaPoolCars(tier) {
    const query = String(state.gachaCatalog.query || "").trim().toLocaleLowerCase();
    return gachaPoolCars(tier).filter((car) => {
      if (state.gachaCatalog.carClass !== "all" && String(car.class || "") !== state.gachaCatalog.carClass) return false;
      if (state.gachaCatalog.rarity !== "all" && String(car.rarity || "").toLowerCase() !== state.gachaCatalog.rarity) return false;
      if (!query) return true;
      return `${car.manufacturer || ""} ${car.name || ""} ${Number(car.year || 0)} ${car.class || ""}`
        .toLocaleLowerCase().includes(query);
    });
  }

  function gachaPoolCard(car, tier, owned) {
    const ownedRow = owned.get(String(car.catalog_id));
    const gold = gachaGoldEligible(car, tier);
    return `<article class="life-catalog-card life-gacha-pool-card rarity-${esc(rarityClass(car.rarity))} ${ownedRow ? "is-owned" : "is-locked"} ${gold ? "is-gold-eligible" : ""}">
      <div class="life-catalog-photo">${vehicleImageTag(car.image, car.name)}${vehicleClassBadge(car.class)}<span class="life-rarity-badge rarity-${esc(rarityClass(car.rarity))}">${esc(rarityLabel(car.rarity))}</span>${ownedRow ? `<span class="life-catalog-lock is-collected"><i data-lucide="badge-check"></i></span>` : ""}</div>
      <div class="life-catalog-copy"><small>${esc(car.manufacturer)} · ${Number(car.year || 0)}</small><h3>${esc(car.name)}</h3><p><span>PI ${Number(car.pi || 0).toFixed(0)}</span><span>${esc(car.type || "")}</span></p></div>
      <footer><span class="life-catalog-owned ${ownedRow ? "is-owned" : ""}">${esc(ownedRow ? t("life.collection.owned_count", {count:Number(ownedRow.count || 1)}) : t("life.collection.not_owned"))}</span><strong>${esc(money(car.price))}</strong></footer>
      ${gold ? `<div class="life-gacha-pool-gold"><i data-lucide="crown"></i><span>${esc(t("life.gacha.catalog_gold"))}</span></div>` : ""}
    </article>`;
  }

  function paintGachaCatalogResults(tier = gachaPoolTier()) {
    const host = document.getElementById("life-gacha-catalog-results");
    if (!host || !tier) return;
    const cars = filteredGachaPoolCars(tier);
    const owned = collectionOwnedMap();
    host.innerHTML = cars.length
      ? `<div class="life-gacha-catalog-count">${esc(t("life.gacha.catalog_results", {count:cars.length}))}</div><div class="life-catalog-grid">${cars.map((car) => gachaPoolCard(car, tier, owned)).join("")}</div>`
      : `<div class="life-gacha-catalog-count">${esc(t("life.gacha.catalog_results", {count:0}))}</div>${emptyMarkup(t("life.collection.no_matches"), "search-x")}`;
    bridge()?.renderIcons(host);
    scheduleVehicleImageHydration(host);
  }

  function paintGachaCatalogDialog() {
    const dialog = document.getElementById("life-gacha-catalog-dialog");
    const host = document.getElementById("life-gacha-catalog-content");
    if (!dialog || !host) return;
    const tier = gachaPoolTier();
    if (!tier) {
      host.innerHTML = emptyMarkup(t("life.gacha.catalog_empty"), "book-open-check");
      bridge()?.renderIcons(host);
      return;
    }
    const cars = gachaPoolCars(tier);
    const owned = collectionOwnedMap();
    const ownedCount = cars.filter((car) => owned.has(String(car.catalog_id))).length;
    const goldCount = cars.filter((car) => gachaGoldEligible(car, tier)).length;
    const title = document.getElementById("life-gacha-catalog-title");
    const eyebrow = document.getElementById("life-gacha-catalog-eyebrow");
    if (title) title.textContent = t("life.gacha.catalog_title", {tier:t("life.gacha.tier_" + tier.id)});
    if (eyebrow) eyebrow.textContent = t("life.gacha.catalog_eyebrow");
    const classes = VEHICLE_CLASS_KEYS.filter((value) => cars.some((car) => String(car.class || "") === value));
    const rarities = ["common", "rare", "epic", "legendary", "forza edition", "donut edition"]
      .filter((value) => cars.some((car) => String(car.rarity || "").toLowerCase() === value));
    host.innerHTML = `<section class="life-gacha-catalog-summary">
        <div><small>${esc(t("life.gacha.catalog_pool"))}</small><strong>${cars.length}</strong><span>${esc(t("life.vehicle"))}</span></div>
        <div><small>${esc(t("life.gacha.catalog_owned"))}</small><strong>${ownedCount}</strong><span>${cars.length ? percent(ownedCount / cars.length, 0) : "0%"}</span></div>
        <div><small>${esc(t("life.gacha.catalog_gold_pool"))}</small><strong>${goldCount}</strong><span>${esc(t("life.gacha.catalog_gold_hint"))}</span></div>
      </section>
      <div class="life-gacha-catalog-toolbar">
        <label class="life-search-field"><i data-lucide="search"></i><input type="search" data-life-gacha-catalog-search value="${esc(state.gachaCatalog.query)}" placeholder="${esc(t("life.gacha.catalog_search"))}" aria-label="${esc(t("life.gacha.catalog_search"))}" autocomplete="off"></label>
        <label class="life-field"><span>${esc(t("life.class"))}</span><select data-life-gacha-catalog-filter="class"><option value="all">${esc(t("life.collection.all_classes"))}</option>${classes.map((value) => `<option value="${value}" ${state.gachaCatalog.carClass === value ? "selected" : ""}>${esc(value)}</option>`).join("")}</select></label>
        <label class="life-field"><span>${esc(t("life.rarity"))}</span><select data-life-gacha-catalog-filter="rarity"><option value="all">${esc(t("life.collection.all_rarities"))}</option>${rarities.map((value) => `<option value="${value}" ${state.gachaCatalog.rarity === value ? "selected" : ""}>${esc(rarityLabel(value))}</option>`).join("")}</select></label>
      </div>
      <div id="life-gacha-catalog-results"></div>`;
    bridge()?.renderIcons(host);
    paintGachaCatalogResults(tier);
  }

  async function openGachaCatalogDialog(tierId) {
    const dialog = document.getElementById("life-gacha-catalog-dialog");
    if (!dialog) return;
    state.gachaCatalog = {tier:String(tierId || ""), query:"", carClass:"all", rarity:"all"};
    if (!state.catalog) await refreshLife({catalog:true});
    paintGachaCatalogDialog();
    const content = document.getElementById("life-gacha-catalog-content");
    if (content) content.scrollTop = 0;
    if (dialog.open) return;
    if (typeof dialog.showModal === "function") dialog.showModal();
    else dialog.setAttribute("open", "");
  }

  function closeGachaCatalogDialog() {
    const dialog = document.getElementById("life-gacha-catalog-dialog");
    if (!dialog) return;
    if (typeof dialog.close === "function") dialog.close();
    else dialog.removeAttribute("open");
  }

  function collectionProgress(ownedCount, total) {
    return total > 0 ? Math.max(0, Math.min(100, Math.round(ownedCount / total * 100))) : 0;
  }

  function collectionManufacturerStats() {
    const owned = collectionOwnedMap();
    const rows = new Map();
    for (const car of dealerCatalog()) {
      const name = String(car.manufacturer || "");
      if (!name) continue;
      const row = rows.get(name) || {name, total: 0, ownedModels: 0, ownedCars: 0, exclusive: 0};
      row.total += 1;
      const ownedRow = owned.get(String(car.catalog_id));
      if (ownedRow) {
        row.ownedModels += 1;
        row.ownedCars += Number(ownedRow.count || 1);
      }
      if (String(car.dealer_status || "") === "display_only") row.exclusive += 1;
      rows.set(name, row);
    }
    return [...rows.values()].sort((left, right) => (
      collectionProgress(right.ownedModels, right.total) - collectionProgress(left.ownedModels, left.total)
      || right.total - left.total
      || left.name.localeCompare(right.name, window.FMODDI18n?.locale || "en-GB")
    ));
  }

  function collectionRarityStats() {
    const owned = collectionOwnedMap();
    const order = ["common", "rare", "epic", "legendary", "forza edition", "donut edition"];
    const rows = new Map(order.map((rarity) => [rarity, {rarity, total: 0, owned: 0}]));
    for (const car of dealerCatalog()) {
      const rarity = String(car.rarity || "common").toLowerCase();
      const row = rows.get(rarity) || {rarity, total: 0, owned: 0};
      row.total += 1;
      if (owned.has(String(car.catalog_id))) row.owned += 1;
      rows.set(rarity, row);
    }
    return [...rows.values()].filter((row) => row.total > 0);
  }

  function collectionClassStats() {
    const owned = collectionOwnedMap();
    const order = ["D", "C", "B", "A", "S1", "S2"];
    return order.map((carClass) => {
      const cars = dealerCatalog().filter((car) => String(car.class || "") === carClass);
      return {
        carClass, total: cars.length,
        owned: cars.filter((car) => owned.has(String(car.catalog_id))).length,
      };
    }).filter((row) => row.total > 0);
  }

  function collectionCard(car, owned = collectionOwnedMap()) {
    const ownedRow = owned.get(String(car.catalog_id));
    const displayOnly = String(car.dealer_status || "") === "display_only";
    const ownedCount = Number(ownedRow?.count || 0);
    return `<article class="life-catalog-card rarity-${esc(rarityClass(car.rarity))} ${ownedRow ? "is-owned" : "is-locked"} ${displayOnly ? "is-display-only" : ""}">
      <div class="life-catalog-photo">${vehicleImageTag(car.image, car.name)}${vehicleClassBadge(car.class)}<span class="life-rarity-badge rarity-${esc(rarityClass(car.rarity))}">${esc(rarityLabel(car.rarity))}</span>${ownedRow ? `<span class="life-catalog-lock is-collected"><i data-lucide="badge-check"></i></span>` : `<span class="life-catalog-lock"><i data-lucide="lock-keyhole"></i></span>`}</div>
      <div class="life-catalog-copy"><small>${esc(car.manufacturer)} · ${Number(car.year || 0)}</small><h3>${esc(car.name)}</h3><p><span>PI ${Number(car.pi || 0).toFixed(0)}</span><span>${esc(car.type || "")}</span></p></div>
      <footer><span class="life-catalog-owned ${ownedRow ? "is-owned" : ""}">${esc(ownedRow ? t("life.collection.owned_count", {count:ownedCount}) : t("life.collection.not_owned"))}</span><strong>${esc(money(car.price))}</strong></footer>
      ${displayOnly ? `<div class="life-catalog-exclusive"><i data-lucide="gem"></i><span>${esc(t("life.collection.display_only"))}</span></div>` : ""}
    </article>`;
  }

  function collectionCards(cars) {
    if (!cars.length) return emptyMarkup(t("life.collection.no_matches"), "search-x");
    const owned = collectionOwnedMap();
    return `<div class="life-catalog-grid">${cars.map((car) => collectionCard(car, owned)).join("")}</div>`;
  }

  function collectionFilterOptions(values, selected, labeler = (value) => value) {
    return values.map((value) => `<option value="${esc(value)}" ${String(selected) === String(value) ? "selected" : ""}>${esc(labeler(value))}</option>`).join("");
  }

  function collectionToolbar() {
    const manufacturers = [...new Set(dealerCatalog().map((car) => String(car.manufacturer || "")).filter(Boolean))]
      .sort((left, right) => left.localeCompare(right, window.FMODDI18n?.locale || "en-GB"));
    return `<div class="life-collection-toolbar">
      <label class="life-search-field"><i data-lucide="search"></i><input type="search" data-life-collection-search value="${esc(state.collection.query)}" placeholder="${esc(t("life.collection.search"))}" aria-label="${esc(t("life.collection.search"))}" autocomplete="off"></label>
      <label class="life-field"><span>${esc(t("life.brand"))}</span><select data-life-collection-filter="manufacturer"><option value="all">${esc(t("life.collection.all_brands"))}</option>${collectionFilterOptions(manufacturers, state.collection.manufacturer)}</select></label>
      <label class="life-field"><span>${esc(t("life.class"))}</span><select data-life-collection-filter="class"><option value="all">${esc(t("life.collection.all_classes"))}</option>${collectionFilterOptions(["S2", "S1", "A", "B", "C", "D"], state.collection.carClass)}</select></label>
      <label class="life-field"><span>${esc(t("life.rarity"))}</span><select data-life-collection-filter="rarity"><option value="all">${esc(t("life.collection.all_rarities"))}</option>${collectionFilterOptions(["common", "rare", "epic", "legendary", "forza edition", "donut edition"], state.collection.rarity, rarityLabel)}</select></label>
      <label class="life-field"><span>${esc(t("life.collection.ownership"))}</span><select data-life-collection-filter="owned"><option value="all">${esc(t("life.collection.all_ownership"))}</option><option value="owned" ${state.collection.owned === "owned" ? "selected" : ""}>${esc(t("life.collection.owned_only"))}</option><option value="missing" ${state.collection.owned === "missing" ? "selected" : ""}>${esc(t("life.collection.missing_only"))}</option></select></label>
    </div>`;
  }

  function filteredCollectionCars(baseCars = dealerCatalog()) {
    const query = String(state.collection.query || "").trim().toLocaleLowerCase();
    const owned = collectionOwnedMap();
    return baseCars.filter((car) => {
      if (state.collection.manufacturer !== "all" && String(car.manufacturer || "") !== state.collection.manufacturer) return false;
      if (state.collection.carClass !== "all" && String(car.class || "") !== state.collection.carClass) return false;
      if (state.collection.rarity !== "all" && String(car.rarity || "").toLowerCase() !== state.collection.rarity) return false;
      const hasOwned = owned.has(String(car.catalog_id));
      if (state.collection.owned === "owned" && !hasOwned) return false;
      if (state.collection.owned === "missing" && hasOwned) return false;
      if (!query) return true;
      return `${car.name} ${car.manufacturer} ${car.year} ${car.type}`.toLocaleLowerCase().includes(query);
    }).sort((left, right) => (
      Number(owned.has(String(right.catalog_id))) - Number(owned.has(String(left.catalog_id)))
      || (RARITY_SORT[right.rarity] || 0) - (RARITY_SORT[left.rarity] || 0)
      || (CLASS_SORT[right.class] || 0) - (CLASS_SORT[left.class] || 0)
      || String(left.manufacturer || "").localeCompare(String(right.manufacturer || ""), window.FMODDI18n?.locale || "en-GB")
      || String(left.name || "").localeCompare(String(right.name || ""), window.FMODDI18n?.locale || "en-GB")
    ));
  }

  const CLASS_SORT = {D: 1, C: 2, B: 3, A: 4, S1: 5, S2: 6};
  const RARITY_SORT = {"common": 1, "rare": 2, "epic": 3, "legendary": 4, "forza edition": 5, "donut edition": 6};

  function collectionOverview() {
    const cars = dealerCatalog();
    const owned = collectionOwnedMap();
    const unique = owned.size;
    const total = Number(state.data?.collection?.summary?.total || 0);
    const progress = collectionProgress(unique, cars.length);
    const legendaryRows = cars.filter((car) => ["legendary", "forza edition", "donut edition"].includes(String(car.rarity || "").toLowerCase()));
    const legendaryOwned = legendaryRows.filter((car) => owned.has(String(car.catalog_id))).length;
    const manufacturers = collectionManufacturerStats();
    const rarityRows = collectionRarityStats();
    const classRows = collectionClassStats();
    const highlights = [...legendaryRows].sort((left, right) => (
      Number(owned.has(String(right.catalog_id))) - Number(owned.has(String(left.catalog_id)))
      || (RARITY_SORT[right.rarity] || 0) - (RARITY_SORT[left.rarity] || 0)
      || String(left.name || "").localeCompare(String(right.name || ""), window.FMODDI18n?.locale || "en-GB")
    )).slice(0, 8);
    return `
      <section class="life-collection-hero">
        <div class="life-collection-ring" style="--collection-progress:${progress}%"><strong>${progress}%</strong><span>${esc(t("life.collection.complete"))}</span></div>
        <div class="life-collection-hero-copy"><small>${esc(t("life.collection.account_shared"))}</small><h3>${esc(t("life.collection.progress", {owned:unique, total:cars.length}))}</h3><p>${esc(t("life.collection.summary", {unique, total, brands:manufacturers.filter((row) => row.ownedModels > 0).length}))}</p></div>
        <dl class="life-collection-kpis"><div><dt>${esc(t("life.collection.copies"))}</dt><dd>${Number(total).toLocaleString()}</dd></div><div><dt>${esc(t("life.collection.legendary_owned"))}</dt><dd>${legendaryOwned} / ${legendaryRows.length}</dd></div><div><dt>${esc(t("life.collection.manufacturers_owned"))}</dt><dd>${manufacturers.filter((row) => row.ownedModels > 0).length} / ${manufacturers.length}</dd></div></dl>
      </section>
      <section class="life-collection-section"><header><div><small>${esc(t("life.collection.manufacturer_progress"))}</small><h3>${esc(t("life.collection.manufacturers"))}</h3></div><button type="button" class="life-secondary" data-life-action="collection-tab" data-collection-tab="manufacturers">${esc(t("life.collection.view_all"))}</button></header><div class="life-collection-manufacturer-list">${manufacturers.slice(0, 6).map((row) => collectionManufacturerRow(row)).join("")}</div></section>
      <div class="life-collection-overview-grid">
        <section class="life-collection-section"><header><div><small>${esc(t("life.collection.rarity_progress"))}</small><h3>${esc(t("life.collection.by_rarity"))}</h3></div></header>${rarityRows.map((row) => `<div class="life-collection-progress-row rarity-${esc(rarityClass(row.rarity))}"><span>${esc(rarityLabel(row.rarity))}</span><div><i style="width:${collectionProgress(row.owned, row.total)}%"></i></div><b>${row.owned} / ${row.total}</b></div>`).join("")}</section>
        <section class="life-collection-section"><header><div><small>${esc(t("life.collection.class_progress"))}</small><h3>${esc(t("life.collection.by_class"))}</h3></div></header>${classRows.map((row) => `<div class="life-collection-progress-row"><span>${esc(row.carClass)}</span><div><i style="width:${collectionProgress(row.owned, row.total)}%"></i></div><b>${row.owned} / ${row.total}</b></div>`).join("")}</section>
      </div>
      <section class="life-collection-section"><header><div><small>${esc(t("life.collection.legendary_collection"))}</small><h3>${esc(t("life.collection.highlights"))}</h3></div><button type="button" class="life-secondary" data-life-action="collection-tab" data-collection-tab="legendary">${esc(t("life.collection.view_all"))}</button></header>${collectionCards(highlights)}</section>`;
  }

  function collectionManufacturerRow(row) {
    const progress = collectionProgress(row.ownedModels, row.total);
    return `<button type="button" class="life-collection-manufacturer" data-life-action="collection-manufacturer" data-manufacturer="${esc(row.name)}"><span><strong>${esc(row.name)}</strong><small>${esc(t("life.collection.models_owned", {owned:row.ownedModels, total:row.total}))}</small></span><div class="life-collection-progress-row"><div><i style="width:${progress}%"></i></div><b>${progress}%</b></div><em>${esc(t("life.collection.copies_owned", {count:row.ownedCars}))}</em></button>`;
  }

  function collectionManufacturersTab() {
    return `<div class="life-collection-manufacturer-grid">${collectionManufacturerStats().map((row) => collectionManufacturerRow(row)).join("")}</div>`;
  }

  function collectionLegendaryTab() {
    const base = dealerCatalog().filter((car) => ["legendary", "forza edition", "donut edition"].includes(String(car.rarity || "").toLowerCase()));
    return collectionToolbar() + `<div id="life-collection-results">${collectionCards(filteredCollectionCars(base))}</div>`;
  }

  function collectionAllTab() {
    return collectionToolbar() + `<div id="life-collection-results">${collectionCards(filteredCollectionCars())}</div>`;
  }

  function paintCollectionResults() {
    const host = document.getElementById("life-collection-results");
    if (!host || !state.catalog) return;
    const base = state.collection.tab === "legendary"
      ? dealerCatalog().filter((car) => ["legendary", "forza edition", "donut edition"].includes(String(car.rarity || "").toLowerCase()))
      : dealerCatalog();
    host.innerHTML = collectionCards(filteredCollectionCars(base));
    bridge()?.renderIcons(host);
    scheduleVehicleImageHydration(host);
  }

  function paintCollectionDialog() {
    const host = document.getElementById("life-collection-dialog-content");
    if (!host) return;
    if (!state.catalog) {
      host.innerHTML = loadingMarkup();
      bridge()?.renderIcons(host);
      return;
    }
    const counts = collectionTabCounts();
    const tab = ["overview", "all", "manufacturers", "legendary"].includes(state.collection.tab) ? state.collection.tab : "overview";
    const tabs = [
      ["overview", t("life.collection.tab_overview"), null],
      ["all", t("life.collection.tab_all"), counts.all],
      ["manufacturers", t("life.collection.tab_manufacturers"), counts.manufacturers],
      ["legendary", t("life.collection.tab_legendary"), counts.legendary],
    ].map(([id, label, count]) => `<button type="button" role="tab" aria-selected="${tab === id}" class="${tab === id ? "active" : ""}" data-life-action="collection-tab" data-collection-tab="${id}"><span>${esc(label)}</span>${count === null ? "" : `<b>${count}</b>`}</button>`).join("");
    const body = tab === "all"
      ? collectionAllTab()
      : tab === "manufacturers" ? collectionManufacturersTab()
        : tab === "legendary" ? collectionLegendaryTab() : collectionOverview();
    const summary = state.data?.collection?.summary || {};
    host.innerHTML = `<div class="life-collection-stats"><span><small>${esc(t("life.collection.unique_models"))}</small><strong>${Number(summary.unique || 0)}</strong></span><span><small>${esc(t("life.collection.total_cars"))}</small><strong>${Number(summary.total || 0)}</strong></span><span><small>${esc(t("life.collection.manufacturers"))}</small><strong>${Number(summary.manufacturers || 0)}</strong></span><span><small>${esc(t("life.collection.display_only"))}</small><strong>${dealerCatalog().filter((car) => String(car.dealer_status || "") === "display_only").length}</strong></span></div><nav class="life-collection-tabs" role="tablist">${tabs}</nav>${body}`;
    bridge()?.renderIcons(host);
    scheduleVehicleImageHydration(host);
  }

  function vehicleCard(vehicle) {
    const targets = (state.data.garages || []).filter((garage) => String(garage.id) !== String(vehicle.garage_id));
    const options = targets.map((garage) => `<option value="${esc(garage.id)}" ${Number(garage.free || 0) <= 0 ? "disabled" : ""}>${esc(garageLabel(garage))} · ${Number(garage.free || 0)} ${esc(t("life.free"))}</option>`).join("");
    const canMove = targets.some((garage) => Number(garage.free || 0) > 0);
    return `<article class="life-vehicle-row">
      <div class="life-vehicle-photo">${vehicleImageTag(vehicle.image, vehicle.name)}${vehicleClassBadge(vehicle.class)}</div>
      <div class="life-vehicle-main"><div><small>${esc(vehicle.manufacturer)} · ${esc(rarityLabel(vehicle.rarity))}</small><h3>${esc(vehicle.name)}</h3></div><dl><div><dt>${esc(t("life.year"))}</dt><dd>${Number(vehicle.year || 0)}</dd></div><div><dt>${esc(t("life.market_value"))}</dt><dd>${esc(money(vehicle.market_value))}</dd></div><div><dt>${esc(t("life.garage"))}</dt><dd>${esc(garageLabel(vehicle.garage_id))}</dd></div><div><dt>${esc(t("life.garage.source_" + (vehicle.source || "dealer")))}</dt><dd>${Number(vehicle.mileage_km || 0).toLocaleString()} km · ${esc(percent(vehicle.condition, 0))}</dd></div></dl></div>
      <div class="life-vehicle-actions"><label class="life-field"><span>${esc(t("life.garage.move_hint"))}</span><select data-life-vehicle-garage="${esc(vehicle.id)}" ${canMove ? "" : "disabled"}><option value="">${esc(t("life.select"))}</option>${options}</select></label><button type="button" class="life-secondary" data-life-action="move-vehicle" data-vehicle-id="${esc(vehicle.id)}" ${!canMove || state.busy === `move:${vehicle.id}` ? "disabled" : ""}><i data-lucide="move-right"></i>${esc(state.busy === `move:${vehicle.id}` ? t("life.loading") : t("life.move"))}</button><button type="button" class="life-danger-button" data-life-action="sell-vehicle" data-vehicle-id="${esc(vehicle.id)}" ${state.busy === `sell-vehicle:${vehicle.id}` ? "disabled" : ""}><i data-lucide="${state.busy === `sell-vehicle:${vehicle.id}` ? "loader-circle" : "banknote-arrow-up"}"></i>${esc(t("life.sell"))}</button></div>
    </article>`;
  }

  function dealerCatalog() {
    return Array.isArray(state.catalog?.cars?.cars) ? state.catalog.cars.cars : [];
  }

  function garageOptions(selection) {
    return (state.data?.garages || []).map((garage) => `<option value="${esc(garage.id)}" ${String(garage.id) === String(selection) ? "selected" : ""} ${Number(garage.free || 0) <= 0 ? "disabled" : ""}>${esc(garageLabel(garage))} · ${Number(garage.free || 0)}/${Number(garage.capacity || 0)}</option>`).join("");
  }

  function dealerGarageOptions() {
    return garageOptions(state.dealer.garageId);
  }

  function renderDealerPage() {
    if (!state.catalog) return loadingMarkup();
    const cars = dealerCatalog();
    const manufacturers = [...new Set(cars.map((car) => car.manufacturer).filter(Boolean))].sort((left, right) => left.localeCompare(right));
    const classes = ["S2", "S1", "A", "B", "C", "D"];
    const rarities = ["legendary", "epic", "rare", "common"];
    return `
      <div class="life-dealer-toolbar">
        <label class="life-search-field"><i data-lucide="search"></i><input type="search" data-life-dealer-search value="${esc(state.dealer.query)}" placeholder="${esc(t("life.dealer.search"))}" aria-label="${esc(t("life.dealer.search"))}" autocomplete="off"></label>
        <label class="life-field"><span>${esc(t("life.brand"))}</span><select data-life-dealer-filter="manufacturer"><option value="all">${esc(t("life.dealer.all_brands"))}</option>${manufacturers.map((brand) => `<option value="${esc(brand)}" ${state.dealer.manufacturer === brand ? "selected" : ""}>${esc(brand)}</option>`).join("")}</select></label>
        <label class="life-field"><span>${esc(t("life.class"))}</span><select data-life-dealer-filter="class"><option value="all">${esc(t("life.dealer.all_classes"))}</option>${classes.map((value) => `<option value="${value}" ${state.dealer.carClass === value ? "selected" : ""}>${value}</option>`).join("")}</select></label>
        <label class="life-field"><span>${esc(t("life.rarity"))}</span><select data-life-dealer-filter="rarity"><option value="all">${esc(t("life.dealer.all_rarities"))}</option>${rarities.map((value) => `<option value="${value}" ${state.dealer.rarity === value ? "selected" : ""}>${esc(rarityLabel(value))}</option>`).join("")}</select></label>
        <label class="life-field life-dealer-garage"><span>${esc(t("life.dealer.select_garage"))}</span><select data-life-dealer-garage>${dealerGarageOptions()}</select></label>
      </div>
      <div class="life-dealer-note"><i data-lucide="info"></i><span>${esc(t("life.dealer.note"))}</span></div>
      <div id="life-dealer-results" class="life-dealer-results" aria-live="polite"></div>`;
  }

  function filteredDealerCars() {
    const query = String(state.dealer.query || "").trim().toLocaleLowerCase();
    return dealerCatalog().filter((car) => {
      if (state.dealer.manufacturer !== "all" && String(car.manufacturer) !== state.dealer.manufacturer) return false;
      if (state.dealer.carClass !== "all" && String(car.class) !== state.dealer.carClass) return false;
      if (state.dealer.rarity !== "all" && String(car.rarity) !== state.dealer.rarity) return false;
      if (!query) return true;
      return `${car.name} ${car.manufacturer} ${car.year}`.toLocaleLowerCase().includes(query);
    });
  }

  function paintDealerResults() {
    const host = document.getElementById("life-dealer-results");
    if (!host || !state.catalog) return;
    const cars = filteredDealerCars();
    const pages = Math.max(1, Math.ceil(cars.length / DEALER_PAGE_SIZE));
    state.dealer.page = Math.max(0, Math.min(pages - 1, Number(state.dealer.page || 0)));
    const visible = cars.slice(state.dealer.page * DEALER_PAGE_SIZE, (state.dealer.page + 1) * DEALER_PAGE_SIZE);
    const garage = (state.data?.garages || []).find((row) => String(row.id) === String(state.dealer.garageId));
    const hasSpace = Number(garage?.free || 0) > 0;
    const buyable = cars.filter((car) => String(car.dealer_status || "") !== "display_only");
    const buyableTotal = buyable.reduce((total, car) => total + Number(car.price || 0), 0);
    const buyableOverLimit = buyable.length > 200 || buyable.length > Number(garage?.free || 0);
    const cards = visible.map((car) => dealerCarCard(car, hasSpace)).join("");
    host.innerHTML = `
      <div class="life-results-head"><div><strong>${esc(t("life.dealer.results", {count:cars.length}))}</strong><span>${esc(hasSpace ? t("life.dealer.select_garage") : t("life.dealer.no_space"))}</span></div><div class="life-dealer-batch"><span>${esc(t("life.dealer.batch_summary", {count: buyable.length, total: money(buyableTotal)}))}</span><button type="button" class="life-primary" data-life-action="buy-filtered-cars" ${!buyable.length || buyableOverLimit || state.busy ? "disabled" : ""}><i data-lucide="shopping-cart"></i>${esc(t("life.dealer.batch_buy", {count: buyable.length}))}</button></div></div>
      ${visible.length ? `<div class="life-dealer-grid">${cards}</div>` : emptyMarkup(t("life.dealer.no_matches"), "search-x")}
      <div class="life-pagination"><button type="button" class="life-secondary" data-life-action="dealer-page" data-page="${state.dealer.page - 1}" ${state.dealer.page <= 0 ? "disabled" : ""}><i data-lucide="chevron-left"></i>${esc(t("life.dealer.prev"))}</button><span>${esc(t("life.dealer.page", {page:state.dealer.page + 1, pages}))}</span><button type="button" class="life-secondary" data-life-action="dealer-page" data-page="${state.dealer.page + 1}" ${state.dealer.page >= pages - 1 ? "disabled" : ""}>${esc(t("life.dealer.next"))}<i data-lucide="chevron-right"></i></button></div>`;
    bridge()?.renderIcons(host);
    scheduleVehicleImageHydration(host);
  }

  function dealerCarCard(car, hasSpace) {
    const busy = state.busy === `dealer:${car.catalog_id}`;
    const displayOnly = String(car.dealer_status || "") === "display_only";
    return `<article class="life-dealer-card ${displayOnly ? "is-display-only" : ""}">
      <div class="life-dealer-photo">${vehicleImageTag(car.image, car.name)}${vehicleClassBadge(car.class)}<span class="life-rarity-badge rarity-${esc(rarityClass(car.rarity))}">${esc(rarityLabel(car.rarity))}</span>${displayOnly ? `<span class="life-dealer-exclusive"><i data-lucide="gem"></i>${esc(t("life.dealer.display_only_badge"))}</span>` : ""}</div>
      <div class="life-dealer-copy"><small>${esc(car.manufacturer)} · ${Number(car.year || 0)}</small><h3>${esc(car.name)}</h3><div><span>PI ${Number(car.pi || 0).toFixed(0)}</span><span>${esc(car.type || "")}</span></div></div>
      <footer><strong>${esc(money(car.price))}</strong>${displayOnly ? `<button type="button" class="life-secondary" disabled><i data-lucide="lock-keyhole"></i>${esc(t("life.dealer.display_only"))}</button>` : `<button type="button" class="life-primary" data-life-action="buy-car" data-catalog-id="${esc(car.catalog_id)}" ${!hasSpace || busy ? "disabled" : ""}>${esc(busy ? t("life.loading") : t("life.buy"))}</button>`}</footer>
    </article>`;
  }

  const GACHA_MULTIPLIERS = [1, 2, 5, 10, 100];

  function gachaMultiplier(tierId) {
    const value = Number(state.gacha.multipliers?.[String(tierId)] || 1);
    return GACHA_MULTIPLIERS.includes(value) ? value : 1;
  }

  function gachaCost(tier, draws) {
    const count = Math.max(1, Number(draws || 1));
    const tenPacks = Math.floor(count / 10);
    const remainder = count % 10;
    return tenPacks * Number(tier.ten_ticket_price || 0)
      + remainder * Number(tier.ticket_price || 0);
  }

  function renderGachaPage() {
    const tiers = state.data?.gacha_tiers || [];
    const garageOptionsMarkup = garageOptions(state.gacha.garageId);
    const garage = (state.data?.garages || []).find((row) => String(row.id) === String(state.gacha.garageId));
    const storage = findGarage("storage");
    const storageRent = state.data?.storage_rent || {};
    const free = Number(garage?.free || 0);
    const topHits = state.lastGacha?.records?.filter(gachaTopHit) || [];
    const deliveryValue = Number(state.lastGacha?.totalValue || 0);
    const deliveryCost = Number(state.lastGacha?.draw?.cost || 0);
    const deliveryNet = deliveryValue - deliveryCost;
    const deliveryRoi = deliveryCost > 0 ? deliveryNet / deliveryCost : 0;
    const deliveryPositive = deliveryNet >= 0;
    const resultMarkup = state.lastGacha?.records?.length ? `
      <section class="life-gacha-results">
        <header class="life-gacha-delivery-head">
          <div class="life-gacha-delivery-title">
            <div class="life-gacha-delivery-heading">
              <div><small>${esc(t("life.gacha.success", {count:state.lastGacha.records.length}))}</small><h2>${esc(t("life.gacha.result"))}</h2></div>
              ${topHits.length ? `<span class="life-gacha-top-summary"><i data-lucide="crown"></i>${esc(t("life.gacha.gold_summary", {count:topHits.length}))}</span>` : ""}
            </div>
            <p class="life-gacha-result-hint">${esc(t("life.gacha.result_hint"))}</p>
          </div>
          <div class="life-gacha-delivery-metrics">
            <span class="life-gacha-total-value"><small>${esc(t("life.gacha.total_value"))}</small><strong>${esc(money(deliveryValue))}</strong><em>${Number(state.lastGacha.records.length)} ${esc(t("life.vehicle"))}</em></span>
            <span class="life-gacha-total-value"><small>${esc(t("life.gacha.delivery_cost"))}</small><strong>${esc(money(deliveryCost))}</strong><em>${esc(t("life.gacha.stats_spent"))}</em></span>
            <span class="life-gacha-total-value life-gacha-net-value ${deliveryPositive ? "is-positive" : "is-negative"}"><small>${esc(t("life.gacha.net_value"))}</small><strong>${deliveryPositive ? "+" : "−"}${esc(money(Math.abs(deliveryNet)))}</strong><em>${deliveryPositive ? "+" : ""}${(deliveryRoi * 100).toFixed(1)}%</em></span>
          </div>
        </header>
        <div class="life-gacha-result-grid">${state.lastGacha.records.map((car) => gachaResultCard(car)).join("")}</div>
      </section>` : "";
    const tierCards = tiers.map((tier) => {
      const multiplier = gachaMultiplier(tier.id);
      const singleDraws = multiplier;
      const tenDraws = multiplier * 10;
      const singleBusy = state.busy === `gacha:${tier.id}:${singleDraws}`;
      const tenBusy = state.busy === `gacha:${tier.id}:${tenDraws}`;
      const anyBusy = String(state.busy || "").startsWith(`gacha:${tier.id}:`);
      const singlePrice = gachaCost(tier, singleDraws);
      const tenPrice = gachaCost(tier, tenDraws);
      const historyCount = (tier.history || []).length;
      const stats = tier.stats || {};
      const trackedPulls = Number(stats.tracked_pulls || 0);
      const goldCondition = gachaGoldCondition(tier);
      return `<article class="life-gacha-tier tier-${esc(tier.id)}">
        <div class="life-gacha-tier-head"><span><i data-lucide="${tier.id === "collector" ? "gem" : tier.id === "performance" ? "gauge" : "sparkles"}"></i></span><div class="life-gacha-tier-title"><div class="life-gacha-tier-title-row"><div><small>${Number(tier.car_count || 0)} ${esc(t("life.vehicle"))}</small><h2>${esc(t("life.gacha.tier_" + tier.id))}</h2></div><button type="button" class="life-gacha-multiplier" data-life-action="gacha-multiplier" data-tier="${esc(tier.id)}" aria-label="${esc(t("life.gacha.multiplier_label", {count:multiplier}))}" title="${esc(t("life.gacha.multiplier_hint"))}"><i data-lucide="repeat-2"></i><span>×${multiplier}</span></button></div><p>${esc(t("life.gacha.tier_" + tier.id + "_note"))}</p></div><div class="life-gacha-tier-actions"><button type="button" class="life-gacha-catalog-button" data-life-action="open-gacha-catalog" data-tier="${esc(tier.id)}" aria-haspopup="dialog" aria-controls="life-gacha-catalog-dialog"><i data-lucide="book-open-check"></i><span>${esc(t("life.gacha.catalog_button", {count:Number(tier.car_count || 0)}))}</span></button><button type="button" class="life-gacha-history-button" data-life-action="open-gacha-history" data-tier="${esc(tier.id)}" aria-haspopup="dialog" aria-controls="life-gacha-history-dialog"><i data-lucide="history"></i><span>${esc(t("life.gacha.history_button", {count:historyCount}))}</span></button></div></div>
        <div class="life-pity-track"><span style="width:${Math.min(100, Number(tier.pity || 0) / Math.max(1, Number(tier.pity_limit || 1)) * 100)}%"></span></div>
        <div class="life-pity-copy"><span>${esc(t("life.gacha.pity", {current:Number(tier.pity || 0), limit:Number(tier.pity_limit || 0)}))}</span><small>${esc(t("life.gacha.pulls", {count:Number(tier.pulls || 0)}))}</small></div>
        <p class="life-pity-hint">${esc(t("life.gacha.pity_hint", {limit:Number(tier.pity_limit || 0), condition:goldCondition}))}</p>
        <div class="life-gacha-pool-stats"><span><small>${esc(t("life.gacha.stats_spent"))}</small><strong>${trackedPulls > 0 ? esc(money(stats.spent)) : "—"}</strong></span><span><small>${esc(t("life.gacha.stats_gold"))}</small><strong>${trackedPulls > 0 ? Number(stats.gold_count || 0) : "—"}</strong></span><span><small>${esc(t("life.gacha.stats_value"))}</small><strong>${trackedPulls > 0 ? esc(money(stats.total_value)) : "—"}</strong></span></div>
        <dl class="life-gacha-prices"><div><dt>${esc(t("life.gacha.ticket", {price:money(tier.ticket_price)}))}</dt></div><div><dt>${esc(t("life.gacha.ten_ticket", {price:money(tier.ten_ticket_price)}))}</dt></div></dl>
        ${gachaOddsMarkup(tier)}
        <div class="life-gacha-actions"><button type="button" class="life-primary life-gacha-draw" data-life-action="gacha-draw" data-tier="${esc(tier.id)}" data-draws="${singleDraws}" ${free < singleDraws || anyBusy ? "disabled" : ""}><i data-lucide="${singleBusy ? "loader-circle" : "dices"}"></i><span>${esc(singleBusy ? t("life.gacha.drawing") : t("life.gacha.single"))}</span><b>×${singleDraws}</b><small>${esc(money(singlePrice))}</small></button><button type="button" class="life-primary life-gacha-draw" data-life-action="gacha-draw" data-tier="${esc(tier.id)}" data-draws="${tenDraws}" ${free < tenDraws || anyBusy ? "disabled" : ""}><i data-lucide="${tenBusy ? "loader-circle" : "layers-3"}"></i><span>${esc(tenBusy ? t("life.gacha.drawing") : t("life.gacha.ten"))}</span><b>×${tenDraws}</b><small>${esc(money(tenPrice))}</small></button></div>
      </article>`;
    }).join("");
    return `
      <div class="life-gacha-toolbar">
        <label class="life-gacha-tool life-gacha-delivery"><i data-lucide="car-front"></i><span><small>${esc(t("life.gacha.select_garage"))}</small><select data-life-gacha-garage>${garageOptionsMarkup}</select></span></label>
        <div class="life-gacha-tool life-gacha-space"><i data-lucide="garage"></i><span><small>${esc(t("life.gacha.capacity"))}</small><b>${Number(garage?.used || 0)} / ${Number(garage?.capacity || 0)}</b><em>${free} ${esc(t("life.free"))}</em></span></div>
        <button type="button" class="life-secondary life-gacha-tool life-gacha-storage-entry" id="life-gacha-storage-open" data-life-action="open-storage" aria-haspopup="dialog" aria-controls="life-storage-dialog"><i data-lucide="archive"></i><span><small>${esc(t("life.storage.open_short"))}</small><b id="life-gacha-storage-open-count">${Number(storage?.used || 0)} / ${Number(storage?.capacity || 10000)}</b><em data-life-storage-rent>${esc(t("life.storage.daily_short", {amount:money(storageRent.daily_amount || 0)}))}</em></span></button>
        <button type="button" class="life-secondary life-gacha-tool life-gacha-collection-entry" id="life-gacha-collection-open" data-life-action="open-collection" aria-haspopup="dialog" aria-controls="life-collection-dialog"><i data-lucide="library-big"></i><span><small>${esc(t("life.collection.open_short"))}</small><b id="life-gacha-collection-open-count">—</b><em>${esc(t("life.collection.save_scope_short"))}</em></span></button>
        <p><i data-lucide="info"></i>${esc(free < 1 ? t("life.gacha.no_space") : t("life.gacha.result_hint"))}</p>
      </div>
      <div class="life-gacha-grid">${tierCards}</div>
      ${resultMarkup}`;
  }

  function gachaOddsMarkup(tier) {
    const odds = tier.odds || {};
    const classRows = Object.entries(odds.class || {}).map(([key, value]) => `<span><b>${esc(key)}</b><em>${(Number(value) * 100).toFixed(Number(value) < 0.01 ? 2 : 1)}%</em></span>`).join("");
    const rarityRows = Object.entries(odds.rarity || {}).map(([key, value]) => `<span><b>${esc(rarityLabel(key))}</b><em>${(Number(value) * 100).toFixed(Number(value) < 0.01 ? 2 : 1)}%</em></span>`).join("");
    const soft = tier.soft_pity || {};
    const condition = gachaGoldCondition(tier);
    return `<section class="life-gacha-odds"><header><span><i data-lucide="chart-no-axes-column"></i>${esc(t("life.gacha.odds_title"))}</span></header><div class="life-gacha-gold-rule"><i data-lucide="crown"></i><div><small>${esc(t("life.gacha.gold_condition"))}</small><strong>${esc(condition)}</strong><em>${esc(t("life.gacha.gold_rate_base", {rate:gachaRate(tier.gold_rate, 3)}))} · ${esc(t("life.gacha.gold_rate_expected", {rate:gachaRate(tier.expected_gold_rate, 3), pulls:Math.max(1, Math.round(Number(tier.expected_pulls_per_gold || 1)))}))}</em></div></div><div class="life-gacha-odds-groups"><div><small>${esc(t("life.gacha.odds_class"))}</small><div>${classRows}</div></div><div><small>${esc(t("life.gacha.odds_rarity"))}</small><div>${rarityRows}</div></div></div><p>${esc(t("life.gacha.odds_soft_note", {start:Number(soft.start_after || 0), step:(Number(soft.step || 0) * 100).toFixed(0), cap:Number(soft.cap || 1).toFixed(1), limit:Number(tier.pity_limit || 0)}))}</p></section>`;
  }

  function gachaGoldCondition(tier) {
    const rules = Array.isArray(tier.gold_rules) && tier.gold_rules.length
      ? tier.gold_rules
      : [{class:tier.top_class || "", rarities:tier.top_rarities || []}];
    return rules.map((rule) => {
      const rarities = (rule.rarities || []).map((rarity) => rarityLabel(rarity)).join(" / ");
      return rule.class
        ? `${rule.class} + ${rarities}`
        : t("life.gacha.rule_any_class", {rarities});
    }).join(` ${t("life.gacha.rule_or")} `);
  }

  function gachaResultCard(car) {
    const garageCopiesBefore = Number(car.garage_copies_before || 0);
    const duplicate = Boolean(car.garage_duplicate ?? garageCopiesBefore > 0);
    return `<article class="life-gacha-result rarity-${esc(rarityClass(car.rarity))}"><div>${vehicleImageTag(car.image, car.name)}${vehicleClassBadge(car.class)}${gachaTopHit(car) ? gachaTopBadge(car) : ""}</div><small>${esc(car.manufacturer)} · ${esc(rarityLabel(car.rarity))}</small><h3>${esc(car.name)}</h3><p>${esc(garageLabel(car.garage_id))} · ${esc(money(car.value || car.base_price))}</p>${duplicate ? `<em>${esc(t("life.gacha.duplicate_garage", {count:garageCopiesBefore}))}</em>` : ""}</article>`;
  }

  function gachaTopHit(record) {
    return Boolean(record?.gacha_gold_hit ?? record?.gold_hit ?? record?.gacha_top_hit ?? record?.top_hit);
  }

  function gachaTopBadge(record) {
    const guaranteed = Boolean(record?.gacha_guaranteed ?? record?.guaranteed);
    const label = guaranteed ? t("life.gacha.guaranteed_gold_hit") : t("life.gacha.gold_hit");
    return `<span class="life-gacha-top-mark ${guaranteed ? "is-guaranteed" : ""}"><i data-lucide="crown"></i>${esc(label)}</span>`;
  }

  function gachaRate(value, digits = 2) {
    return `${(Number(value || 0) * 100).toFixed(digits)}%`;
  }

  // __RENDERERS__

  // __EVENTS__

  function findProperty(assetId) {
    return (state.data?.properties || []).find((row) => String(row.id) === String(assetId)) || null;
  }

  function findParcel(parcelId) {
    return mapParcels().find((row) => String(row.id) === String(parcelId)) || null;
  }

  function findCar(catalogId) {
    return dealerCatalog().find((row) => String(row.catalog_id) === String(catalogId)) || null;
  }

  function findVehicle(vehicleId) {
    return (state.data?.vehicles || []).find((row) => String(row.id) === String(vehicleId)) || null;
  }

  function findGarage(garageId) {
    return (state.data?.garages || []).find((row) => String(row.id) === String(garageId)) || null;
  }

  async function refreshLifeView({packs = false, catalog = false} = {}) {
    if (packs) state.packs = null;
    if (catalog) state.catalog = null;
    await refreshLife({packs, catalog});
  }

  async function confirmBusinessConfiguration(property, card) {
    const businessSelect = card?.querySelector("[data-life-property-business]");
    const selectedOption = businessSelect?.selectedOptions?.[0] || null;
    const businessType = String(businessSelect?.value || property.business_type || "");
    const businessLabel = String(selectedOption?.textContent || businessType);
    const setupCost = Number(selectedOption?.dataset.setupCost || 0);
    const setupDays = Number(selectedOption?.dataset.setupDays || 0);
    const employees = Math.max(0, Math.trunc(Number(
      card?.querySelector("[data-life-property-employees]")?.value || property.employees || 0,
    )));
    const changingBusiness = String(property.mode || "") !== "operate"
      || String(property.business_type || "") !== businessType;
    const message = changingBusiness
      ? t("life.properties.business_confirm", {
        name:propertyName(property), business:businessLabel,
        cost:money(setupCost), days:setupDays, employees,
      })
      : t("life.properties.config_confirm", {
        name:propertyName(property), business:businessLabel, employees,
      });
    const confirmed = await bridge().fmoddConfirm(
      message,
      t("life.properties.submit_business"),
      t("life.properties.title"),
    );
    if (!confirmed) return null;
    return {asset_id:property.id, mode:"operate", business_type:businessType, employees};
  }

  async function handleLifeClick(event) {
    const button = event.target.closest("[data-life-action]");
    if (!button || button.disabled || !button.closest(".life-page, .life-collection-dialog")) return;
    const action = String(button.dataset.lifeAction || "");
    const button_ = button;
    if (!action) return;
    event.preventDefault();

    if (action === "refresh") {
      await refreshLifeView({
        packs: state.page === "life-map",
        catalog: ["life-dealer", "life-gacha", "life-garage"].includes(state.page),
      });
      return;
    }

    if (action === "open-collection") {
      await openCollectionDialog();
      return;
    }

    if (action === "close-collection") {
      closeCollectionDialog();
      return;
    }

    if (action === "open-storage") {
      await openStorageDialog();
      return;
    }

    if (action === "close-storage") {
      closeStorageDialog();
      return;
    }

    if (action === "open-gacha-history") {
      openGachaHistoryDialog(button.dataset.tier);
      return;
    }

    if (action === "close-gacha-history") {
      closeGachaHistoryDialog();
      return;
    }

    if (action === "open-gacha-catalog") {
      await openGachaCatalogDialog(button.dataset.tier);
      return;
    }

    if (action === "close-gacha-catalog") {
      closeGachaCatalogDialog();
      return;
    }

    if (action === "open-garage-bulk") {
      openGarageBulkDialog();
      return;
    }

    if (action === "close-garage-bulk") {
      closeGarageBulkDialog();
      return;
    }

    if (action === "garage-bulk-select-all") {
      const vehicles = filteredGarageBulkVehicles();
      const allSelected = vehicles.length > 0 && vehicles.every(
        (vehicle) => state.garageBulk.selected.has(String(vehicle.id)),
      );
      state.garageBulk.selected.clear();
      if (!allSelected) {
        vehicles.slice(0, 100).forEach((vehicle) => state.garageBulk.selected.add(String(vehicle.id)));
      }
      renderGarageBulkDialog();
      return;
    }

    if (action === "garage-bulk-move") {
      const ids = [...state.garageBulk.selected];
      const target = findGarage(state.garageBulk.targetId);
      if (!ids.length || !target) {
        bridge().toast(t("life.storage.select_required"));
        return;
      }
      if (ids.length > Number(target.free || 0)) {
        bridge().toast(t("life.storage.target_shortage", {count: ids.length - Number(target.free || 0)}));
        return;
      }
      const confirmed = await bridge().fmoddConfirm(
        t("life.storage.move_confirm", {count: ids.length, garage: garageLabel(target)}),
        t("life.storage.move_selected_short"),
        t("life.storage.title"),
      );
      if (!confirmed) return;
      const response = await postLife(
        "/api/life/vehicle/move-batch",
        {vehicle_ids: ids, garage_id: target.id},
        "garage-bulk-move",
      );
      if (response) {
        state.garageBulk.selected.clear();
        bridge().toast(t("life.storage.move_success", {count: Number(response.count || ids.length)}));
        renderGarageBulkDialog();
        paint();
      }
      return;
    }

    if (action === "sell-duplicates") {
      const garageId = String(button.dataset.garageId || "");
      const garage = findGarage(garageId);
      if (!garage) {
        bridge().toast(t("life.garage.no_selection"));
        return;
      }
      const vehicles = (state.data?.vehicles || []).filter(
        (vehicle) => String(vehicle.garage_id) === garageId,
      );
      const duplicates = duplicateVehicleCandidates(vehicles);
      if (!duplicates.length) {
        bridge().toast(t("life.garage.duplicate_empty"));
        return;
      }
      const value = duplicates.reduce(
        (total, vehicle) => total + Math.max(0, Number(vehicle.market_value || 0)), 0,
      );
      const net = Math.max(0, value - Math.round(value * 0.03 * 100) / 100);
      const confirmed = await bridge().fmoddConfirm(
        t("life.garage.duplicate_confirm", {
          count: duplicates.length,
          garage: garageLabel(garage),
          net: money(net),
        }),
        t("life.garage.duplicate_sell", {count: duplicates.length}),
        t("life.garage.title"),
      );
      if (!confirmed) return;
      const response = await postLife(
        "/api/life/vehicle/sell-duplicates",
        {garage_id: garageId},
        `duplicate:${garageId}`,
      );
      if (response) {
        bridge().toast(t("life.garage.duplicate_success", {
          count: Number(response.count || 0),
          amount: money(response.total_net || 0),
        }));
        if (garageId === "storage") paintStorageDialog();
        if (document.getElementById("life-garage-bulk-dialog")?.open
          && String(garageBulkSource()?.id || "") === garageId) {
          renderGarageBulkDialog();
        }
        paint();
      }
      return;
    }

    if (action === "garage-bulk-sell") {
      const vehicles = garageBulkVehicles().filter(
        (vehicle) => state.garageBulk.selected.has(String(vehicle.id)),
      );
      if (!vehicles.length) {
        bridge().toast(t("life.storage.select_required"));
        return;
      }
      const value = vehicles.reduce(
        (total, vehicle) => total + Math.max(0, Number(vehicle.market_value || 0)), 0,
      );
      const fee = Math.round(value * 0.03 * 100) / 100;
      const net = Math.max(0, value - fee);
      const confirmed = await bridge().fmoddConfirm(
        t("life.storage.sell_confirm", {count: vehicles.length, fee: money(fee), net: money(net)}),
        t("life.storage.sell_selected_short"),
        t("life.storage.title"),
      );
      if (!confirmed) return;
      const response = await postLife(
        "/api/life/vehicle/sell-batch",
        {vehicle_ids: vehicles.map((vehicle) => vehicle.id)},
        "garage-bulk-sell",
      );
      if (response) {
        state.garageBulk.selected.clear();
        bridge().toast(t("life.storage.sell_success", {
          count: Number(response.count || vehicles.length),
          amount: money(response.total_net || net),
        }));
        renderGarageBulkDialog();
        paint();
      }
      return;
    }

    if (action === "storage-select-all") {
      const vehicles = filteredStorageVehicles();
      const allSelected = vehicles.length > 0 && vehicles.every(
        (vehicle) => state.storage.selected.has(String(vehicle.id)),
      );
      state.storage.selected.clear();
      if (!allSelected) vehicles.forEach((vehicle) => state.storage.selected.add(String(vehicle.id)));
      paintStorageDialog();
      return;
    }

    if (action === "storage-move-selected") {
      const vehicleIds = [...state.storage.selected];
      const target = findGarage(state.storage.targetId);
      if (!vehicleIds.length || !target) {
        bridge().toast(t("life.storage.select_required"));
        return;
      }
      const confirmed = await bridge().fmoddConfirm(
        t("life.storage.move_confirm", {
          count:vehicleIds.length, garage:garageLabel(target),
        }),
        t("life.storage.move_selected_short"),
        t("life.storage.title"),
      );
      if (!confirmed) return;
      const response = await postLife(
        "/api/life/vehicle/move-batch",
        {vehicle_ids:vehicleIds, garage_id:target.id},
        "storage-move",
      );
      if (response) {
        state.storage.selected.clear();
        bridge().toast(t("life.storage.move_success", {count:Number(response.count || vehicleIds.length)}));
        paintStorageDialog();
        paintStorageButton();
      }
      return;
    }

    if (action === "storage-sell-selected") {
      const vehicles = (state.data?.vehicles || []).filter(
        (vehicle) => state.storage.selected.has(String(vehicle.id)),
      );
      if (!vehicles.length) {
        bridge().toast(t("life.storage.select_required"));
        return;
      }
      const value = vehicles.reduce(
        (total, vehicle) => total + Math.max(0, Number(vehicle.market_value || 0)), 0,
      );
      const fee = Math.round(value * 0.03 * 100) / 100;
      const net = Math.max(0, value - fee);
      const confirmed = await bridge().fmoddConfirm(
        t("life.storage.sell_confirm", {
          count:vehicles.length, fee:money(fee), net:money(net),
        }),
        t("life.storage.sell_selected_short"),
        t("life.storage.title"),
      );
      if (!confirmed) return;
      const response = await postLife(
        "/api/life/vehicle/sell-batch",
        {vehicle_ids:vehicles.map((vehicle) => vehicle.id)},
        "storage-sell",
      );
      if (response) {
        state.storage.selected.clear();
        bridge().toast(t("life.storage.sell_success", {
          count:Number(response.count || vehicles.length),
          amount:money(response.total_net || net),
        }));
        paintStorageDialog();
        paintStorageButton();
      }
      return;
    }

    if (action === "collection-tab") {
      const tab = String(button.dataset.collectionTab || "overview");
      state.collection.tab = ["overview", "all", "manufacturers", "legendary"].includes(tab) ? tab : "overview";
      paintCollectionDialog();
      return;
    }

    if (action === "collection-manufacturer") {
      state.collection.manufacturer = String(button.dataset.manufacturer || "all");
      state.collection.tab = "all";
      state.collection.query = "";
      paintCollectionDialog();
      return;
    }

    if (action === "asset-filter") {
      state.assetFilter = String(button.dataset.filter || "all");
      state.assetExpandAll = null;
      state.assetExpanded.clear();
      paint();
      return;
    }

    if (action === "asset-toggle-group") {
      const key = String(button.dataset.group || "");
      if (!key) return;
      const open = button.getAttribute("aria-expanded") === "true";
      state.assetExpandAll = null;
      const groups = [...document.querySelectorAll("[data-life-action='asset-toggle-group']")]
        .map((node) => String(node.dataset.group || ""));
      if (open) {
        state.assetExpanded.delete(key);
        state.assetExpanded.delete(`open:${key}`);
        state.assetExpanded.add(`closed:${key}`);
      } else {
        state.assetExpanded.add(key);
        state.assetExpanded.add(`open:${key}`);
        state.assetExpanded.delete(`closed:${key}`);
        // Revealing a city must reveal its district headers, not every plot.
        // Collapse the districts first so the user opens the exact one they
        // want; the same rule applies when one district is opened explicitly.
        const childPrefix = key.includes(":district:") ? "" : `${key}:district:`;
        for (const groupKey of groups) {
          if (groupKey === key) continue;
          if (childPrefix && groupKey.startsWith(childPrefix)) {
            state.assetExpanded.delete(groupKey);
            state.assetExpanded.add(`closed:${groupKey}`);
          } else if (key.includes(":district:")) {
            const cityKey = key.split(":district:")[0];
            if (groupKey.startsWith(`${cityKey}:district:`) && groupKey !== key) {
              state.assetExpanded.delete(groupKey);
              state.assetExpanded.add(`closed:${groupKey}`);
            }
          }
        }
      }
      paint();
      return;
    }

    if (action === "asset-toggle-all") {
      state.assetExpandAll = String(button.dataset.expand || "1") === "1";
      state.assetExpanded.clear();
      paint();
      return;
    }

    if (action === "download-map-layer") {
      const city = selectedCity();
      const layer = currentMapLayer();
      if (!city || layer === "city" && !city.city_id) return;
      const response = layer === "parcel"
        ? await postLife("/api/life/city-pack/install", {city_id:city.city_id}, "map-layer")
        : await postLife(
          "/api/life/layer-pack/install",
          {layer, city_id:city.city_id, country_code:state.map.countryCode},
          "map-layer",
        );
      if (!response) return;
      if (layer === "parcel") state.map.zoom = Math.max(TRADE_MIN_ZOOM, state.map.zoom);
      await refreshLifeView({packs:true});
      bridge().toast(t("life.map.layer_success", {layer:mapLayerLabel(layer)}));
      return;
    }

    if (action === "open-map-bulk") {
      openMapBulkDialog();
      return;
    }

    if (action === "close-map-bulk") {
      closeMapBulkDialog();
      return;
    }

    if (action === "map-bulk-kind") {
      state.mapBulk.kind = String(button.dataset.kind || "all");
      renderMapBulkDialog();
      return;
    }

    if (action === "confirm-map-bulk") {
      const city = selectedCity();
      const candidates = mapBulkCandidates();
      if (!city || !candidates.length) return;
      const fallbackTotal = mapBulkTotal(candidates);
      const submitBtn = button_;
      submitBtn.disabled = true;
      const label_ = submitBtn.querySelector("span") || submitBtn;
      const originalLabel = label_.innerHTML;
      label_.innerHTML = `<i data-lucide="loader-circle"></i>${esc(t("life.map.bulk_preparing"))}`;
      bridge()?.renderIcons(submitBtn);
      try {
        const plan = await bridge().request("/api/life/property/buy-batch/prepare", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({city_id: city.city_id, kind: state.mapBulk.kind}),
        });
        const total = Number(plan?.total || fallbackTotal);
        const count = Number(plan?.count || candidates.length);
        const confirmed = await bridge().fmoddConfirm(
          t("life.map.bulk_confirm", {
            count,
            city: cityName(city),
            total: money(total),
          }),
          t("life.map.bulk_open"),
          t("life.map.title"),
        );
        if (!confirmed) return;
        label_.innerHTML = `<i data-lucide="loader-circle"></i>${esc(t("life.map.bulk_buying"))}`;
        bridge()?.renderIcons(submitBtn);
        const response = await postLife(
          "/api/life/property/buy-batch",
          {city_id: city.city_id, kind: state.mapBulk.kind},
          "map-bulk",
        );
        if (response) {
          closeMapBulkDialog();
          bridge().toast(t("life.map.bulk_success", {
            count: Number(response.count || count),
            total: money(response.total || total),
          }));
        }
      } catch (error) {
        bridge().toast(error?.message || t("life.error"));
      } finally {
        if (submitBtn.isConnected) {
          submitBtn.disabled = false;
          label_.innerHTML = originalLabel;
          bridge()?.renderIcons(submitBtn);
        }
      }
      return;
    }

    if (action === "map-kind") {
      state.map.kind = String(button.dataset.kind || "all");
      state.map.parcelId = "";
      paint();
      return;
    }

    if (action === "map-zoom") {
      setMapZoom(state.map.zoom + (Number(button.dataset.direction || 0) || 0));
      return;
    }

    if (action === "map-marker") {
      if (!canTradeMap()) {
        bridge().toast(t("life.map.parcel_locked"));
        return;
      }
      const parcel = findParcel(button.dataset.parcelId);
      if (!parcel) return;
      state.map.parcelId = String(parcel.id);
      if (button.dataset.mapFocus === "true") {
        state.map.center = {lat:Number(parcel.lat), lng:Number(parcel.lng)};
        state.map.zoom = TRADE_MAX_ZOOM;
        state.map.tileError = false;
      }
      paint();
      return;
    }

    if (action === "map-aggregate") {
      const layer = currentMapLayer();
      const node = aggregateNodes().find((row) => String(row.id) === String(button.dataset.nodeId || ""));
      if (!node) return;
      state.map.nodeId = String(node.id);
      if (layer === "world" && mapCountries().some((row) => row.code === String(node.id))) {
        const code = String(node.id);
        const scoped = mapCountryCities(code);
        const city = scoped.find((row) => row.installed) || scoped[0];
        state.map.countryCode = code;
        if (city) {
          state.map.cityId = String(city.city_id);
          state.map.center = {lat:Number(city.lat), lng:Number(city.lng)};
        } else {
          state.map.center = {lat:Number(node.lat), lng:Number(node.lng)};
        }
        state.map.fallbackProvider = "";
        state.map.zoom = 6;
        state.map.tileError = false;
        paint();
        return;
      }
      if (layer === "country" && mapCountryCities().some((row) => String(row.city_id) === String(node.id))) {
        state.map.cityId = String(node.id);
        state.map.center = {lat:Number(node.lat), lng:Number(node.lng)};
        state.map.zoom = 10;
        state.map.tileError = false;
        paint();
        return;
      }
      state.map.center = {lat:Number(node.lat), lng:Number(node.lng)};
      paint();
      return;
    }

    if (action === "map-close") {
      state.map.parcelId = "";
      paint();
      return;
    }

    if (action === "buy-plot") {
      if (!canTradeMap()) {
        bridge().toast(t("life.map.parcel_locked"));
        return;
      }
      const parcel = findParcel(button.dataset.parcelId);
      if (!parcel || ownedParcelIds().has(String(parcel.id))) return;
      const price = Number(parcel.quote || parcel.base_price || 0);
      const fee = Number(parcel.buy_fee || 0);
      const confirmed = await bridge().fmoddConfirm(
        t("life.map.buy_confirm", {
          name:propertyName(parcel),
          price:money(price + fee),
          fee:money(fee),
        }),
        t("life.map.buy_plot"),
        t("life.map.details"),
      );
      if (!confirmed) return;
      const response = await postLife(
        "/api/life/property/buy",
        {parcel_id:parcel.id, city_id:parcel.city_id || state.map.cityId},
        "buy-plot",
      );
      if (response) bridge().toast(t("life.map.buy_success", {name:propertyName(parcel)}));
      return;
    }

    if (action === "lease-plot") {
      if (!canTradeMap()) {
        bridge().toast(t("life.map.parcel_locked"));
        return;
      }
      const parcel = findParcel(button.dataset.parcelId);
      if (!parcel || propertyForParcel(parcel.id)) return;
      const leaseDays = Number(document.querySelector("[data-life-lease-days]")?.value || state.map.leaseDays || 90);
      const option = (parcel.lease_options || []).find((row) => Number(row.days) === leaseDays);
      if (!option) return;
      const confirmed = await bridge().fmoddConfirm(
        t("life.map.lease_confirm", {
          name:propertyName(parcel), days:leaseDays,
          prepaid:money(option.prepaid_rent), deposit:money(option.deposit),
          total:money(option.total),
        }),
        t("life.map.lease_plot"),
        t("life.map.details"),
      );
      if (!confirmed) return;
      const response = await postLife(
        "/api/life/property/lease",
        {parcel_id:parcel.id, city_id:parcel.city_id || state.map.cityId, days:leaseDays},
        "lease-plot",
      );
      if (response) bridge().toast(t("life.map.lease_success", {name:propertyName(parcel), days:leaseDays}));
      return;
    }

    if (action === "collect-income") {
      const response = await postLife("/api/life/income/collect", {}, "collect");
      if (response) {
        bridge().toast(t("life.properties.collect_success", {
          amount:money(response.income?.amount || 0),
        }));
      }
      return;
    }

    if (action === "property-mode") {
      const property = findProperty(button.dataset.assetId);
      if (!property) return;
      const mode = String(button.dataset.mode || "");
      if (!propertyModeChoices(String(property.kind || ""), property).includes(mode) || mode === property.mode) return;
      const card = button.closest(".life-property-card");
      const payload = mode === "operate"
        ? await confirmBusinessConfiguration(property, card)
        : {asset_id:property.id, mode};
      if (!payload) return;
      const response = await postLife(
        "/api/life/property/configure",
        payload,
        `mode:${property.id}`,
      );
      if (response) {
        bridge().toast(response.business_setup
          ? t("life.properties.business_submitted", {days:Number(response.project?.duration_days || 0)})
          : t("life.properties.mode_saved"));
      }
      return;
    }

    if (action === "save-property-config") {
      const property = findProperty(button.dataset.assetId);
      if (!property) return;
      const card = button.closest(".life-property-card");
      const payload = await confirmBusinessConfiguration(property, card);
      if (!payload) return;
      const response = await postLife(
        "/api/life/property/configure",
        payload,
        `config:${property.id}`,
      );
      if (response) {
        bridge().toast(response.business_setup
          ? t("life.properties.business_submitted", {days:Number(response.project?.duration_days || 0)})
          : t("life.properties.config_saved"));
      }
      return;
    }

    if (action === "upgrade-property") {
      const property = findProperty(button.dataset.assetId);
      if (!property) return;
      const cost = Number(property.upgrade_cost || 0);
      if (cost <= 0) return;
      const nextLevel = Math.max(1, Number(property.level || 1)) + 1;
      const days = Number(property.upgrade_days || 0);
      const confirmed = await bridge().fmoddConfirm(
        t("life.properties.upgrade_confirm_schedule", {
          name:propertyName(property), level:nextLevel, cost:money(cost), days,
        }),
        t("life.properties.upgrade"),
        t("life.properties.title"),
      );
      if (!confirmed) return;
      const response = await postLife(
        "/api/life/property/upgrade", {asset_id:property.id}, `upgrade:${property.id}`,
      );
      if (response) {
        bridge().toast(t("life.properties.upgrade_started", {
          name:propertyName(property), days:Number(response.upgrade?.duration_days || 0),
        }));
      }
      return;
    }

    if (action === "sell-property") {
      const property = findProperty(button.dataset.assetId);
      if (!property) return;
      const value = Number(property.market_value || 0);
      const fee = Math.round(value * 0.03 * 100) / 100;
      const pending = Number(property.pending_income || 0);
      const confirmed = await bridge().fmoddConfirm(
        t("life.properties.sell_confirm", {
          name:propertyName(property),
          net:money(Math.max(0, value - fee)),
          income:money(pending),
        }),
        t("life.sell"),
        t("life.properties.title"),
      );
      if (!confirmed) return;
      const response = await postLife(
        "/api/life/property/sell", {asset_id:property.id}, `sell:${property.id}`,
      );
      if (response) {
        bridge().toast(t("life.properties.sell_success", {
          amount:money(response.sale?.credit || 0),
        }));
      }
      return;
    }

    if (action === "renew-lease") {
      const property = findProperty(button.dataset.assetId);
      if (!property) return;
      const card = button.closest(".life-property-card");
      const days = Number(card?.querySelector("[data-life-lease-renew-days]")?.value || 90);
      const option = (property.lease_renew_options || []).find((row) => Number(row.days) === days);
      if (!option) return;
      const confirmed = await bridge().fmoddConfirm(
        t("life.properties.lease_renew_confirm", {
          name:propertyName(property), days, amount:money(option.amount),
        }),
        t("life.properties.lease_renew"),
        t("life.properties.title"),
      );
      if (!confirmed) return;
      const response = await postLife(
        "/api/life/property/renew-lease",
        {asset_id:property.id, days},
        `renew:${property.id}`,
      );
      if (response) bridge().toast(t("life.properties.lease_renew_success", {days}));
      return;
    }

    if (action === "release-lease") {
      const property = findProperty(button.dataset.assetId);
      if (!property) return;
      const deposit = Number(property.lease?.deposit || 0);
      const confirmed = await bridge().fmoddConfirm(
        t("life.properties.lease_release_confirm", {
          name:propertyName(property), deposit:money(deposit),
        }),
        t("life.properties.lease_release"),
        t("life.properties.title"),
      );
      if (!confirmed) return;
      const response = await postLife(
        "/api/life/property/release-lease",
        {asset_id:property.id},
        `release:${property.id}`,
      );
      if (response) bridge().toast(t("life.properties.lease_release_success", {
        amount:money(response.release?.credit || 0),
      }));
      return;
    }

    if (action === "select-garage") {
      const garage = findGarage(button.dataset.garageId);
      if (!garage) return;
      state.garage.selectedId = String(garage.id);
      paint();
      return;
    }

    if (action === "sell-vehicle") {
      const vehicle = findVehicle(button.dataset.vehicleId);
      if (!vehicle) return;
      const value = Number(vehicle.market_value || 0);
      const fee = Math.round(value * 0.03 * 100) / 100;
      const net = Math.max(0, value - fee);
      const confirmed = await bridge().fmoddConfirm(
        t("life.garage.sell_confirm", {name:vehicle.name, fee:money(fee), net:money(net)}),
        t("life.sell"),
        t("life.garage.title"),
      );
      if (!confirmed) return;
      const response = await postLife(
        "/api/life/vehicle/sell",
        {vehicle_id:vehicle.id},
        `sell-vehicle:${vehicle.id}`,
      );
      if (response) {
        bridge().toast(t("life.garage.sell_success", {
          name:response.vehicle?.name || vehicle.name,
          amount:money(response.sale?.net || net),
        }));
      }
      return;
    }

    if (action === "move-vehicle") {
      const vehicleId = String(button.dataset.vehicleId || "");
      const select = [...document.querySelectorAll("[data-life-vehicle-garage]")]
        .find((node) => String(node.dataset.lifeVehicleGarage || "") === vehicleId);
      const garageId = String(select?.value || "");
      if (!vehicleId || !garageId) {
        bridge().toast(t("life.select"));
        return;
      }
      const response = await postLife(
        "/api/life/vehicle/move",
        {vehicle_id:vehicleId, garage_id:garageId},
        `move:${vehicleId}`,
      );
      if (response) bridge().toast(t("life.garage.move_success"));
      return;
    }

    if (action === "dealer-page") {
      state.dealer.page = Math.max(0, Number(button.dataset.page || 0));
      paintDealerResults();
      return;
    }

    if (action === "buy-car") {
      const car = findCar(button.dataset.catalogId);
      const garage = findGarage(state.dealer.garageId);
      if (!car) return;
      if (String(car.dealer_status || "") === "display_only") {
        bridge().toast(t("life.dealer.display_only_message"));
        return;
      }
      if (!garage || Number(garage.free || 0) <= 0) {
        bridge().toast(t("life.dealer.no_space"));
        return;
      }
      const confirmed = await bridge().fmoddConfirm(
        t("life.dealer.buy_confirm", {
          name:car.name, price:money(car.price), garage:garageLabel(garage.id),
        }),
        t("life.buy"),
        t("life.dealer.title"),
      );
      if (!confirmed) return;
      const response = await postLife(
        "/api/life/vehicle/buy",
        {catalog_id:car.catalog_id, garage_id:garage.id},
        `dealer:${car.catalog_id}`,
      );
      if (response) bridge().toast(t("life.dealer.buy_success", {name:car.name}));
      return;
    }

    if (action === "buy-filtered-cars") {
      const garage = findGarage(state.dealer.garageId);
      const cars = filteredDealerCars().filter(
        (car) => String(car.dealer_status || "") !== "display_only",
      );
      if (!garage || !cars.length) return;
      if (cars.length > 200 || cars.length > Number(garage.free || 0)) {
        bridge().toast(t("life.dealer.batch_no_space", {
          count: cars.length,
          free: Number(garage.free || 0),
        }));
        return;
      }
      const total = cars.reduce((sum, car) => sum + Number(car.price || 0), 0);
      const confirmed = await bridge().fmoddConfirm(
        t("life.dealer.batch_confirm", {
          count: cars.length,
          total: money(total),
          garage: garageLabel(garage.id),
        }),
        t("life.dealer.batch_buy", {count: cars.length}),
        t("life.dealer.title"),
      );
      if (!confirmed) return;
      const response = await postLife(
        "/api/life/vehicle/buy-batch",
        {catalog_ids: cars.map((car) => car.catalog_id), garage_id: garage.id},
        "dealer-batch",
      );
      if (response) {
        bridge().toast(t("life.dealer.batch_success", {
          count: Number(response.count || cars.length),
          total: money(response.total || total),
        }));
      }
      return;
    }

    if (action === "gacha-multiplier") {
      const tierId = String(button.dataset.tier || "");
      const current = gachaMultiplier(tierId);
      const index = GACHA_MULTIPLIERS.indexOf(current);
      state.gacha.multipliers[tierId] = GACHA_MULTIPLIERS[(index + 1) % GACHA_MULTIPLIERS.length];
      paint();
      return;
    }

    if (action === "gacha-draw") {
      const tierId = String(button.dataset.tier || "");
      const draws = Number(button.dataset.draws || 1);
      const tier = (state.data?.gacha_tiers || []).find((row) => String(row.id) === tierId);
      const garage = findGarage(state.gacha.garageId);
      if (!tier) return;
      if (!garage || Number(garage.free || 0) < draws) {
        bridge().toast(t("life.gacha.no_space"));
        return;
      }
      const price = gachaCost(tier, draws);
      if (bridge().gachaConfirmEnabled?.() !== false) {
        const confirmed = await bridge().fmoddConfirm(
          t("life.gacha.confirm", {
            draws,
            tier:t(`life.gacha.tier_${tier.id}`),
            price:money(price),
          }),
          t("life.gacha.draw_count", {count: draws}),
          t("life.gacha.title"),
        );
        if (!confirmed) return;
      }
      const response = await postLife(
        "/api/life/gacha/draw",
        {tier:tier.id, draws, garage_id:garage.id},
        `gacha:${tier.id}:${draws}`,
      );
      if (response) {
        const topHits = (response.records || []).filter(gachaTopHit);
        bridge().toast(topHits.length
          ? t("life.gacha.gold_hit_toast", {name:topHits[0].name, count:topHits.length})
          : t("life.gacha.success", {count:response.records?.length || draws}));
      }
    }
  }

  function handleLifeChange(event) {
    const target = event.target;
    if (target.matches("[data-life-map-country]")) {
      selectMapCountry(target.value);
      return;
    }
    if (target.matches("[data-life-map-city]")) {
      selectMapCity(target.value);
      return;
    }
    if (target.matches("[data-life-map-provider]")) {
      setMapProvider(target.value);
      return;
    }
    if (target.matches("[data-life-lease-days]")) {
      state.map.leaseDays = Number(target.value || 90);
      paint();
      return;
    }
    if (target.matches("[data-life-property-business]")) {
      const option = target.selectedOptions?.[0] || null;
      const quote = target.closest(".life-property-config")?.querySelector(".life-business-quote");
      if (quote && option) {
        const cost = quote.querySelector("[data-life-business-cost]");
        const days = quote.querySelector("[data-life-business-days]");
        if (cost) cost.textContent = money(Number(option.dataset.setupCost || 0));
        if (days) days.textContent = String(Number(option.dataset.setupDays || 0));
      }
      return;
    }
    if (target.matches("[data-life-dealer-filter]")) {
      const key = String(target.dataset.lifeDealerFilter || "");
      if (key === "manufacturer") state.dealer.manufacturer = target.value;
      if (key === "class") state.dealer.carClass = target.value;
      if (key === "rarity") state.dealer.rarity = target.value;
      state.dealer.page = 0;
      paintDealerResults();
      return;
    }
    if (target.matches("[data-life-dealer-garage]")) {
      state.dealer.garageId = String(target.value || "");
      paintDealerResults();
      return;
    }
    if (target.matches("[data-life-collection-filter]")) {
      const key = String(target.dataset.lifeCollectionFilter || "");
      if (key === "manufacturer") state.collection.manufacturer = target.value;
      if (key === "class") state.collection.carClass = target.value;
      if (key === "rarity") state.collection.rarity = target.value;
      if (key === "owned") state.collection.owned = target.value;
      paintCollectionResults();
      return;
    }
    if (target.matches("[data-life-gacha-catalog-filter]")) {
      const key = String(target.dataset.lifeGachaCatalogFilter || "");
      if (key === "class") state.gachaCatalog.carClass = target.value;
      if (key === "rarity") state.gachaCatalog.rarity = target.value;
      paintGachaCatalogResults();
      return;
    }
    if (target.matches("[data-life-garage-bulk-select]")) {
      const vehicleId = String(target.dataset.lifeGarageBulkSelect || "");
      if (target.checked) state.garageBulk.selected.add(vehicleId);
      else state.garageBulk.selected.delete(vehicleId);
      refreshGarageBulkSelectionUi();
      return;
    }
    if (target.matches("[data-life-garage-bulk-filter]")) {
      const key = String(target.dataset.lifeGarageBulkFilter || "");
      if (key === "manufacturer") state.garageBulk.manufacturer = target.value;
      if (key === "class") state.garageBulk.carClass = target.value;
      if (key === "rarity") state.garageBulk.rarity = target.value;
      renderGarageBulkDialog();
      return;
    }
    if (target.matches("[data-life-garage-bulk-target]")) {
      state.garageBulk.targetId = String(target.value || "");
      renderGarageBulkDialog();
      return;
    }
    if (target.matches("[data-life-storage-select]")) {
      const vehicleId = String(target.dataset.lifeStorageSelect || "");
      if (target.checked) state.storage.selected.add(vehicleId);
      else state.storage.selected.delete(vehicleId);
      refreshStorageSelectionUi();
      return;
    }
    if (target.matches("[data-life-storage-filter]")) {
      const key = String(target.dataset.lifeStorageFilter || "");
      if (key === "manufacturer") state.storage.manufacturer = target.value;
      if (key === "class") state.storage.carClass = target.value;
      if (key === "rarity") state.storage.rarity = target.value;
      paintStorageResults();
      return;
    }
    if (target.matches("[data-life-storage-target]")) {
      state.storage.targetId = String(target.value || "");
      paintStorageDialog();
      return;
    }
    if (target.matches("[data-life-gacha-garage]")) {
      state.gacha.garageId = String(target.value || "");
      paint();
    }
  }

  function handleLifeInput(event) {
    const target = event.target;
    if (target.matches("[data-life-dealer-search]")) {
      state.dealer.query = String(target.value || "");
      state.dealer.page = 0;
      clearTimeout(state.dealer.searchTimer);
      state.dealer.searchTimer = setTimeout(paintDealerResults, 120);
      return;
    }
    if (target.matches("[data-life-collection-search]")) {
      state.collection.query = String(target.value || "");
      clearTimeout(state.collection.searchTimer);
      state.collection.searchTimer = setTimeout(paintCollectionResults, 120);
      return;
    }
    if (target.matches("[data-life-garage-bulk-search]")) {
      state.garageBulk.query = String(target.value || "");
      clearTimeout(state.garageBulk.searchTimer);
      state.garageBulk.searchTimer = setTimeout(renderGarageBulkDialog, 120);
      return;
    }
    if (target.matches("[data-life-storage-search]")) {
      state.storage.query = String(target.value || "");
      clearTimeout(state.storage.searchTimer);
      state.storage.searchTimer = setTimeout(paintStorageResults, 120);
      return;
    }
    if (target.matches("[data-life-gacha-catalog-search]")) {
      state.gachaCatalog.query = String(target.value || "");
      clearTimeout(state.gachaCatalog.searchTimer);
      state.gachaCatalog.searchTimer = setTimeout(paintGachaCatalogResults, 120);
    }
  }

  window.FMSDDLife = Object.freeze({render, preload});
})();
