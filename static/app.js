const state = {
  articles: [],
  activeTag: "ALL",
  selectedId: null,
  dateLabel: null,
};

const listEl = document.getElementById("article-list");
const detailEl = document.getElementById("detail");
const tagRowEl = document.getElementById("tag-row");
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
const exportFavoritesBtn = document.getElementById("export-favorites");
const importFavoritesInput = document.getElementById("import-favorites");
const favoritesStatusEl = document.getElementById("favorites-status");
const todayLabelEl = document.getElementById("today-label");
const lastSyncEl = document.getElementById("last-sync");
const syncStatusEl = document.getElementById("sync-status");
const TAIWAN_TZ = "Asia/Taipei";
const FAVORITES_KEY = "nephro_brain_favorites";

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

const FRAMEWORK_LABELS = {
  TREATMENT_PICO: "治療／策略（PICO）",
  DIAG_OR_ETIOLOGY_FRAME: "診斷／病因／預後",
  MECHANISTIC_PRECLINICAL: "機轉／前臨床",
  REVIEW_GUIDELINE: "回顧／指南",
  OBSERVATIONAL_ASSOCIATION: "觀察性關聯",
  OTHER: "其他",
};

const SECTION_LABELS = {
  framework_reason: "分類理由",
  P: "P（Population）",
  I: "I（Intervention / Exposure）",
  C: "C（Comparison）",
  O_primary: "O（Primary）",
  O_secondary: "O（Secondary）",
  O_safety: "O（Safety）",
  O: "O（Outcome）",
  Implication: "Implication",
  Model: "Model",
  Manipulation: "Manipulation",
  Readouts: "Readouts",
  Mechanism: "Mechanism",
  "So what": "So what",
  "Exposure/Marker": "Exposure/Marker",
  Outcomes: "Outcomes",
  "Key results": "Key results",
  "Confounding/limits": "Confounding/limits",
  Scope: "Scope",
  "Data sources": "Data sources",
  "Key conclusions": "Key conclusions",
  "Evidence strength": "Evidence strength",
  key_points: "重點整理",
};

const MECHANISTIC_SECTION_LABELS = {
  P: "P（模型/樣本）",
  I: "I（操作/介入）",
  C: "C（對照）",
  O: "O（Readouts）",
};

const SECTION_ORDER = {
  TREATMENT_PICO: [
    "framework_reason",
    "P",
    "I",
    "C",
    "O_primary",
    "O_secondary",
    "O_safety",
  ],
  DIAG_OR_ETIOLOGY_FRAME: [
    "framework_reason",
    "P",
    "I",
    "C",
    "O",
    "Implication",
  ],
  MECHANISTIC_PRECLINICAL: [
    "framework_reason",
    "P",
    "I",
    "C",
    "O",
  ],
  OBSERVATIONAL_ASSOCIATION: [
    "framework_reason",
    "P",
    "Exposure/Marker",
    "Outcomes",
    "Key results",
    "Confounding/limits",
    "So what",
  ],
  REVIEW_GUIDELINE: [
    "framework_reason",
    "Scope",
    "Data sources",
    "Key conclusions",
    "Evidence strength",
  ],
  OTHER: ["framework_reason", "key_points"],
};

const renderSummarySection = (title, items) => {
  const safeItems = Array.isArray(items) ? items : [String(items || "UNKNOWN")];
  return `
    <div class="summary-section">
      <div class="summary-section-title">${escapeHtml(title)}</div>
      <ul class="summary-list">
        ${safeItems
          .map((item, idx) => {
            return `
              <li>
                <div class="summary-item">${escapeHtml(item)}</div>
              </li>
            `;
          })
          .join("")}
      </ul>
    </div>
  `;
};

