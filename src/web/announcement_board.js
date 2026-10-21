/* FMSDD announcement board.
 *
 * The board ships with the build: a notice is a stable key plus a stamp, a
 * set of status tags and a pin flag, so the copy lives in the locale packs
 * while ordering, filtering and rendering stay language neutral.
 *
 * Bodies are Markdown. Only a deliberately small subset is supported (ATX and
 * legacy `【】` headings, paragraphs, flat lists, quotes, rules, pipe tables,
 * fenced code and inline emphasis/links/code/images). Everything is escaped
 * before formatting; links must be http(s) and images must be packaged under
 * /assets/ or explicit https URLs, so a notice can never inject markup or
 * reach the local file system.
 *
 * The board owns no server truth and never writes storage: unread state and
 * the reader's sort/filter choice stay with the shell in app.js.
 */
(() => {
  "use strict";

  /* Tag tones are presentation only; the visible label always carries the
     meaning, so a colour-blind reader never loses the status. */
  const TAG_TONES = Object.freeze({
    release: "green",
    feature: "blue",
    improvement: "teal",
    fix: "amber",
    important: "red",
    notice: "grey",
    event: "violet",
    guide: "slate",
  });
  const TAG_IDS = Object.freeze(Object.keys(TAG_TONES));
  const SORT_MODES = Object.freeze(["pinned", "newest"]);
  const COLLAPSED_PLAIN_LENGTH = 280;
  const COLLAPSED_BLOCK_LIMIT = 6;

  /* New entries go at the top of the array. The shell marks the newest stamp
     (not the first row) as unread, so re-sorting can never fake a new notice. */
  const BOARD = Object.freeze([
    {id:"2026-10-21-v296-update", date:"2026-10-21", time:"18:10", pinned:true, version:"V2.9.6cBeta", key:"announce.entry.v296_update", tags:["release","feature","improvement","fix"]},
    {id:"2026-10-19-v290-update", date:"2026-10-19", time:"13:00", pinned:false, version:"V2.9.0Beta", key:"announce.entry.v290_update", tags:["release","feature","improvement"]},
    {id:"2026-10-19-community", date:"2026-10-19", time:"12:00", pinned:true, version:"", alwaysOpen:true, key:"announce.entry.community", tags:["notice","event"]},
    {id:"2026-10-18-v285-launch", date:"2026-10-18", time:"02:00", pinned:false, version:"V2.8.5Beta", key:"announce.entry.v285_launch", tags:["release"]},
    {id:"2026-10-17-v280-launch-fmsdd", date:"2026-10-17", time:"12:00", pinned:false, version:"V2.8.0beta", key:"announce.entry.v280_launch", tags:["release","feature"]},
    {id:"2026-10-17-open-source", date:"2026-10-17", time:"09:00", pinned:true, version:"", key:"announce.entry.open_source", tags:["notice","important"]},
    {id:"2026-10-16-feature-guide", date:"2026-10-16", time:"21:00", pinned:false, version:"V2.7.0beta", key:"announce.entry.feature_guide", tags:["guide"]},
  ]);

  const HTML_ESCAPES = Object.freeze({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;",
  });
  const escapeHtml = (value) => String(value ?? "").replace(
    /[&<>"']/g, (character) => HTML_ESCAPES[character],
  );

  const CODE_TOKEN = "\u0000code\u0000";
  const CODE_RESTORE = new RegExp(`${CODE_TOKEN}(\\d+)${CODE_TOKEN}`, "g");
  const LINK_PATTERN = /\[([^\]\n]+)\]\(((?:[^()\s]|\([^()]*\))+)\)/g;
  const IMAGE_PATTERN = /!\[([^\]\n]*)\]\(((?:[^()\s]|\([^()]*\))+)\)/g;
  const IMAGE_ONLY_PATTERN = /^\s*!\[([^\]\n]*)\]\(((?:[^()\s]|\([^()]*\))+)\)\s*$/;
  const IMAGE_PAIR_PATTERN = /^\s*!\[([^\]\n]*)\]\(((?:[^()\s]|\([^()]*\))+)\)\s+!\[([^\]\n]*)\]\(((?:[^()\s]|\([^()]*\))+)\)\s*$/;
  const SAFE_LINK = /^https?:\/\/[^\s"'<>]+$/i;
  const SAFE_IMAGE = /^(?:https?:\/\/[^\s"'<>]+|\/assets\/[^\s"'<>]*)$/i;
  const HEADING_PATTERN = /^(#{1,6})\s+(.+?)\s*#*\s*$/;
  const LEGACY_HEADING_PATTERN = /^【([^】\n]{1,90})】\s*(.*)$/;
  const UNORDERED_PATTERN = /^\s*[-*+]\s+(.+)$/;
  const ORDERED_PATTERN = /^\s*\d+[.)]\s+(.+)$/;
  const QUOTE_PATTERN = /^\s*>\s?(.*)$/;
  const RULE_PATTERN = /^\s*(?:-{3,}|\*{3,}|_{3,})\s*$/;
  const FENCE_PATTERN = /^\s*(```|~~~)\s*([A-Za-z0-9+#.-]*)\s*$/;
  const TABLE_ROW_PATTERN = /^\s*\|(.+)\|\s*$/;

  function safeLinkTarget(url) {
    const value = String(url || "").trim().replace(/&amp;/g, "&");
    return SAFE_LINK.test(value) ? value : "";
  }

  /* Announcement artwork is either packaged with the app (/assets/…) or an
     explicit https image. Data URLs and relative traversal are refused so a
     notice cannot probe the local file system or inline a script payload. */
  function safeImageTarget(url) {
    const value = String(url || "").trim().replace(/&amp;/g, "&");
    if (!SAFE_IMAGE.test(value)) return "";
    if (value.startsWith("/assets/") && (value.includes("..") || value.includes("\\"))) {
      return "";
    }
    return value;
  }

  function inlineMarkdown(source) {
    let text = escapeHtml(source);
    const codes = [];
    text = text.replace(/`([^`\n]+)`/g, (_match, code) => {
      codes.push(code);
      return `${CODE_TOKEN}${codes.length - 1}${CODE_TOKEN}`;
    });
    text = text.replace(IMAGE_PATTERN, (_match, alt, src) => {
      const target = safeImageTarget(src);
      if (!target) return alt;
      return `<img class="announcement-image" src="${escapeHtml(target)}" alt="${alt}" loading="lazy" decoding="async">`;
    });
    text = text.replace(LINK_PATTERN, (match, label, href) => {
      const target = safeLinkTarget(href);
      if (!target) return label;
      return `<a href="${escapeHtml(target)}" target="_blank" rel="noreferrer noopener">${label}</a>`;
    });
    text = text.replace(/\*\*([^*\n]+)\*\*/g, "<strong>$1</strong>");
    text = text.replace(
      /(^|[\s(])\*([^*\n]{1,240})\*(?=$|[\s).,;:!?])/g,
      "$1<em>$2</em>",
    );
    text = text.replace(/~~([^~\n]+)~~/g, "<del>$1</del>");
    text = text.replace(
      CODE_RESTORE,
      (_match, index) => `<code>${codes[Number(index)] || ""}</code>`,
    );
    return text;
  }

  function plainText(source) {
    return String(source ?? "")
      .replace(/```[\s\S]*?```/g, " ")
      .replace(/!\[([^\]]*)\]\([^)]*\)/g, "$1 ")
      .replace(/^\s{0,3}(?:#{1,6}|>)\s*/gm, "")
      .replace(/^\s*(?:[-*+]|\d+[.)])\s+/gm, "")
      .replace(/^\s*【([^】]+)】\s*/gm, "$1 ")
      .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
      .replace(/[*_~`|]/g, "")
      .replace(/[ \t]+/g, " ")
      .replace(/\n{2,}/g, "\n")
      .trim();
  }

  function isTableDivider(line) {
    return /^\s*\|?[\s:|-]+\|[\s:|-]*$/.test(line) && String(line).includes("-");
  }

  function tableCells(line) {
    return String(line).trim().replace(/^\|/, "").replace(/\|$/, "")
      .split("|").map((cell) => cell.trim());
  }

  function renderMarkdown(source) {
    const text = String(source ?? "").replace(/\r\n?/g, "\n").trim();
    if (!text) return {html: "", plain: "", blocks: 0, headings: 0};
    const lines = text.split("\n");
    const blocks = [];
    let paragraph = [];
    let listType = "";
    let listItems = [];
    let quoteLines = [];
    let headings = 0;

    const flushParagraph = () => {
      if (!paragraph.length) return;
      blocks.push(`<p>${paragraph.map(inlineMarkdown).join("<br>")}</p>`);
      paragraph = [];
    };
    const flushList = () => {
      if (!listItems.length) {
        listType = "";
        return;
      }
      blocks.push(
        `<${listType}>${listItems.map((item) => `<li>${inlineMarkdown(item)}</li>`).join("")}</${listType}>`,
      );
      listItems = [];
      listType = "";
    };
    const flushQuote = () => {
      if (!quoteLines.length) return;
      blocks.push(
        `<blockquote>${quoteLines.map((line) => `<p>${inlineMarkdown(line)}</p>`).join("")}</blockquote>`,
      );
      quoteLines = [];
    };
    const flushAll = () => {
      flushParagraph();
      flushList();
      flushQuote();
    };
    const pushHeading = (level, value) => {
      headings += 1;
      blocks.push(
        `<h${level} class="announcement-md-heading" data-md-level="${level - 3}">${inlineMarkdown(value)}</h${level}>`,
      );
    };

    let index = 0;
    while (index < lines.length) {
      const line = lines[index];
      if (!line.trim()) {
        flushAll();
        index += 1;
        continue;
      }

      const fence = line.match(FENCE_PATTERN);
      if (fence) {
        flushAll();
        const marker = fence[1];
        const code = [];
        index += 1;
        while (index < lines.length && !lines[index].trim().startsWith(marker)) {
          code.push(lines[index]);
          index += 1;
        }
        index += 1;
        blocks.push(
          `<pre class="announcement-md-code"><code>${escapeHtml(code.join("\n"))}</code></pre>`,
        );
        continue;
      }

      const legacy = line.match(LEGACY_HEADING_PATTERN);
      if (legacy) {
        flushAll();
        pushHeading(5, legacy[1]);
        if (legacy[2].trim()) paragraph.push(legacy[2].trim());
        index += 1;
        continue;
      }

      const atx = line.match(HEADING_PATTERN);
      if (atx) {
        flushAll();
        pushHeading(Math.min(6, atx[1].length + 3), atx[2]);
        index += 1;
        continue;
      }

      if (RULE_PATTERN.test(line)) {
        flushAll();
        blocks.push("<hr>");
        index += 1;
        continue;
      }

      const quote = line.match(QUOTE_PATTERN);
      if (quote) {
        flushParagraph();
        flushList();
        quoteLines.push(quote[1]);
        index += 1;
        continue;
      }
      flushQuote();

      const unordered = line.match(UNORDERED_PATTERN);
      const ordered = unordered ? null : line.match(ORDERED_PATTERN);
      if (unordered || ordered) {
        flushParagraph();
        const nextType = unordered ? "ul" : "ol";
        if (listType && listType !== nextType) flushList();
        listType = nextType;
        listItems.push((unordered || ordered)[1]);
        index += 1;
        continue;
      }
      flushList();

      const imagePair = line.match(IMAGE_PAIR_PATTERN);
      if (imagePair) {
        const left = safeImageTarget(imagePair[2]);
        const right = safeImageTarget(imagePair[4]);
        if (left && right) {
          flushAll();
          blocks.push(
            `<div class="announcement-media-row">${figureHtml(imagePair[1].trim(), left)}${figureHtml(imagePair[3].trim(), right)}</div>`,
          );
          index += 1;
          continue;
        }
      }

      const imageOnly = line.match(IMAGE_ONLY_PATTERN);
      if (imageOnly) {
        const target = safeImageTarget(imageOnly[2]);
        if (target) {
          flushAll();
          blocks.push(figureHtml(imageOnly[1].trim(), target));
          index += 1;
          continue;
        }
      }

      if (
        TABLE_ROW_PATTERN.test(line)
        && index + 1 < lines.length
        && isTableDivider(lines[index + 1])
      ) {
        flushParagraph();
        const header = tableCells(line);
        index += 2;
        const rows = [];
        while (index < lines.length && TABLE_ROW_PATTERN.test(lines[index])) {
          rows.push(tableCells(lines[index]));
          index += 1;
        }
        const body = rows.length
          ? `<tbody>${rows.map((row) => (
            `<tr>${header.map((_cell, column) => (
              `<td>${inlineMarkdown(row[column] || "")}</td>`
            )).join("")}</tr>`
          )).join("")}</tbody>`
          : "";
        blocks.push(
          `<div class="announcement-md-table-wrap"><table class="announcement-md-table"><thead><tr>${header.map((cell) => `<th>${inlineMarkdown(cell)}</th>`).join("")}</tr></thead>${body}</table></div>`,
        );
        continue;
      }

      paragraph.push(line.trim());
      index += 1;
    }
    flushAll();

    return {
      html: blocks.join(""),
      plain: plainText(text),
      blocks: blocks.length,
      headings,
    };
  }

  function tagChips(entry, t) {
    const tags = Array.isArray(entry.tags) ? entry.tags : [];
    if (!tags.length) return "";
    return `<span class="announcement-tags">${tags.map((tag) => (
      `<span class="announcement-tag" data-tag-tone="${escapeHtml(TAG_TONES[tag] || "grey")}">${escapeHtml(t(`announce.tag.${tag}`))}</span>`
    )).join("")}</span>`;
  }

  function renderBody(entry) {
    return entry.rendered || renderMarkdown(entry.body);
  }

  function figureHtml(caption, target) {
    return `<figure class="announcement-figure"><img class="announcement-image" src="${escapeHtml(target)}" alt="${caption}" loading="lazy" decoding="async">${caption ? `<figcaption>${caption}</figcaption>` : ""}</figure>`;
  }

  function cardHtml(entry, {t = (key) => key, expanded = false} = {}) {
    const body = renderBody(entry);
    const long = !entry.alwaysOpen && (
      body.plain.length > COLLAPSED_PLAIN_LENGTH
      || body.blocks > COLLAPSED_BLOCK_LIMIT
    );
    const collapsed = Boolean(long && !expanded);
    const titleId = `announcement-title-${entry.id}`;
    const bodyId = `announcement-body-${entry.id}`;
    const heads = [
      `<span class="announcement-author"><i data-lucide="badge-check"></i>${escapeHtml(entry.author || "")}</span>`,
      `<time class="announcement-stamp" datetime="${escapeHtml(entry.date)}">${escapeHtml(entry.stamp)}</time>`,
      entry.pinned ? `<span class="announcement-pinned">${escapeHtml(t("announce.pinned"))}</span>` : "",
      entry.version ? `<span class="announcement-version">${escapeHtml(entry.version)}</span>` : "",
      tagChips(entry, t),
    ].filter(Boolean).join("");
    const toggle = long
      ? `<button type="button" class="announcement-toggle" data-announcement-toggle aria-expanded="${collapsed ? "false" : "true"}" aria-controls="${bodyId}">${escapeHtml(t(collapsed ? "announce.expand" : "announce.collapse"))}<i data-lucide="${collapsed ? "chevron-down" : "chevron-up"}"></i></button>`
      : "";
    return `<article class="announcement-card${entry.pinned ? " is-pinned" : ""}" data-announcement-id="${escapeHtml(entry.id)}" aria-labelledby="${titleId}">
      <header class="announcement-card-head">${heads}</header>
      <h3 class="announcement-title" id="${titleId}">${escapeHtml(entry.title)}</h3>
      <div class="announcement-body${collapsed ? " is-collapsed" : ""}" id="${bodyId}" data-announcement-body>${body.html}</div>
      ${toggle}
    </article>`;
  }

  function tagCounts(entries) {
    const counts = Object.create(null);
    for (const entry of entries) {
      for (const tag of entry.tags || []) {
        counts[tag] = (counts[tag] || 0) + 1;
      }
    }
    return counts;
  }

  function filtersHtml(entries, {tag = "all", t = (key) => key} = {}) {
    const counts = tagCounts(entries);
    const ids = ["all", ...TAG_IDS.filter((id) => counts[id])];
    return ids.map((id) => {
      const count = id === "all" ? entries.length : counts[id];
      const label = id === "all" ? t("announce.filter.all") : t(`announce.tag.${id}`);
      const pressed = id === tag ? "true" : "false";
      return `<button type="button" class="announcement-filter" data-announcement-filter="${escapeHtml(id)}" aria-pressed="${pressed}"><span class="announcement-filter-label">${escapeHtml(label)}</span><span class="announcement-filter-count">${count}</span></button>`;
    }).join("");
  }

  function entries(t = (key) => key) {
    const resolved = [];
    for (const definition of BOARD) {
      const titleKey = `${definition.key}.title`;
      const bodyKey = `${definition.key}.body`;
      const title = String(t(titleKey) || "");
      const body = String(t(bodyKey) || "");
      if (!title || title === titleKey || !body || body === bodyKey) continue;
      const rendered = renderMarkdown(body);
      resolved.push({
        id: String(definition.id),
        key: String(definition.key),
        date: String(definition.date),
        time: String(definition.time || "00:00"),
        stamp: `${definition.date} ${definition.time || "00:00"}`,
        pinned: Boolean(definition.pinned),
        alwaysOpen: Boolean(definition.alwaysOpen),
        version: String(definition.version || ""),
        tags: Array.isArray(definition.tags) ? [...definition.tags] : [],
        title,
        body,
        rendered,
        plain: rendered.plain,
        author: String(t("announce.author") || ""),
      });
    }
    return resolved;
  }

  function stampKey(entry) {
    return `${entry.date}T${entry.time || "00:00"}`;
  }

  function newestId(entriesList) {
    if (!entriesList.length) return "";
    return entriesList.reduce(
      (newest, entry) => (stampKey(entry) > stampKey(newest) ? entry : newest),
      entriesList[0],
    ).id;
  }

  /* Permanent notice first, then (pinned mode) the pinned group, then the
     rest. Every group is newest first, so the board never depends on the
     literal array order once an entry is dated. */
  function orderedEntries(entriesList, {mode = "pinned", permanentKey = ""} = {}) {
    const permanent = entriesList.filter((entry) => permanentKey && entry.key === permanentKey);
    const rest = entriesList
      .filter((entry) => !permanentKey || entry.key !== permanentKey)
      .slice()
      .sort((left, right) => (
        stampKey(right).localeCompare(stampKey(left)) || left.id.localeCompare(right.id)
      ));
    if (SORT_MODES.includes(mode) && mode === "newest") return [...permanent, ...rest];
    return [
      ...permanent,
      ...rest.filter((entry) => entry.pinned),
      ...rest.filter((entry) => !entry.pinned),
    ];
  }

  function filterEntries(entriesList, {
    tag = "all", query = "", tagLabel = () => "",
  } = {}) {
    const needle = String(query || "").trim().toLocaleLowerCase();
    return entriesList.filter((entry) => {
      if (tag !== "all" && !(entry.tags || []).includes(tag)) return false;
      if (!needle) return true;
      const haystack = [
        entry.title,
        entry.plain,
        entry.version,
        ...(entry.tags || []).map((id) => tagLabel(id)),
      ].join("\n").toLocaleLowerCase();
      return haystack.includes(needle);
    });
  }

  window.FMSDDAnnouncements = Object.freeze({
    BOARD, TAG_TONES, TAG_IDS, SORT_MODES,
    COLLAPSED_PLAIN_LENGTH, COLLAPSED_BLOCK_LIMIT,
    escapeHtml, inlineMarkdown, plainText, renderMarkdown,
    entries, newestId, orderedEntries, filterEntries, tagCounts,
    cardHtml, filtersHtml,
  });
})();

