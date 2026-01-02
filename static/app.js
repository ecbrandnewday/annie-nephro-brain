const state = {
  articles: [],
  selectedId: null,
  dateLabel: null,
  selectedTags: [],
  favoritesOnly: false,
  pagination: {
    mode: "date",
    total: 0,
    limit: 50,
    offset: 0,
    start: null,
    end: null,
    tags: [],
  },
};

const listEl = document.getElementById("article-list");
const detailEl = document.getElementById("detail");
const resultCountEl = document.getElementById("result-count");
const dateChipEl = document.getElementById("today-date");
const refreshBtn = document.getElementById("refresh-btn");
const listPanelEl = document.getElementById("list-panel");
const detailPanelEl = document.getElementById("detail-panel");
const dateInputEl = document.getElementById("date-input");
const dateSearchBtn = document.getElementById("date-search");
const dateTodayBtn = document.getElementById("date-today");
const rangeStartEl = document.getElementById("range-start");
const rangeEndEl = document.getElementById("range-end");
const rangeSearchBtn = document.getElementById("range-search");
const rangeStatusEl = document.getElementById("range-status");
const tagOptionsEl = document.getElementById("tag-options");
const favoritesOnlyEl = document.getElementById("favorites-only");
const loadMoreBtn = document.getElementById("load-more");
const exportFavoritesBtn = document.getElementById("export-favorites");
const importFavoritesInput = document.getElementById("import-favorites");
const favoritesStatusEl = document.getElementById("favorites-status");
const todayLabelEl = document.getElementById("today-label");
const lastSyncEl = document.getElementById("last-sync");
const syncStatusEl = document.getElementById("sync-status");
const TAIWAN_TZ = "Asia/Taipei";
const FAVORITES_KEY = "nephro_brain_favorites";
const DEFAULT_LIMIT = 50;
const INCLUDE_ABSTRACT_PARAM = "&include_abstract=0";

const escapeHtml = (text) =>
  (text || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");

const renderSummaryText = (text) => {
  const lines = String(text || "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  if (!lines.length) {
    return "<p>UNKNOWN</p>";
  }
  const isList = lines.some((line) => line.startsWith("-") || line.startsWith("•"));
  if (isList) {
    const items = lines.map((line) => line.replace(/^[-•]\s*/, ""));
    return `<ul class="summary-list">${items
      .map((item) => `<li>${escapeHtml(item)}</li>`)
      .join("")}</ul>`;
  }
  return lines.map((line) => `<p>${escapeHtml(line)}</p>`).join("");
};

const isUnknown = (value) => String(value || "").trim().toUpperCase() === "UNKNOWN";

const getSummaryText = (summary) => {
  if (summary && typeof summary === "object") {
    return String(summary.summary || "UNKNOWN");
  }
  return String(summary || "UNKNOWN");
};

const copyText = async (text) => {
  if (!text) return false;
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (error) {
      console.error(error);
    }
  }
  try {
    const textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.style.position = "fixed";
    textarea.style.opacity = "0";
    document.body.appendChild(textarea);
    textarea.select();
    const ok = document.execCommand("copy");
    textarea.remove();
    return ok;
  } catch (error) {
    console.error(error);
    return false;
  }
};


const RESEARCH_TYPE_LABELS = {
  A: "Clinical trial / interventional study",
  B: "Observational study",
  C: "Diagnostic / prognostic / biomarker study",
  D: "Systematic review / meta-analysis / narrative review",
  E: "Guideline / consensus / position statement",
  F: "Editorial / commentary / letter / viewpoint",
  G: "Basic / animal / in vitro / mechanistic",
  H: "Other / unclear",
};

const splitItems = (value) => {
  const text = (value || "").trim();
  if (!text) return ["UNKNOWN"];
  const parts = text
    .split(/[；;]\s*|(?<=。)\s*/g)
    .map((part) => part.trim())
    .filter(Boolean);
  return parts.length ? parts : [text];
};

