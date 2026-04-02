// ==========================================
// CONFIGURATION & STATE
// ==========================================
const DATA_PATHS = {
    institutions: "./data/institutions.json",
    ccRegistry: "./data/colleges/cc_registry.json",
    subjectCategories: (uni) => `./data/universities/${encodeURIComponent(uni)}/Subjects/subjects.json`,
    subjectItems: (uni, prefix) => `./data/universities/${encodeURIComponent(uni)}/Subjects/subj_${encodeURIComponent(prefix)}.json`,
    majorCategories: (uni) => `./data/universities/${encodeURIComponent(uni)}/Majors/majors.json`,
    majorItems: (uni, major) => `./data/universities/${encodeURIComponent(uni)}/Majors/${encodeURIComponent(getSafeFileName(major))}.json`,
    geCategories: (uni) => `./data/universities/${encodeURIComponent(uni)}/GEs/ge_categories.json`
};

let currentState = {
    viewBy: "subject",
    selectedUniversity: null,
    selectedCategory: null,
    selectedItem: null
};

const EMPTY_LABELS = {
    subject: { category: "subjects", item: "subjects" },
    major: { category: "majors", item: "majors" },
    ge: { category: "ge", item: "GE requirements" }
};

let REGISTRY = { colleges: {}, courses: {} };
const CACHE = new Map();
const currentItemsMap = new Map();


// ==========================================
// DOM ELEMENTS
// ==========================================
const html = document.documentElement;
const body = document.body;
const themeToggle = document.getElementById("theme-toggle");

// Custom Dropdowns
const uniSearch = document.getElementById("university-search");
const uniDropdown = document.getElementById("university-dropdown");
const viewBySearch = document.getElementById("view-by-search");
const viewByDropdown = document.getElementById("view-by-dropdown");
const catSearch = document.getElementById("category-search");
const catDropdown = document.getElementById("category-dropdown");
const itemSearch = document.getElementById("item-search");
const itemDropdown = document.getElementById("item-dropdown");
const allCustomDropdowns = document.querySelectorAll(".custom-options-list");

uniSearch._lastValidText = "";
catSearch._lastValidText = "";
itemSearch._lastValidText = "";

// Labels & Loaders
const categoryLabel = document.getElementById("category-label");
const itemLabel = document.getElementById("item-label");
const universityLoader = document.getElementById("university-loader");
const categoryLoader = document.getElementById("category-loader");
const itemLoader = document.getElementById("item-loader");

// Results UI
const resultsSection = document.getElementById("articulation-results");
const articulationCards = document.getElementById("articulation-cards");
const noArticulations = document.getElementById("no-articulations");
const selectedCourseDisplay = document.getElementById("selected-course-display");
const loadingDiv = document.getElementById("articulation-loading");