const renderSummaryPayload = (summary) => {
  if (!summary || typeof summary !== "object") {
    return renderSummaryText(summary);
  }
  const framework = summary.framework || "UNKNOWN";
  const oneLiner = summary.one_liner || "UNKNOWN";
  const sections =
    summary.sections && typeof summary.sections === "object" ? summary.sections : {};
  const qualityFlags = Array.isArray(summary.quality_flags)
    ? summary.quality_flags
    : [];

  const order = SECTION_ORDER[framework] || Object.keys(sections);
  const orderedKeys = [
    ...order,
    ...Object.keys(sections).filter((key) => !order.includes(key)),
  ].filter((key) => typeof sections[key] !== "undefined");

  const labelMap =
    framework === "MECHANISTIC_PRECLINICAL"
      ? { ...SECTION_LABELS, ...MECHANISTIC_SECTION_LABELS }
      : SECTION_LABELS;
  const sectionHtml = orderedKeys
    .map((key) => renderSummarySection(labelMap[key] || key, sections[key]))
    .join("");

  const qualityHtml = qualityFlags.length
    ? `<div class="summary-flags">品質標記：${qualityFlags
        .map((flag) => escapeHtml(flag))
        .join("、")}</div>`
    : "";

  return `
    <div class="summary-meta">
      <div class="summary-framework">框架：${escapeHtml(
        FRAMEWORK_LABELS[framework] || framework
      )}</div>
      <div class="summary-one-liner">${escapeHtml(oneLiner)}</div>
    </div>
    ${sectionHtml || "<p>UNKNOWN</p>"}
    ${qualityHtml}
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

const buildTagButton = (tag) => {
  const button = document.createElement("button");
  button.className = `tag ${state.activeTag === tag.value ? "active" : ""}`;
  button.textContent = tag.label;
  button.addEventListener("click", () => {
    state.activeTag = tag.value;
    render();
  });
  return button;
};

const renderTags = () => {
  tagRowEl.innerHTML = "";
  const tagSet = new Set();
  state.articles.forEach((article) => {
    article.tags.forEach((tag) => tagSet.add(tag));
  });
  const tags = [
    { label: "全部", value: "ALL" },
    { label: "已收藏", value: "FAVORITES" },
  ];
  Array.from(tagSet).forEach((tag) => tags.push({ label: tag, value: tag }));
  tags.forEach((tag) => tagRowEl.appendChild(buildTagButton(tag)));
};

const renderList = () => {
  listEl.innerHTML = "";
  let articles = state.articles;
  if (state.activeTag === "FAVORITES") {
    articles = articles.filter((article) => article.favorite);
  } else if (state.activeTag !== "ALL") {
    articles = articles.filter((article) => article.tags.includes(state.activeTag));
  }
  resultCountEl.textContent = `${articles.length} 篇`;
  if (articles.length === 0) {
    const empty = document.createElement("div");
    empty.className = "empty-state";
    if (state.activeTag === "FAVORITES") {
      empty.textContent = "尚未收藏文章。";
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
      ${
        article.title_zh
          ? `<div class="article-title-zh">${escapeHtml(article.title_zh)}</div>`
          : ""
      }
      <div class="article-meta">
        <span>${escapeHtml(article.journal)}</span>
        <span>${escapeHtml(article.publish_date)}</span>
        <span>${escapeHtml(article.study_type)}</span>
      </div>
      <div class="article-meta">
        ${article.tags.map((tag) => `<span class="tag-pill">${escapeHtml(tag)}</span>`).join("")}
        ${article.favorite ? `<span class="tag-pill">已收藏</span>` : ""}
      </div>
    `;
    card.addEventListener("click", () => {
      state.selectedId = article.id;
      renderDetail();
      if (window.matchMedia("(max-width: 900px)").matches && detailPanelEl) {
        setTimeout(() => {
          detailPanelEl.scrollIntoView({ behavior: "smooth", block: "start" });
        }, 0);
      }
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
        ${
          article.title_zh
            ? `<div class="detail-title-zh">${escapeHtml(article.title_zh)}</div>`
            : ""
        }
        <div class="article-meta">
          <span>${escapeHtml(article.journal)}</span>
          <span>${escapeHtml(article.publish_date)}</span>
          <span>${escapeHtml(article.study_type)}</span>
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
      <h3>摘要</h3>
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
        <p class="muted">尚未生成摘要總結。</p>
        <button class="ghost small" id="summary-btn">摘要總結</button>
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
        if (!response.ok) {
          throw new Error("summary fetch failed");
        }
        const data = await response.json();
        article.summary = data || "UNKNOWN";
        renderDetail();
      } catch (error) {
        console.error(error);
        summaryBtn.textContent = "生成失敗，請重試";
        summaryBtn.disabled = false;
      }
    });
  }
};