const parseSummaryBlocks = (text) => {
  const lines = String(text || "")
    .split(/\n+/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => line.replace(/^[-•]\s*/, "").trim());
  if (!lines.length) return null;
  let keyTakeaway = "";
  let researchTypeCode = null;
  let researchTypeLabel = "";
  const pico = { P: [], I: [], C: [], O: [] };
  const sections = [];
  const freeformItems = [];

  const addSection = (title, value) => {
    sections.push({ title, items: splitItems(value) });
  };

  for (const line of lines) {
    if (line.startsWith("【研究類型】")) {
      const rest = line.replace("【研究類型】", "").trim();
      const match = rest.match(/^([A-H])/i);
      if (match) {
        researchTypeCode = match[1].toUpperCase();
      }
      const cleanedRest = rest.replace(/^([A-H])\s*[\)\]】\-]?\s*/i, "").trim();
      let matchedLabel = "";
      if (cleanedRest) {
        const normalizedRest = cleanedRest.toLowerCase();
        for (const label of Object.values(RESEARCH_TYPE_LABELS)) {
          if (normalizedRest.startsWith(label.toLowerCase())) {
            matchedLabel = label;
            break;
          }
        }
      }
      researchTypeLabel =
        matchedLabel || cleanedRest || RESEARCH_TYPE_LABELS[researchTypeCode] || "";
      continue;
    }
    if (
      line.startsWith("重點結論：") ||
      line.startsWith("一句話結論：") ||
      line.startsWith("一句話重點：") ||
      line.toLowerCase().startsWith("key takeaway:")
    ) {
      keyTakeaway = line.split(/：|:/).slice(1).join("：").trim();
      continue;
    }
    const picoMatch = line.match(/^([PICO]|I\/INDEX)\s*[:：]\s*(.+)$/i);
    if (picoMatch) {
      const rawKey = picoMatch[1].toUpperCase();
      const key = rawKey === "I/INDEX" ? "I" : rawKey;
      const value = picoMatch[2].trim();
      if (pico[key]) {
        pico[key].push(value || "UNKNOWN");
      }
      continue;
    }
    const parts = line.split(/：|:/);
    if (parts.length > 1) {
      const title = parts[0].trim();
      const value = parts.slice(1).join("：").trim();
      addSection(title, value);
      continue;
    }
    freeformItems.push(line);
  }

  if (!sections.length && freeformItems.length) {
    sections.push({ title: "摘要重點", items: freeformItems });
  }
  const hasPicoLines = Object.values(pico).some((items) => items.length);
  const hasSections = sections.length > 0;
  if (!keyTakeaway && !hasPicoLines && !hasSections) return null;
  if (!keyTakeaway) keyTakeaway = "UNKNOWN";
  if (hasPicoLines) {
    ["P", "I", "C", "O"].forEach((key) => {
      if (!pico[key].length) pico[key].push("UNKNOWN");
    });
  }
  if (!researchTypeLabel && researchTypeCode) {
    researchTypeLabel = RESEARCH_TYPE_LABELS[researchTypeCode] || researchTypeCode;
  }
  return {
    keyTakeaway,
    researchTypeCode,
    researchTypeLabel,
    pico,
    sections,
    hasPicoLines,
  };
};

const renderSummaryRows = (rows) =>
  rows
    .map(
      ({ title, items }) => `
        <div class="summary-row">
          <div class="summary-row-title">${escapeHtml(title)}</div>
          <div class="summary-row-body">
            ${items.map((item) => `<p>${escapeHtml(item)}</p>`).join("")}
          </div>
        </div>
      `
    )
    .join("");