// ==========================================
// UTILITY FUNCTIONS
// ==========================================
function getSafeFileName(name) {
    return name.replace(/\//g, "-").replace(/:/g, "").replace(/\*/g, "=").replace(/>/g, "").trim();
}

async function getJson(url) {
    const res = await fetch(url)
    if (!res.ok) {
        const detail = await res.text().catch(() => "");
        throw new Error(`Fetch failed ${res.status}: ${detail || res.statusText}`)
    }
    return res.json()
}

async function fetchWithCache(key, fetcher) {
    if (!CACHE.has(key)) {
        CACHE.set(key, fetcher());
    }
    return CACHE.get(key);
}

function generateAliases(uni) {
    const aliases = new Set();
    const addAlias = (...items) => items.forEach(item => aliases.add(item.toLowerCase()));

    if (uni.category === "UC") {
        const campus = uni.name.split(",")[1]?.trim();
        const initials = campus.split(" ").map(w => w[0]).join("").toUpperCase();
        addAlias(`UC${initials}`, `UC ${campus}`);
    }

    if (uni.category === "CSU") {
        const campus = uni.name.split(",")[1]?.trim();

        if (campus) {  // Avoids undefined from CSUs without comma (SJSU, SDSU, etc.)
            if (uni.name.includes("Polytechnic")) {
                if (uni.name.includes("San Luis Obispo")) {
                    addAlias("CPSLO", "Cal Poly SLO");
                } else if (uni.name.includes("Pomona")) {
                    addAlias("CPP", "Cal Poly Pomona");
                } else if (uni.name.includes("Humboldt")) {
                    addAlias("CPH", "Cal Poly Humboldt");
                }
            } else {
                const initials = campus.split(" ").map(w => w[0]).join("").toUpperCase();
                addAlias(`CSU${initials}`, `CSU ${campus}`)
            }
        }
    }

    // Generic
    const cleanName = uni.name.replace(/[^a-zA-Z\s]/g, "");
    const words = cleanName.split(" ").filter(w => w.length > 0 && w[0] === w[0].toUpperCase() && !["Of", "The", "And"].includes(w));
    if (words.length > 1) {
        addAlias(words.map(w => w[0]).join("").toUpperCase());
    }

    return Array.from(aliases).join(" ");
}


// ==========================================
// CUSTOM DROPDOWNS
// ==========================================
function createCustomOption(title, subtitle, onClickCallback, searchAliases = "") {
    const div = document.createElement("div");
    div.className = "custom-option";
    div.dataset.aliases = searchAliases.toLowerCase();

    const titleSpan = document.createElement("span");
    titleSpan.className = "custom-option-title";
    titleSpan.textContent = title;
    div.appendChild(titleSpan);

    if (subtitle) {
        const subSpan = document.createElement("span");
        subSpan.className = "custom-option-subtitle";
        subSpan.innerHTML = subtitle;
        div.appendChild(subSpan);
    }

    // Cache the strings so we don't have to keep reading from the DOM
    div._searchString = div.textContent.toLowerCase();
    div._searchAliases = searchAliases.toLowerCase();

    div.addEventListener("click", onClickCallback);
    return div;
}

function createCustomGroup(label) {
    const div = document.createElement("div");
    div.className = "custom-optgroup";
    div.textContent = label;
    return div;
}

function setupSearchableDropdown(inputEl, dropdownEl) {
    // Highlight automatically to allow immediate typing
    inputEl.addEventListener("focus", (e) => {
        allCustomDropdowns.forEach(dropdown => {
            if (dropdown !== dropdownEl) {
                dropdown.classList.remove("show");
                const wrapper = dropdown.closest(".custom-select-wrapper");
                if (wrapper) {
                    wrapper.classList.remove("is-open");
                }
            }
        });

        dropdownEl.classList.add("show");
        const thisWrapper = dropdownEl.closest(".custom-select-wrapper");
        if (thisWrapper) {
            thisWrapper.classList.add("is-open");
        }

        if (inputEl.value && !inputEl.readOnly) {
            inputEl.placeholder = inputEl.value;
            inputEl.value = "";
            inputEl.dispatchEvent(new Event("input"));
        }

        setTimeout(() => e.target.select(), 10);
    });

    inputEl.addEventListener("input", (e) => {
        const query = e.target.value.toLowerCase();
        if (document.activeElement === inputEl) {
            dropdownEl.classList.add("show");
        }

        let currentGroup = null;
        let groupHasVisibleChild = false;
        let lastVisibleElement = null;
        let visibleCount = 0;

        const options = dropdownEl._cachedOptions || [];

        for (const el of options) {
            if (el.classList.contains("no-results-message")) {
                continue;
            }

            el.classList.remove("last-visible");

            if (el.classList.contains("custom-optgroup")) {
                if (currentGroup && !groupHasVisibleChild) {
                    currentGroup.style.display = "none";
                }

                currentGroup = el;
                groupHasVisibleChild = false;
                el.style.display = "block";
            } else {
                const text = el._searchString;
                const aliases = el._searchAliases;

                if (text.includes(query) || aliases.includes(query)) {
                    el.style.display = "flex";
                    groupHasVisibleChild = true;
                    lastVisibleElement = el;
                    visibleCount++;
                } else {
                    el.style.display = "none";
                }
            }
        }

        if (currentGroup && !groupHasVisibleChild) {
            currentGroup.style.display = "none";
        }

        if (lastVisibleElement) {
            lastVisibleElement.classList.add("last-visible");
        }

        if (visibleCount === 0) {
            if (!dropdownEl._noResultsEl) {
                dropdownEl._noResultsEl = document.createElement("div");
                dropdownEl._noResultsEl.className = "no-results-message";
                dropdownEl.appendChild(dropdownEl._noResultsEl);
            }

            dropdownEl._noResultsEl.textContent = e.target.value
                ? `No results found for "${e.target.value}"`
                : "No items available.";

            dropdownEl._noResultsEl.style.display = "block";
        } else if (dropdownEl._noResultsEl) {
            dropdownEl._noResultsEl.style.display = "none";
        }
    });
}


// ==========================================
// DOM & UI HELPERS
// ==========================================
function enableDropdown(dropdownElement) {
    dropdownElement.disabled = false;

}
function disableDropdown(dropdownElement) {
    dropdownElement.disabled = true;
}

function showLoader(loaderElement) {
    loaderElement.style.display = "block";
}

function hideLoader(loaderElement) {
    loaderElement.style.display = "none";
}

function clearArticulations() {
    resultsSection.style.display = "none";
    articulationCards.innerHTML = "";
    noArticulations.style.display = "none";
}

function resetDropdowns(level) {
    clearArticulations();
    if (level <= 1) {
        catSearch.value = "";
        catSearch.placeholder = `Select a ${currentState.viewBy === "ge" ? "category" : currentState.viewBy}...`;
        catSearch._lastValidText = "";
        disableDropdown(catSearch);
        currentState.selectedCategory = null;
    }
    if (level <= 2) {
        itemSearch.value = "";
        itemSearch.placeholder = `Select a ${currentState.viewBy === 'subject' ? 'course' : 'requirement'}...`;
        itemSearch._lastValidText = "";
        disableDropdown(itemSearch);
        currentState.selectedItem = null;
    }
}

function handleEmptyData(inputEl, dropdownEl, itemName) {
    dropdownEl.innerHTML = "";
    inputEl.value = "";
    inputEl._lastValidText = "";
    inputEl.placeholder = `No ${itemName} available.`;

    const emptyMsg = document.createElement("div");
    emptyMsg.className = "no-results-message";
    emptyMsg.textContent = `No ${itemName} available.`;
    dropdownEl.appendChild(emptyMsg);

    dropdownEl._cachedOptions = Array.from(dropdownEl.children);
    dropdownEl._noResultsEl = emptyMsg;

    enableDropdown(inputEl);
}


// ==========================================
// DATA FETCHING & POPULATORS
// ==========================================
async function loadRegistry() {
    try {
        REGISTRY = await fetchWithCache("registry", () => getJson(DATA_PATHS.ccRegistry));
        console.log("Loaded CC registry:", Object.keys(REGISTRY.colleges || {}).length, "colleges")
    } catch (e) {
        console.error("Failed to load CC registry:", e);
        throw e;
    }
}

async function populateUniversities() {
    try {
        showLoader(universityLoader);
        disableDropdown(uniSearch);
        uniSearch.value = "";
        uniDropdown.innerHTML = "";

        let universities = await fetchWithCache("institutions", () => getJson(DATA_PATHS.institutions));
        universities = universities.filter(u => u.category !== "CCC");

        const CATEGORY_WEIGHTS = { "UC": 0, "CSU": 1, "AICCU": 2 };
        universities.sort((a, b) => (CATEGORY_WEIGHTS[a.category] ?? 3) - (CATEGORY_WEIGHTS[b.category] ?? 3) || a.name.localeCompare(b.name));

        const fragment = document.createDocumentFragment();
        let currentCategory = null;

        for (const uni of universities) {
            if (uni.category !== currentCategory) {
                currentCategory = uni.category;
                const labels = { "UC": "University of California", "CSU": "California State University", "AICCU": "Independent (AICCU)" };
                fragment.appendChild(createCustomGroup(labels[currentCategory]));
            }

            const aliases = generateAliases(uni);
            const option = createCustomOption(uni.name, null, async () => {
                uniSearch.value = uni.name;
                uniSearch._lastValidText = uni.name;
                uniDropdown.classList.remove("show");
                uniSearch.closest(".custom-select-wrapper").classList.remove("is-open");
                currentState.selectedUniversity = uni.name;
                resetDropdowns(1);
                await populateCategories(uni.name);
            }, aliases);

            fragment.appendChild(option);
        }

        uniDropdown.appendChild(fragment);
        uniDropdown._cachedOptions = Array.from(uniDropdown.children);
        uniDropdown._noResultsEl = null;

        enableDropdown(uniSearch);
    } catch (error) {
        console.error("Error:", error);
    } finally {
        hideLoader(universityLoader);
    }
}

function initializeViewBy() {
    viewByDropdown.innerHTML = "";
    const options = [
        { value: "subject", title: "Subject", sub: "Search by academic department" },
        { value: "major", title: "Major", sub: "Search by degree program" },
        { value: "ge", title: "General Education", sub: "Search by GE pattern" }
    ];

    options.forEach(opt => {
        const el = createCustomOption(opt.title, opt.sub, async () => {
            viewBySearch.value = opt.title;
            viewByDropdown.classList.remove("show");
            viewBySearch.closest(".custom-select-wrapper").classList.remove("is-open");

            currentState.viewBy = opt.value;
            currentState.selectedCategory = null;
            currentState.selectedItem = null;

            categoryLabel.textContent = opt.value === "subject" ? "Subject" : opt.value === "major" ? "Major" : "GE Category";
            itemLabel.textContent = opt.value === "subject" ? "Course" : opt.value === "major" ? "Requirement" : "Area";

            resetDropdowns(1);
            if (currentState.selectedUniversity) {
                await populateCategories(currentState.selectedUniversity);
            }
        });
        viewByDropdown.appendChild(el);
    });
}

async function populateCategories(universityName) {
    try {
        showLoader(categoryLoader);
        disableDropdown(catSearch);
        catSearch.value = "";
        catSearch.placeholder = `Select a ${currentState.viewBy === "ge" ? "category" : currentState.viewBy}...`;
        catDropdown.innerHTML = "";

        let cacheKey, dataPath, getValue, getTitle, getSubtitle;

        if (currentState.viewBy === "subject") {
            cacheKey = `subjectCategories:${universityName}`;
            dataPath = DATA_PATHS.subjectCategories(universityName);
            getValue = (item) => item.prefix;
            getTitle = (item) => item.prefix;
            getSubtitle = (item) => item.name;
        } else if (currentState.viewBy === "major") {
            cacheKey = `majorCategories:${universityName}`;
            dataPath = DATA_PATHS.majorCategories(universityName);
            getValue = (item) => item;
            getTitle = (item) => item;
            getSubtitle = () => null;
        } else if (currentState.viewBy === "ge") {
            cacheKey = `geCategories:${universityName}`;
            dataPath = DATA_PATHS.geCategories(universityName);
            getValue = (item) => item.name;
            getTitle = (item) => item.name;
            getSubtitle = () => null;
        }

        const items = await fetchWithCache(cacheKey, () => getJson(dataPath));

        if (items.length === 0) {
            const typeName = EMPTY_LABELS[currentState.viewBy].item;
            handleEmptyData(catSearch, catDropdown, typeName);
            hideLoader(categoryLoader);
            return;
        }

        const fragment = document.createDocumentFragment();

        for (const item of items) {
            const val = getValue(item);
            const option = createCustomOption(getTitle(item), getSubtitle(item), async () => {
                catSearch.value = getTitle(item);
                catSearch._lastValidText = getTitle(item);
                catDropdown.classList.remove("show");
                catSearch.closest(".custom-select-wrapper").classList.remove("is-open");

                currentState.selectedCategory = val;
                resetDropdowns(2);
                await populateItems(universityName, val);
                loadRegistry().catch(console.error);
            });
            fragment.appendChild(option);
        }

        catDropdown.appendChild(fragment);
        catDropdown._cachedOptions = Array.from(catDropdown.children);
        catDropdown._noResultsEl = null;

        enableDropdown(catSearch);
    } catch (error) {
        console.error("Error:", error);
    } finally {
        hideLoader(categoryLoader);
    }
}

async function getItemsData(universityName, categoryVal) {
    const view = currentState.viewBy;
    if (view === "subject") {
        return await fetchWithCache(`subItems:${universityName}|${categoryVal}`, () => getJson(DATA_PATHS.subjectItems(universityName, categoryVal)));
    } else if (view === "major") {
        const majorObj = await fetchWithCache(`majItems:${universityName}|${categoryVal}`, () => getJson(DATA_PATHS.majorItems(universityName, categoryVal)));
        return majorObj.courses || [];
    } else if (view === "ge") {
        const ges = await fetchWithCache(`geCats:${universityName}`, () => getJson(DATA_PATHS.geCategories(universityName)));
        const targetGe = ges.find(g => g.name === categoryVal);
        return targetGe ? targetGe.courses : [];
    }
    return [];
}

async function populateItems(universityName, categoryVal) {
    try {
        showLoader(itemLoader);
        disableDropdown(itemSearch);
        itemSearch.value = "";
        itemSearch.placeholder = `Select a ${currentState.viewBy === "subject" ? "course" : "requirement"}...`;
        itemDropdown.innerHTML = "";

        const items = await getItemsData(universityName, categoryVal);

        if (items.length === 0) {
            const typeName = currentState.viewBy === "subject" ? "courses" : "requirements";
            handleEmptyData(itemSearch, itemDropdown, typeName);
            hideLoader(itemLoader);
            return;
        }

        const fragment = document.createDocumentFragment();
        currentItemsMap.clear();

        items.forEach(course => {
            const key = getItemKey(course);
            course._key = key;
            currentItemsMap.set(key, course);

            const labels = buildCourseFullLabel(course);

            const option = createCustomOption(labels.title, labels.subtitle, async () => {
                itemSearch.value = labels.title;
                itemSearch._lastValidText = labels.title;
                itemDropdown.classList.remove("show");
                itemSearch.closest(".custom-select-wrapper").classList.remove("is-open");

                currentState.selectedItem = key;
                clearArticulations();

                resultsSection.style.display = "block";
                loadingDiv.style.display = "flex";

                try {
                    await loadRegistry();
                    const targetItem = currentItemsMap.get(key);
                    const articulationData = {
                        courseFull: buildCourseFullLabel(targetItem, true),
                        articulations: targetItem ? normalizeArticulations(targetItem) : []
                    };
                    displayArticulations(articulationData, articulationData.courseFull);
                } catch (error) {
                    console.error("Error fetching articulations:", error);
                    loadingDiv.style.display = "none";
                }
            });

            fragment.appendChild(option);
        });

        itemDropdown.appendChild(fragment);
        itemDropdown._cachedOptions = Array.from(itemDropdown.children);
        itemDropdown._noResultsEl = null;

        enableDropdown(itemSearch);
    } catch (error) {
        console.error("Error:", error);
    } finally {
        hideLoader(itemLoader);
    }
}


// ==========================================
// DATA PARSING & RENDERING
// ==========================================
function getItemKey(item) {
    if (item.course_id !== undefined) {
        return `COURSE:${item.course_id}`;
    }

    if (item.courses) {
        return `SERIES:${item.conjunction}:${item.courses.map(c => c.course_id).join("|")}`;
    }

    if (item.area_type) {
        return `GE:${item.code}`;
    }

    if (item.name) {
        return `REQ:${item.name}`;
    }

    return JSON.stringify(item);
}

function buildCourseFullLabel(item, multiline = false) {
    let title, subtitle, html;

    if (item.course_id !== undefined) {
        title = `${item.prefix} ${item.number}`;
        subtitle = item.title || "";
        html = subtitle ? `<strong>${title}</strong> - ${subtitle}` : `<strong>${title}</strong>`;
    } else if (item.courses) {
        const conj = (item.conjunction || "AND").toUpperCase();
        const codes = [], names = [], htmlParts = [];

        for (const c of item.courses) {
            const codeString = `${c.prefix} ${c.number}`;
            codes.push(codeString);
            names.push(c.title || codeString);
            htmlParts.push(`<strong>${codeString}</strong>${c.title ? ` - ${c.title}` : ""}`);
        }

        title = codes.join(` ${conj.toLowerCase()} `);
        subtitle = names.join(`,<br>`);
        html = htmlParts.join(`<br><i><strong>${conj}</strong></i><br>`);
    } else if (item.area_type) {
        title = item.code;
        subtitle = item.name || "";
        html = `<strong>${title}</strong> - ${subtitle}`;
    } else if (item.name) {
        title = item.name;
        subtitle = "";
        html = `<strong>${title}</strong>`;
    } else {
        title = "Unknown Item";
        subtitle = "";
        html = "<strong>Unknown Item</strong>";
    }

    return multiline ? html : { title, subtitle };
}

function processSeriesCourses(rawCourses) {
    const courses = [];

    for (const seriesCourse of rawCourses) {
        const ccCourse = REGISTRY.courses[seriesCourse.course_id];
        let title = `${ccCourse.prefix} ${ccCourse.number}`;
        let subtitle = ccCourse.title;
        courses.push({ title, subtitle, notes: seriesCourse.notes || [] });
    }

    return courses;
}

function normalizeArticulations(course) {
    const raw = course?.articulations;
    if (!Array.isArray(raw)) {
        return [];
    }

    const byCollege = new Map();

    for (const artItem of raw) {
        const items = Array.isArray(artItem) ? artItem : [artItem];

        for (const item of items) {
            const articulation = item.articulation;

            if (!articulation) {
                continue;
            }

            const globalNotes = articulation.notes || [];
            const conjunctions = articulation.conjunctions || [];
            const artItems = articulation.items || [];
            const groups = [];

            for (const series of artItems) {
                const courses = processSeriesCourses(series.courses || []);
                groups.push({
                    type: courses.length <= 1 ? "single" : (series.conjunction || "OR").toLowerCase(),
                    courses: courses,
                    notes: series.notes || []
                });
            }

            if (groups.length === 0) {
                continue;
            }

            let topLevelNode;
            if (groups.length === 1) {
                topLevelNode = groups[0];
                if (globalNotes.length > 0) topLevelNode.notes.push(...globalNotes);
            } else {
                topLevelNode = {
                    type: "nested",
                    joins: conjunctions.map(c => (c || "or").toLowerCase()),
                    groups: groups,
                    notes: globalNotes
                };
            }

            topLevelNode.contexts = item.contexts || [];
            const collegeName = REGISTRY.colleges[item.sending_id];

            if (!byCollege.has(collegeName)) {
                byCollege.set(collegeName, []);
            }
            byCollege.get(collegeName).push(topLevelNode);
        }
    }

    return Array.from(byCollege, ([college, paths]) => ({ college, paths }));
}

function renderNotes(notes, position = "below") {
    if (!notes || notes.length === 0) {
        return "";
    }

    const className = position === "above" ? "course-notes-above" : "course-notes";
    let notesHtml = "";
    for (const note of notes) {
        notesHtml += `<div class="note-item"><span class="note-text">${note}</span></div>`;
    }

    return `<div class="${className}">${notesHtml}</div>`;
}

function groupSepMeta(join) {
    const t = String(join || "or").trim().toLowerCase() === "and" ? "and" : "or";
    return {
        className: t === "and" ? "group-separator group-separator-and" : "group-separator group-separator-or",
        text: t.toUpperCase(),
    };
}

function renderCourseItem(course) {
    if (typeof course === "string") {
        return `<div class="course-chip">${course}</div>`;
    }

    let innerHtml = `<span class="chip-title">${course.title}</span><span class="chip-subtitle">${course.subtitle}</span>`;
    let html = `<span class="course-chip">${innerHtml}</span>`;

    if (Array.isArray(course.notes) && course.notes.length) {
        html += renderNotes(course.notes, "below");
    }

    return html;
}

function renderCourseGroup(group) {
    const { type, courses, notes = [] } = group;

    if (type === "single") {
        const chipHtml = renderCourseItem(courses[0]);
        const notesHtml = renderNotes(notes, "below");
        return `<li class="course-item"><div class="group-box group-box-single">${chipHtml}</div>${notesHtml}</li>`;
    }

    if (type === "and" || type === "or") {
        const sepText = type.toUpperCase();
        const sepClass = type === "and" ? "separator-and" : "separator-or";
        const boxClass = type === "and" ? "group-box group-box-and" : "group-box group-box-or";
        const notesHtml = renderNotes(notes, "below");

        let inner = "";
        for (let i = 0; i < courses.length; i++) {
            inner += renderCourseItem(courses[i]);
            if (i < courses.length - 1) inner += `<div class="course-separator ${sepClass}">${sepText}</div>`;
        }
        return `<li class="course-item"><div class="${boxClass}">${inner}</div>${notesHtml}</li>`;
    }

    if (type === "nested") {
        const joins = Array.isArray(group.joins) ? group.joins : null;
        let nestedHtml = "";
        for (let i = 0; i < group.groups.length; i++) {
            nestedHtml += renderCourseGroup(group.groups[i]);
            if (i < group.groups.length - 1) {
                const join = (joins && (joins[i] === "and" || joins[i] === "or")) ? joins[i] : (String(group.join || "or").toLowerCase());
                if (join === "and" || join === "or") {
                    const { className, text } = groupSepMeta(join);
                    nestedHtml += `<li class="${className}">${text}</li>`;
                }
            }
        }
        return nestedHtml;
    }
    return "";
}

function createArticulationCard(collegeData) {
    const { college, paths } = collegeData;
    let pathsHtml = "";

    for (let i = 0; i < paths.length; i++) {
        const path = paths[i];
        let contextHtml = "";

        if (path.contexts && path.contexts.length > 0) {
            const uniqueContexts = [...new Set(path.contexts)];
            const tags = uniqueContexts.map(c => `<div class="context-tag">${c}</div>`).join("");
            contextHtml = `<div class="context-tooltip"><div class="context-tooltip-content"><span class="context-tooltip-header">Articulated In</span>${tags}</div></div>`;
        }

        let groupItemsHtml = "";
        if (path.type === "nested") {
            for (let j = 0; j < path.groups.length; j++) {
                groupItemsHtml += renderCourseGroup(path.groups[j]);
                if (j < path.groups.length - 1) {
                    const join = path.joins[j] || "or";
                    const { className, text } = groupSepMeta(join);
                    groupItemsHtml += `<li class="${className}">${text}</li>`;
                }
            }
        } else {
            groupItemsHtml += renderCourseGroup(path);
        }

        pathsHtml += `<div class="articulation-path has-tooltip">${contextHtml}<ul class="course-list">${groupItemsHtml}</ul></div>`;

        if (i < paths.length - 1) {
            pathsHtml += `<div class="path-separator"><span class="path-or-badge">OR<div class="or-tooltip">These alternatives come from major-specific articulations or conflicting major and departmental agreements.</div></span></div>`;
        }
    }

    return `<div class="articulation-card"><div class="card-header"><h3 class="college-name">${college}</h3></div><div class="card-body">${pathsHtml}</div></div>`;
}

function displayArticulations(articulationData, selectedCourse) {
    const {articulations} = articulationData;

    loadingDiv.style.display = "none";
    resultsSection.style.display = "block";
    selectedCourseDisplay.innerHTML = `Showing <strong>${articulations.length}</strong> articulation${articulations.length === 1 ? '' : 's'} for:<br>${selectedCourse}`;

    if (articulations.length === 0) {
        articulationCards.innerHTML = "";
        noArticulations.style.display = "block";
    } else {
        noArticulations.style.display = "none";
        let cardsHtml = "";
        for (const articulation of articulations) {
            cardsHtml += createArticulationCard(articulation);
        }
        articulationCards.innerHTML = cardsHtml;
    }
}


// ==========================================
// INITIALIZATION & EVENT LISTENERS
// ==========================================
const savedTheme = localStorage.getItem("theme");
if (savedTheme === "dark" || (!savedTheme && window.matchMedia("(prefers-color-scheme: dark)").matches)) {
    html.classList.add("dark-mode");
}

themeToggle.addEventListener("click", () => {
    html.classList.toggle("dark-mode");
    localStorage.setItem("theme", html.classList.contains("dark-mode") ? "dark" : "light");
});

setupSearchableDropdown(uniSearch, uniDropdown);
setupSearchableDropdown(catSearch, catDropdown);
setupSearchableDropdown(itemSearch, itemDropdown);

document.addEventListener("mousedown", (e) => {
    const clickedWrapper = e.target.closest(".custom-select-wrapper");
    const openDropdown = document.querySelector(".custom-options-list.show");

    if (!openDropdown && !clickedWrapper) {
        return;
    }

    allCustomDropdowns.forEach(dropdown => {
        if (!clickedWrapper || !clickedWrapper.contains(dropdown)) {
            const wrapper = dropdown.closest(".custom-select-wrapper");

            if (wrapper) {
                wrapper.classList.remove("is-open");
                const input = wrapper.querySelector("input.form-control");

                if (input && !input.readOnly && input._lastValidText !== undefined) {
                    if (input.value !== input._lastValidText) {
                        input.value = input._lastValidText;

                        if (input.id === "university-search") {
                            input.placeholder = "Select a university...";
                        } else if (input.id === "category-search") {
                            input.placeholder = `Select a ${currentState.viewBy === "ge" ? "category" : currentState.viewBy}...`;
                        } else if (input.id === "item-search") {
                            input.placeholder = `Select a ${currentState.viewBy === 'subject' ? 'course' : 'requirement'}...`;
                        }

                        setTimeout(() => {
                            input.dispatchEvent(new Event("input"));
                        }, 250);
                    }
                }
            }

            dropdown.classList.remove("show");
        }
    });

    if (clickedWrapper) {
        clickedWrapper.classList.add("is-open");
    }
});

viewBySearch.addEventListener("mousedown", (e) => {
    e.stopPropagation();

    allCustomDropdowns.forEach(dropdown => {
        if (dropdown !== viewByDropdown) {
            dropdown.classList.remove("show");
        }
    });

    viewByDropdown.classList.toggle("show");
    const thisWrapper = viewBySearch.closest(".custom-select-wrapper");
    if (thisWrapper) {
        thisWrapper.classList.toggle("is-open");
    }
});

window.addEventListener("DOMContentLoaded", async () => {
    setTimeout(() => body.classList.remove("no-transition"), 100);
    initializeViewBy();
    await populateUniversities();
});

document.getElementById("uni-clear").addEventListener("click", (e) => {
    e.stopPropagation();
    uniSearch.value = "";
    uniSearch._lastValidText = "";
    uniSearch.placeholder = "Select a university...";
    currentState.selectedUniversity = null;
    resetDropdowns(1);
    uniSearch.dispatchEvent(new Event("input"));
    uniSearch.focus();
});

document.getElementById("cat-clear").addEventListener("click", (e) => {
    e.stopPropagation();
    catSearch.value = "";
    catSearch._lastValidText = "";
    catSearch.placeholder = `Select a ${currentState.viewBy === "ge" ? "category" : currentState.viewBy}...`;
    currentState.selectedCategory = null;
    resetDropdowns(2);
    catSearch.dispatchEvent(new Event("input"));
    catSearch.focus();
});

document.getElementById("item-clear").addEventListener("click", (e) => {
    e.stopPropagation();
    itemSearch.value = "";
    itemSearch._lastValidText = "";
    itemSearch.placeholder = `Select a ${currentState.viewBy === 'subject' ? 'course' : 'requirement'}...`;
    currentState.selectedItem = null;
    clearArticulations();
    itemSearch.dispatchEvent(new Event("input"));
    itemSearch.focus();
});