const render = () => {
  renderTags();
  renderList();
  renderDetail();
};

const setRangeStatus = (message) => {
  if (!rangeStatusEl) return;
  rangeStatusEl.textContent = message || "";
};

const validateRange = (startDate, endDate) => {
  if (!startDate || !endDate) {
    return { ok: false, message: "請選擇完整的區間日期。" };
  }
  const start = new Date(startDate);
  const end = new Date(endDate);
  if (Number.isNaN(start.getTime()) || Number.isNaN(end.getTime())) {
    return { ok: false, message: "日期格式不正確。" };
  }
  if (start > end) {
    return { ok: false, message: "起始日期不可晚於結束日期。" };
  }
  const diffDays = Math.floor((end - start) / (24 * 60 * 60 * 1000)) + 1;
  if (diffDays > 30) {
    return { ok: false, message: "查詢區間最多 30 天。" };
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

const loadArticlesForDate = async (dateValue) => {
  if (!dateValue) {
    await loadArticles();
    return;
  }
  const response = await fetch(`/api/articles?date=${dateValue}`);
  const data = await response.json();
  state.articles = applyFavorites(data.articles);
  state.dateLabel = dateValue;
  state.selectedId = state.articles[0] ? state.articles[0].id : null;
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
  render();
};

const loadArticlesForRange = async (startDate, endDate) => {
  const validation = validateRange(startDate, endDate);
  if (!validation.ok) {
    setRangeStatus(validation.message);
    return;
  }
  setRangeStatus("");
  const response = await fetch(`/api/articles?start=${startDate}&end=${endDate}`);
  const data = await response.json();
  if (!response.ok) {
    setRangeStatus("區間查詢失敗，請確認日期。");
    return;
  }
  state.articles = applyFavorites(data.articles);
  state.dateLabel = data.date || endDate;
  state.selectedId = state.articles[0] ? state.articles[0].id : null;
  render();
  setRangeStatus(data.articles.length ? "" : "該區間沒有文章。");
};

const loadArticles = async (statusOverride) => {
  const today = getTaiwanDate() || new Date().toISOString().slice(0, 10);
  let statusText = statusOverride || "";
  let response = await fetch(`/api/articles?date=${today}`);
  let data = await response.json();
  if (!data.articles.length) {
    response = await fetch("/api/articles");
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
  render();
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

dateSearchBtn.addEventListener("click", async () => {
  const selectedDate = dateInputEl.value;
  if (!selectedDate) {
    updateSyncInfo(undefined, "請先選擇日期。");
    return;
  }
  dateSearchBtn.disabled = true;
  dateSearchBtn.textContent = "查詢中...";
  try {
    const response = await fetch(`/api/refresh?date=${selectedDate}`, {
      method: "POST",
    });
    const data = await response.json();
    const message =
      response.ok && data.stored === 0 ? "該日期無新文章。" : "";
    await loadArticlesForDate(selectedDate);
    updateSyncInfo(data.last_sync, message);
  } catch (error) {
    console.error(error);
    updateSyncInfo(undefined, "查詢失敗，請稍後再試。");
  } finally {
    dateSearchBtn.disabled = false;
    dateSearchBtn.textContent = "查詢";
  }
});

dateTodayBtn.addEventListener("click", () => {
  const today = getTaiwanDate();
  dateInputEl.value = today;
  loadArticlesForDate(today);
});

if (rangeEndEl) {
  rangeEndEl.value = getTaiwanDate();
}

if (rangeSearchBtn) {
  rangeSearchBtn.addEventListener("click", async () => {
    const startDate = rangeStartEl.value;
    const endDate = rangeEndEl.value;
    const validation = validateRange(startDate, endDate);
    if (!validation.ok) {
      setRangeStatus(validation.message);
      return;
    }
    rangeSearchBtn.disabled = true;
    rangeSearchBtn.textContent = "查詢中...";
    try {
      const response = await fetch(
        `/api/refresh?start=${startDate}&end=${endDate}`,
        { method: "POST" }
      );
      if (!response.ok) {
        setRangeStatus("區間查詢失敗，請確認日期。");
        return;
      }
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