const renderSummaryPayload = (summary) => {
  if (summary && typeof summary === "object") {
    return renderSummaryText(summary.summary || "UNKNOWN");
  }
  const parsed = parseSummaryBlocks(summary || "");
  if (!parsed) {
    return renderSummaryText(summary);
  }

  const typeRow = parsed.researchTypeLabel
    ? `
      <div class="summary-card">
        <div class="summary-card-title">研究類型</div>
        <div class="summary-card-body">
          <p>${escapeHtml(parsed.researchTypeLabel)}</p>
        </div>
      </div>
    `
    : "";

  const takeawayCard = `
    <div class="summary-card highlight-card">
      <div class="summary-card-title">重點結論</div>
      <div class="summary-card-body">
        <p>${escapeHtml(parsed.keyTakeaway)}</p>
      </div>
    </div>
  `;

  const summaryRows = parsed.sections.length
    ? parsed.sections
    : [{ title: "摘要重點", items: ["UNKNOWN"] }];
  const singleSummaryOnly =
    summaryRows.length === 1 && summaryRows[0].title === "摘要重點";
  const isClinical = ["A", "B", "C"].includes(parsed.researchTypeCode);
  if (isClinical) {
    const picoRows = [
      { title: "P", items: parsed.pico.P.length ? parsed.pico.P : ["UNKNOWN"] },
      { title: "I", items: parsed.pico.I.length ? parsed.pico.I : ["UNKNOWN"] },
      { title: "C", items: parsed.pico.C.length ? parsed.pico.C : ["UNKNOWN"] },
      { title: "O", items: parsed.pico.O.length ? parsed.pico.O : ["UNKNOWN"] },
    ];
    const hasPicoContent = picoRows.some((row) =>
      row.items.some((item) => !isUnknown(item))
    );
    if (!hasPicoContent && parsed.sections.length) {
      return `
        <div class="summary-cards">
          ${typeRow}
          ${takeawayCard}
          <div class="summary-card">
            <div class="summary-card-title">摘要重點</div>
            <div class="summary-card-body">
              ${
                singleSummaryOnly
                  ? summaryRows[0].items.map((item) => `<p>${escapeHtml(item)}</p>`).join("")
                  : renderSummaryRows(summaryRows)
              }
            </div>
          </div>
        </div>
      `;
    }
    return `
      <div class="summary-cards">
        ${typeRow}
        ${takeawayCard}
        <div class="summary-card pico-card">
          <div class="summary-card-title pico-title">
            <span class="pico-icon" aria-hidden="true"></span>
            <span>架構</span>
          </div>
          <div class="summary-card-body">
            ${renderSummaryRows(picoRows)}
          </div>
        </div>
      </div>
    `;
  }
  return `
    <div class="summary-cards">
      ${typeRow}
      ${takeawayCard}
      <div class="summary-card">
        <div class="summary-card-title">摘要重點</div>
        <div class="summary-card-body">
          ${
            singleSummaryOnly
              ? summaryRows[0].items.map((item) => `<p>${escapeHtml(item)}</p>`).join("")
              : renderSummaryRows(summaryRows)
          }
        </div>
      </div>
    </div>
  `;
};

const renderAbstract = (text) => {
  const blocks = String(text || "")
    .split(/\n{2,}/)
    .map((line) => line.trim())
    .filter(Boolean);
  if (!blocks.length) {
    return "<p>UNKNOWN</p>";
  }
  return blocks.map((block) => `<p>${escapeHtml(block)}</p>`).join("");
};

const loadFavoriteIds = () => {
  try {
    const raw = localStorage.getItem(FAVORITES_KEY);
    if (!raw) return [];
    const data = JSON.parse(raw);
    if (Array.isArray(data)) {
      return data.map((item) => String(item));
    }
    if (data && Array.isArray(data.favorites)) {
      return data.favorites.map((item) => String(item));
    }
  } catch (error) {
    console.error(error);
  }
  return [];
};

const saveFavoriteIds = (ids) => {
  const unique = Array.from(new Set(ids.map((item) => String(item))));
  try {
    localStorage.setItem(FAVORITES_KEY, JSON.stringify(unique));
  } catch (error) {
    console.error(error);
  }
};

const getFavoriteSet = () => new Set(loadFavoriteIds());

const applyFavorites = (articles) => {
  const favorites = getFavoriteSet();
  articles.forEach((article) => {
    article.favorite = favorites.has(article.id);
  });
  return articles;
};

const getSelectedTags = () => {
  if (!tagOptionsEl) return [];
  return Array.from(tagOptionsEl.querySelectorAll('input[type="checkbox"]'))
    .filter((input) => input.checked)
    .map((input) => input.value);
};

const buildTagParam = (tags) =>
  tags && tags.length ? `&tags=${encodeURIComponent(tags.join(","))}` : "";

const mergeArticleInState = (updated) => {
  if (!updated) return;
  const index = state.articles.findIndex((item) => item.id === updated.id);
  if (index === -1) return;
  state.articles[index] = { ...state.articles[index], ...updated };
};

const detailFetches = new Map();

const fetchArticleDetail = async (articleId) => {
  if (!articleId) return null;
  if (detailFetches.has(articleId)) {
    return detailFetches.get(articleId);
  }
  const request = (async () => {
    try {
      const response = await fetch(`/api/articles/${articleId}`);
      if (!response.ok) return null;
      return await response.json();
    } catch (error) {
      console.error(error);
      return null;
    } finally {
      detailFetches.delete(articleId);
    }
  })();
  detailFetches.set(articleId, request);
  return request;
};

const selectArticle = async (articleId, shouldScroll = false) => {
  state.selectedId = articleId;
  if (!articleId) {
    renderDetail();
    return;
  }
  const article = state.articles.find((item) => item.id === articleId);
  if (!article) {
    renderDetail();
    return;
  }
  if (article.abstract == null) {
    detailEl.innerHTML = `
      <div class="empty-state">
        載入中...
      </div>
    `;
    const fullArticle = await fetchArticleDetail(articleId);
    if (fullArticle) {
      mergeArticleInState(fullArticle);
    }
  }
  if (state.selectedId !== articleId) {
    return;
  }
  renderDetail();
  if (shouldScroll && window.matchMedia("(max-width: 900px)").matches && detailPanelEl) {
    setTimeout(() => {
      detailPanelEl.scrollIntoView({ behavior: "smooth", block: "start" });
    }, 0);
  }
};

const toggleFavorite = (articleId) => {
  const favorites = getFavoriteSet();
  if (favorites.has(articleId)) {
    favorites.delete(articleId);
  } else {
    favorites.add(articleId);
  }
  saveFavoriteIds(Array.from(favorites));
  return favorites.has(articleId);
};

const setFavoritesStatus = (message) => {
  if (!favoritesStatusEl) return;
  favoritesStatusEl.textContent = message || "";
  if (message) {
    setTimeout(() => {
      if (favoritesStatusEl.textContent === message) {
        favoritesStatusEl.textContent = "";
      }
    }, 4000);
  }
};

const renderList = () => {
  listEl.innerHTML = "";
  let articles = state.articles;
  if (state.favoritesOnly) {
    articles = articles.filter((article) => article.favorite);
  }
  if (state.pagination.mode === "range") {
    resultCountEl.textContent = `${articles.length} / ${state.pagination.total} 篇`;
  } else {
    resultCountEl.textContent = `${articles.length} 篇`;
  }
  if (articles.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    if (state.favoritesOnly) {
      empty.textContent = "尚未收藏文章。";
    } else if (state.pagination.mode === "range") {
      empty.textContent = "該區間沒有文章。";
    } else {
      empty.textContent = "這一天沒有文章，請改選其他日期。";
    }
    listEl.appendChild(empty);
    return;
  }

  articles.forEach((article, index) => {
    const card = document.createElement("div");
    card.className = "article-card";
    card.style.setProperty("--i", index);
    card.innerHTML = `
      <div class="article-title">${escapeHtml(article.title)}</div>
      <div class="article-meta">
        <span class="meta-journal">${escapeHtml(article.journal)}</span>
        <span>${escapeHtml(article.publish_date)}</span>
        <span class="meta-type">${escapeHtml(article.study_type)}</span>
      </div>
      <div class="article-meta">
        ${article.tags.map((tag) => `<span class="tag-pill">${escapeHtml(tag)}</span>`).join("")}
        ${article.favorite ? `<span class="tag-pill">已收藏</span>` : ""}
      </div>
    `;
    card.addEventListener("click", () => {
      void selectArticle(article.id, true);
    });
    listEl.appendChild(card);
  });
};

const renderDetail = () => {
  const article = state.articles.find((item) => item.id === state.selectedId);
  if (!article) {
    detailEl.innerHTML = `
      <div class="empty-state">
        選擇文章以查看摘要與摘要總結。
      </div>
    `;
    return;
  }

  detailEl.innerHTML = `
    <div class="detail-header">
      <div>
        <div class="detail-title">${escapeHtml(article.title)}</div>
        <div class="article-meta">
          <span class="meta-journal">${escapeHtml(article.journal)}</span>
          <span>${escapeHtml(article.publish_date)}</span>
          <span class="meta-type">${escapeHtml(article.study_type)}</span>
        </div>
      </div>
      <div class="detail-actions">
        <button class="ghost small back-to-list" id="back-to-list">回到列表</button>
        <a class="pubmed-link" href="${escapeHtml(article.url)}" target="_blank" rel="noreferrer">
          PubMed ↗
        </a>
        <button class="favorite-btn ${article.favorite ? "saved" : ""}" id="favorite-btn">
          ${article.favorite ? "取消收藏" : "收藏"}
        </button>
      </div>
    </div>
    <div class="section">
      <div class="section-header">
        <h3>摘要</h3>
        <button class="ghost small" id="abstract-copy">複製摘要</button>
      </div>
      <div class="abstract-block">
        ${renderAbstract(article.abstract || "UNKNOWN")}
      </div>
    </div>
    <div class="section">
      <h3>摘要總結</h3>
      ${
        article.summary
          ? `
        <div class="summary-block">
          ${renderSummaryPayload(article.summary)}
        </div>
      `
          : `
        <p class="muted">尚未生成摘要。</p>
        <button class="ghost small" id="summary-btn">產出摘要</button>
      `
      }
    </div>
  `;

  const favoriteBtn = document.getElementById("favorite-btn");
  favoriteBtn.addEventListener("click", (event) => {
    event.stopPropagation();
    article.favorite = toggleFavorite(article.id);
    render();
  });

  const backBtn = document.getElementById("back-to-list");
  if (backBtn && listPanelEl) {
    backBtn.addEventListener("click", (event) => {
      event.stopPropagation();
      listPanelEl.scrollIntoView({ behavior: "smooth", block: "start" });
    });
  }

  const summaryBtn = document.getElementById("summary-btn");
  if (summaryBtn) {
    summaryBtn.addEventListener("click", async () => {
      summaryBtn.disabled = true;
      summaryBtn.textContent = "生成中...";
      try {
        const response = await fetch(`/api/articles/${article.id}/summary`, {
          method: "POST",
        });
        const data = await response.json();
        if (!response.ok || data.ok === false) {
          const message = data.error || "summary fetch failed";
          throw new Error(message);
        }
        article.summary = data.summary || "UNKNOWN";
        renderDetail();
      } catch (error) {
        console.error(error);
        const message = error?.message || "生成失敗，請重試";
        summaryBtn.textContent = `生成失敗：${message}`.slice(0, 80);
        summaryBtn.disabled = false;
      }
    });
  }

  const abstractCopyBtn = document.getElementById("abstract-copy");
  if (abstractCopyBtn) {
    abstractCopyBtn.addEventListener("click", async () => {
      const text = String(article.abstract || "UNKNOWN");
      const ok = await copyText(text);
      abstractCopyBtn.textContent = ok ? "已複製" : "複製失敗";
      setTimeout(() => {
        abstractCopyBtn.textContent = "複製摘要";
      }, 1500);
    });
  }
};

const render = () => {
  renderList();
  void selectArticle(state.selectedId);
};

const updateLoadMoreVisibility = () => {
  if (!loadMoreBtn) return;
  if (state.pagination.mode !== "range") {
    loadMoreBtn.style.display = "none";
    return;
  }
  const nextOffset = state.pagination.offset + state.pagination.limit;
  loadMoreBtn.style.display =
    nextOffset < state.pagination.total ? "inline-flex" : "none";
};

const setRangeStatus = (message) => {
  if (!rangeStatusEl) return;
  rangeStatusEl.textContent = message || "";
};

const parseMonthValue = (value) => {
  if (!value) return null;
  const parts = value.split("-");
  if (parts.length !== 2) return null;
  const year = Number(parts[0]);
  const month = Number(parts[1]);
  if (!year || !month || month < 1 || month > 12) return null;
  return { year, month };
};

const validateMonthRange = (startMonth, endMonth) => {
  if (!startMonth || !endMonth) {
    return { ok: false, message: "請選擇完整的月份區間。" };
  }
  const start = parseMonthValue(startMonth);
  const end = parseMonthValue(endMonth);
  if (!start || !end) {
    return { ok: false, message: "月份格式不正確。" };
  }
  const startIndex = start.year * 12 + start.month;
  const endIndex = end.year * 12 + end.month;
  if (startIndex > endIndex) {
    return { ok: false, message: "起始月份不可晚於結束月份。" };
  }
  const monthSpan = endIndex - startIndex + 1;
  if (monthSpan > 12) {
    return { ok: false, message: "查詢區間最多 12 個月。" };
  }
  return { ok: true };
};

const updateSyncInfo = (lastSync, statusText) => {
  if (!lastSyncEl && !syncStatusEl) {
    return;
  }
  if (typeof lastSync !== "undefined") {
    if (lastSync) {
      const normalized =
        /[zZ]|[+-]\d{2}:\d{2}$/.test(lastSync) ? lastSync : `${lastSync}Z`;
      const date = new Date(normalized);
      const localized = Number.isNaN(date.getTime())
        ? lastSync
        : date.toLocaleString("zh-TW", { timeZone: TAIWAN_TZ });
      if (lastSyncEl) {
        lastSyncEl.textContent = `最後同步：${localized}`;
      }
    } else {
      if (lastSyncEl) {
        lastSyncEl.textContent = "";
      }
    }
  }
  if (syncStatusEl) {
    syncStatusEl.textContent = statusText || "";
  }
};

const getTaiwanDate = () => {
  const formatter = new Intl.DateTimeFormat("zh-TW", {
    timeZone: TAIWAN_TZ,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
  const parts = formatter.formatToParts(new Date());
  const year = parts.find((part) => part.type === "year")?.value;
  const month = parts.find((part) => part.type === "month")?.value;
  const day = parts.find((part) => part.type === "day")?.value;
  return year && month && day ? `${year}-${month}-${day}` : "";
};

const getTaiwanMonth = () => {
  const today = getTaiwanDate();
  return today ? today.slice(0, 7) : "";
};

const monthToDateRange = (monthValue, isEnd) => {
  const parsed = parseMonthValue(monthValue);
  if (!parsed) return null;
  const start = new Date(parsed.year, parsed.month - 1, 1);
  if (!isEnd) {
    return start.toISOString().slice(0, 10);
  }
  const end = new Date(parsed.year, parsed.month, 0);
  return end.toISOString().slice(0, 10);
};

const loadArticlesForDate = async (dateValue) => {
  if (!dateValue) {
    await loadArticles();
    return;
  }
  const tags = getSelectedTags();
  const tagParam = buildTagParam(tags);
  const response = await fetch(
    `/api/articles?date=${dateValue}&limit=${DEFAULT_LIMIT}${tagParam}${INCLUDE_ABSTRACT_PARAM}`
  );
  const data = await response.json();
  state.articles = applyFavorites(data.articles);
  state.dateLabel = dateValue;
  state.selectedId = state.articles[0] ? state.articles[0].id : null;
  state.pagination = {
    mode: "date",
    total: data.articles.length,
    limit: DEFAULT_LIMIT,
    offset: 0,
    start: null,
    end: null,
    tags,
  };
  if (dateChipEl) {
    dateChipEl.textContent = `查詢日期 ${state.dateLabel}`;
  }
  updateSyncInfo(
    data.last_sync,
    data.articles.length ? "" : "該日期無文章。"
  );
  if (dateInputEl) {
    dateInputEl.value = dateValue;
  }
  updateLoadMoreVisibility();
  render();
};

const loadArticlesForRange = async (startMonth, endMonth) => {
  const validation = validateMonthRange(startMonth, endMonth);
  if (!validation.ok) {
    setRangeStatus(validation.message);
    return;
  }
  setRangeStatus("");
  const tags = getSelectedTags();
  const tagParam = buildTagParam(tags);
  const response = await fetch(
    `/api/articles/range?start=${startMonth}&end=${endMonth}&limit=${DEFAULT_LIMIT}&offset=0${tagParam}${INCLUDE_ABSTRACT_PARAM}`
  );
  if (!response.ok) {
    try {
      const errorData = await response.json();
      setRangeStatus(errorData.error || "區間查詢失敗，請確認日期。");
    } catch (error) {
      setRangeStatus("區間查詢失敗，請確認日期。");
    }
    return;
  }
  const data = await response.json();
  state.articles = applyFavorites(data.items);
  state.dateLabel = endMonth;
  state.selectedId = state.articles[0] ? state.articles[0].id : null;
  state.pagination = {
    mode: "range",
    total: data.total,
    limit: DEFAULT_LIMIT,
    offset: 0,
    start: startMonth,
    end: endMonth,
    tags,
  };
  if (dateChipEl) {
    dateChipEl.textContent = `查詢月份 ${startMonth} - ${endMonth}`;
  }
  render();
  updateLoadMoreVisibility();
  setRangeStatus(data.items.length ? "" : "該區間沒有文章。");
};

const loadArticles = async (statusOverride) => {
  const today = getTaiwanDate() || new Date().toISOString().slice(0, 10);
  let statusText = statusOverride || "";
  const tags = state.pagination.tags || [];
  const tagParam = buildTagParam(tags);
  let response = await fetch(
    `/api/articles?date=${today}&limit=${DEFAULT_LIMIT}${tagParam}${INCLUDE_ABSTRACT_PARAM}`
  );
  let data = await response.json();
  if (!data.articles.length) {
    response = await fetch(
      `/api/articles?limit=${DEFAULT_LIMIT}${tagParam}${INCLUDE_ABSTRACT_PARAM}`
    );
    data = await response.json();
    if (!statusOverride) {
      if (data.articles.length) {
        statusText = "今日無新文章，已顯示最新日期。";
      } else {
        statusText = "目前沒有可顯示的文章。";
      }
    }
  }
  state.articles = applyFavorites(data.articles);
  state.dateLabel = data.date || today;
  state.selectedId = state.articles[0] ? state.articles[0].id : null;
  state.pagination = {
    mode: "date",
    total: data.articles.length,
    limit: DEFAULT_LIMIT,
    offset: 0,
    start: null,
    end: null,
    tags,
  };
  if (dateChipEl) {
    dateChipEl.textContent = `更新至 ${state.dateLabel}`;
  }
  if (todayLabelEl) {
    todayLabelEl.textContent = `今日日期：${today}`;
  }
  if (dateInputEl) {
    dateInputEl.value = today;
  }
  updateSyncInfo(data.last_sync, statusText);
  updateLoadMoreVisibility();
  render();
};

const loadMoreRange = async () => {
  if (state.pagination.mode !== "range") return;
  const nextOffset = state.pagination.offset + state.pagination.limit;
  if (nextOffset >= state.pagination.total) {
    updateLoadMoreVisibility();
    return;
  }
  const tags = getSelectedTags();
  const tagParam = buildTagParam(tags);
  const response = await fetch(
    `/api/articles/range?start=${state.pagination.start}&end=${state.pagination.end}` +
      `&limit=${state.pagination.limit}&offset=${nextOffset}${tagParam}${INCLUDE_ABSTRACT_PARAM}`
  );
  if (!response.ok) {
    setRangeStatus("載入更多失敗，請稍後再試。");
    return;
  }
  const data = await response.json();
  const newItems = applyFavorites(data.items || []);
  state.articles = state.articles.concat(newItems);
  state.pagination.offset = nextOffset;
  render();
  updateLoadMoreVisibility();
};

if (refreshBtn) {
  refreshBtn.addEventListener("click", async () => {
    refreshBtn.disabled = true;
    refreshBtn.textContent = "更新中...";
    let handled = false;
    try {
      const response = await fetch("/api/refresh", { method: "POST" });
      const data = await response.json();
      if (data.stored === 0) {
        await loadArticles("今日無新文章，已顯示最新日期。");
        handled = true;
      }
    } catch (error) {
      console.error(error);
    } finally {
      if (!handled) {
        await loadArticles();
      }
      refreshBtn.disabled = false;
      refreshBtn.textContent = "更新";
    }
  });
}

if (dateInputEl) {
  dateInputEl.value = getTaiwanDate();
}

if (tagOptionsEl) {
  tagOptionsEl.addEventListener("change", () => {
    state.selectedTags = getSelectedTags();
  });
}

if (favoritesOnlyEl) {
  favoritesOnlyEl.addEventListener("change", () => {
    state.favoritesOnly = favoritesOnlyEl.checked;
    render();
  });
}

const runDateSearch = async () => {
  const selectedDate = dateInputEl ? dateInputEl.value : "";
  if (!selectedDate) {
    updateSyncInfo(undefined, "請先選擇日期。");
    return;
  }
  if (dateSearchBtn) {
    dateSearchBtn.disabled = true;
    dateSearchBtn.textContent = "查詢中...";
  }
  try {
    await loadArticlesForDate(selectedDate);
    updateSyncInfo(undefined, state.articles.length ? "" : "該日期無文章。");
  } catch (error) {
    console.error(error);
    updateSyncInfo(undefined, "查詢失敗，請稍後再試。");
  } finally {
    if (dateSearchBtn) {
      dateSearchBtn.disabled = false;
      dateSearchBtn.textContent = "查詢";
    }
  }
};

if (dateSearchBtn) {
  dateSearchBtn.addEventListener("click", runDateSearch);
}

if (dateInputEl) {
  dateInputEl.addEventListener("change", runDateSearch);
}

if (dateTodayBtn) {
  dateTodayBtn.addEventListener("click", () => {
    const today = getTaiwanDate();
    if (dateInputEl) {
      dateInputEl.value = today;
    }
    loadArticlesForDate(today);
  });
}

if (rangeEndEl) {
  rangeEndEl.value = getTaiwanMonth();
}
if (rangeStartEl) {
  rangeStartEl.value = getTaiwanMonth();
}

if (rangeSearchBtn) {
  rangeSearchBtn.addEventListener("click", async () => {
    const startDate = rangeStartEl.value;
    const endDate = rangeEndEl.value;
    rangeSearchBtn.disabled = true;
    rangeSearchBtn.textContent = "查詢中...";
    try {
      const validation = validateMonthRange(startDate, endDate);
      if (!validation.ok) {
        setRangeStatus(validation.message);
        return;
      }
      const startDateValue = monthToDateRange(startDate, false);
      const endDateValue = monthToDateRange(endDate, true);
      if (!startDateValue || !endDateValue) {
        setRangeStatus("月份格式不正確。");
        return;
      }
      setRangeStatus("匯入中，請稍候...");
      const refreshResponse = await fetch(
        `/api/refresh?start=${startDateValue}&end=${endDateValue}&max_per_journal=0`,
        { method: "POST" }
      );
      if (!refreshResponse.ok) {
        const errorData = await refreshResponse.json();
        setRangeStatus(errorData.error || "匯入失敗，請確認日期。");
        return;
      }
      setRangeStatus("匯入完成，正在載入...");
      await loadArticlesForRange(startDate, endDate);
    } catch (error) {
      console.error(error);
      setRangeStatus("區間查詢失敗，請稍後再試。");
    } finally {
      rangeSearchBtn.disabled = false;
      rangeSearchBtn.textContent = "查詢區間";
    }
  });
}

if (loadMoreBtn) {
  loadMoreBtn.addEventListener("click", async () => {
    loadMoreBtn.disabled = true;
    loadMoreBtn.textContent = "載入中...";
    try {
      await loadMoreRange();
    } finally {
      loadMoreBtn.disabled = false;
      loadMoreBtn.textContent = "載入更多";
    }
  });
}

const getImportMode = () => {
  const selected = document.querySelector('input[name="import-mode"]:checked');
  return selected ? selected.value : "merge";
};

if (exportFavoritesBtn) {
  exportFavoritesBtn.addEventListener("click", () => {
    const favorites = loadFavoriteIds();
    const payload = JSON.stringify(favorites, null, 2);
    const blob = new Blob([payload], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = "favorites.json";
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    setFavoritesStatus("已下載 favorites.json");
  });
}

if (importFavoritesInput) {
  importFavoritesInput.addEventListener("change", () => {
    const file = importFavoritesInput.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const data = JSON.parse(reader.result);
        let imported = [];
        if (Array.isArray(data)) {
          imported = data;
        } else if (data && Array.isArray(data.favorites)) {
          imported = data.favorites;
        }
        const normalized = imported.map((item) => String(item)).filter(Boolean);
        const mode = getImportMode();
        if (mode === "replace") {
          saveFavoriteIds(normalized);
        } else {
          const merged = new Set([...loadFavoriteIds(), ...normalized]);
          saveFavoriteIds(Array.from(merged));
        }
        applyFavorites(state.articles);
        render();
        setFavoritesStatus("收藏已匯入");
      } catch (error) {
        console.error(error);
        setFavoritesStatus("匯入失敗，請確認檔案格式。");
      } finally {
        importFavoritesInput.value = "";
      }
    };
    reader.readAsText(file);
  });
}

loadArticles();
