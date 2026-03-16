let currentState = {
    viewBy: "subject",
    selectedUniversity: null,
    selectedCategory: null,
    selectedItem: null
};

let REGISTRY = { colleges: {}, courses: {} }

const universitySelect = document.getElementById("university-select");
const viewBySelect = document.getElementById("view-by-select");
const categorySelect = document.getElementById("category-select");
const itemSelect = document.getElementById("item-select");

const categoryLabel = document.getElementById("category-label");
const itemLabel = document.getElementById("item-label");

const universityLoader = document.getElementById("university-loader");
const categoryLoader = document.getElementById("category-loader");
const itemLoader = document.getElementById("item-loader");

const resultsSection = document.getElementById("articulation-results");
const articulationCards = document.getElementById("articulation-cards");
const noArticulations = document.getElementById("no-articulations");

const selectedCourseDisplay = document.getElementById("selected-course-display");
const loadingDiv = document.getElementById("articulation-loading");

const DATA_PATHS = {
    institutions: "./data/institutions.json",
    ccRegistry: "./data/colleges/cc_registry.json",
    subjectCategories: (uni) => `./data/universities/${encodeURIComponent(uni)}/Subjects/subjects.json`,
    subjectItems: (uni, prefix) => `./data/universities/${encodeURIComponent(uni)}/Subjects/subj_${encodeURIComponent(prefix)}.json`,
    majorCategories: (uni) => `./data/universities/${encodeURIComponent(uni)}/Majors/majors.json`,
    majorItems: (uni, major) => `./data/universities/${encodeURIComponent(uni)}/Majors/${encodeURIComponent(getSafeFileName(major))}.json`,
    geCategories: (uni) => `./data/universities/${encodeURIComponent(uni)}/GEs/ge_categories.json`
};

const CACHE = new Map();
const currentItemsMap = new Map();

const themeToggle = document.getElementById("theme-toggle");
const html = document.documentElement;
const body = document.body;

const savedTheme = localStorage.getItem("theme");
if (savedTheme === "dark") {
    html.classList.add("dark-mode");
} else if (!savedTheme && window.matchMedia("(prefers-color-scheme: dark)").matches) {
    html.classList.add("dark-mode");
}

themeToggle.addEventListener("click", () => {
    html.classList.toggle("dark-mode");

    const isDark = html.classList.contains("dark-mode");
    localStorage.setItem("theme", isDark ? "dark" : "light");
});

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

async function loadRegistry() {
    try {
        REGISTRY = await fetchWithCache("registry", () => getJson(DATA_PATHS.ccRegistry));
        console.log("Loaded CC registry:", Object.keys(REGISTRY.colleges || {}).length, "colleges")
    } catch (e) {
        console.error("Failed to load CC registry:", e);
        throw e;
    }
}

function enableDropdown(dropdownElement) {
    dropdownElement.disabled = false;
}

function disableDropdown(dropdownElement) {
    dropdownElement.disabled = true;
}

function clearDropdown(element, defaultText) {
    element.innerHTML = `<option value="" disabled selected hidden>${defaultText}</option>`;
}

function showLoader(loaderElement) {
    loaderElement.style.display = "block";
}

function hideLoader(loaderElement) {
    loaderElement.style.display = "none";
}

function getItemKey(item) {
    if (item.course_id !== undefined) {
        return `COURSE:${item.course_id}`;
    }

    if (item.courses) {
        const ids = item.courses.map(c => c.course_id).join("|");
        return `SERIES:${item.conjunction}:${ids}`;
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
    if (!item) {
        return "";
    }

    if (item.course_id !== undefined) {
        if (multiline) {
            return `<strong>${item.prefix} ${item.number}</strong> - ${item.title}`;
        }
        return `${item.prefix} ${item.number} - ${item.title}`;
    }

    if (item.courses) {
        const conj = (item.conjunction || "AND").toUpperCase();

        if (multiline) {
            const separatorHtml = `<br><i><strong>${conj}</strong></i><br>`;

            return item.courses.map(c => {
                const title = c.title ? ` - ${c.title}` : "";
                return `<strong>${c.prefix} ${c.number}</strong>${title}`;
            }).join(separatorHtml);
        } else {
            const codes = [];
            const names = [];

            for (const c of item.courses) {
                const codeString = `${c.prefix} ${c.number}`;
                codes.push(codeString);
                names.push(c.title || codeString);
            }

            return `${codes.join(` ${conj} `)} - ${names.join(` ${conj} `)}`;
        }
    }

    if (item.area_type) {
        return `${item.code} - ${item.name}`;
    }

    if (item.name) {
        return `${item.name}`;
    }

    return "Unknown Item";
}

async function populateUniversities() {
    try {
        showLoader(universityLoader);
        disableDropdown(universitySelect);

        let universities = await fetchWithCache("institutions", () => getJson(DATA_PATHS.institutions));
        universities = universities.filter(u => u.category !== "CCC");

        const CATEGORY_WEIGHTS = { "UC": 0, "CSU": 1, "AICCU": 2 };
        const sorted = universities.sort((a, b) => {
            const categoryDiff = (CATEGORY_WEIGHTS[a.category] ?? 3) - (CATEGORY_WEIGHTS[b.category] ?? 3);

            if (categoryDiff !== 0) {
                return categoryDiff;
            }

            return a.name.localeCompare(b.name, undefined, {sensitivity: "base"});
        })

        clearDropdown(universitySelect, "Select a university...");

        const fragment = document.createDocumentFragment();
        let currentCategory = null;
        let currentOptGroup = null;

        for (const university of sorted) {
            if (university.category !== currentCategory) {
                currentCategory = university.category;
                currentOptGroup = document.createElement("optgroup");

                if (currentCategory === "UC") {
                    currentOptGroup.label = "University of California";
                } else if (currentCategory === "CSU") {
                    currentOptGroup.label = "California State University";
                } else if (currentCategory === "AICCU") {
                    currentOptGroup.label = "Independent (AICCU)";
                }

                fragment.appendChild(currentOptGroup);
            }

            const option = document.createElement("option");
            option.value = university.id;
            option.textContent = university.name;
            currentOptGroup.appendChild(option);
        }

        universitySelect.appendChild(fragment);
        enableDropdown(universitySelect);
        console.log("University dropdown populated with", universities.length, "options");
    } catch (error) {
        console.error("Error loading universities:", error);
        alert("Failed to load universities. Please refresh the page.");
    } finally {
        hideLoader(universityLoader);
    }
}

async function populateCategories(universityName) {
    try {
        showLoader(categoryLoader);
        disableDropdown(categorySelect);

        const view = currentState.viewBy;
        const defaultText = `Select a ${view === "ge" ? "category" : view}...`;
        clearDropdown(categorySelect, defaultText);

        let cacheKey, dataPath, getValue, getLabel;

        if (view === "subject") {
            cacheKey = `subjectCategories:${universityName}`;
            dataPath = DATA_PATHS.subjectCategories(universityName);
            getValue = (item) => item.prefix;
            getLabel = (item) => `${item.prefix} - ${item.name}`;
        } else if (view === "major") {
            cacheKey = `majorCategories:${universityName}`;
            dataPath = DATA_PATHS.majorCategories(universityName);
            getValue = (item) => item;
            getLabel = (item) => item;
        } else if (view === "ge") {
            cacheKey = `geCategories:${universityName}`;
            dataPath = DATA_PATHS.geCategories(universityName);
            getValue = (item) => item.name;
            getLabel = (item) => item.name;
        }

        const items = await fetchWithCache(cacheKey, () => getJson(dataPath));
        const fragment = document.createDocumentFragment();

        for (const item of items) {
            const option = document.createElement("option");
            option.value = getValue(item);
            option.textContent = getLabel(item);
            fragment.appendChild(option);
        }

        categorySelect.appendChild(fragment);
        enableDropdown(categorySelect);
    } catch (error) {
        console.error("Error loading subjects:", error);

        if (error.message.includes("404")) {
            alert(`This university does not have ${currentState.viewBy} data available.`)
        } else {
            alert("Failed to load categories. Please try again.");
        }
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
        disableDropdown(itemSelect);

        const defaultText = `Select a ${currentState.viewBy === "subject" ? "course" : "requirement"}...`;
        clearDropdown(itemSelect, defaultText);

        const items = await getItemsData(universityName, categoryVal);
        const fragment = document.createDocumentFragment();

        currentItemsMap.clear();

        items.forEach(course => {
            const key = getItemKey(course);
            course._key = key;

            currentItemsMap.set(key, course);

            const option = document.createElement("option");
            option.value = key;
            option.textContent = buildCourseFullLabel(course);
            fragment.appendChild(option);
        });

        itemSelect.appendChild(fragment);
        enableDropdown(itemSelect);
        console.log("Populated course dropdown with", items.length, "options");
    } catch (error) {
        console.error("Error loading items:", error);
        alert("Failed to load items. Please try again.");
    } finally {
        hideLoader(itemLoader);
    }
}

// Helper for normalizeArticulations
function processSeriesCourses(rawCourses) {
    const courses = [];

    for (const seriesCourse of rawCourses) {
        const ccCourse = REGISTRY.courses[seriesCourse.course_id];

        let label;
        if (ccCourse) {
            if (!ccCourse._cachedLabel) {
                ccCourse._cachedLabel = `${ccCourse.prefix} ${ccCourse.number} - ${ccCourse.title}`;
            }

            label = ccCourse._cachedLabel;
        } else {
            label = `Unknown Course (${seriesCourse.course_id})`;
        }

        courses.push({ label, notes: seriesCourse.notes || [] });
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

                if (globalNotes.length > 0) {
                    topLevelNode.notes.push(...globalNotes);
                }
            } else {
                topLevelNode = {
                    type: "nested",
                    joins: conjunctions.map(conjunction => (conjunction || "or").toLowerCase()),
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

    return Array.from(byCollege, ([college, paths]) => ({
        college,
        paths
    }));
}

function clearArticulations() {
    resultsSection.style.display = "none";
    articulationCards.innerHTML = "";
    noArticulations.style.display = "none";
}

function renderNotes(notes, position = "below") {
    if (!notes || notes.length === 0) {
        return "";
    }

    const className = position === "above" ? "course-notes-above" : "course-notes";

    let notesHtml = "";
    for (const note of notes) {
        notesHtml += `
        <div class="note-item">
            <span class="note-text">${note}</span>
        </div>
        `;
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

function createArticulationCard(collegeData) {
    const { college, paths } = collegeData;
    let pathsHtml = "";

    for (let i = 0; i < paths.length; i++) {
        const path = paths[i];

        let contextHtml = "";
        if (path.contexts && path.contexts.length > 0) {
            const uniqueContexts = [...new Set(path.contexts)];
            const tags = uniqueContexts.map(c => `<div class="context-tag">${c}</div>`).join("");

            contextHtml = `
                <div class="context-tooltip">
                    <div class="context-tooltip-content">
                        <span class="context-tooltip-header">Articulated In</span>
                        ${tags}
                    </div>
                </div>
            `;
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

        pathsHtml += `
            <div class="articulation-path has-tooltip">
                ${contextHtml}
                <ul class="course-list">
                    ${groupItemsHtml}
                </ul>
            </div>
        `;

        if (i < paths.length - 1) {
            pathsHtml += `
                <div class="path-separator">
                    <span class="path-or-badge">
                        OR
                        <div class="or-tooltip">These alternatives come from major-specific articulations or conflicting major and departmental agreements.</div>
                    </span>
                </div>
            `;
        }
    }

    return `
    <div class="articulation-card">
        <div class="card-header">
            <h3 class="college-name">${college}</h3>
        </div>
        <div class="card-body">
            ${pathsHtml}
        </div>
    </div>
  `;
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

function renderCourseItem(course) {
    if (typeof course === "string") {
        return `<div class="course-chip">${course}</div>`;
    }

    const label =
        course.label ??
        [course.prefix, course.number].filter(Boolean).join(" ") +
        (course.title ? ` - ${course.title}` : "");

    let html = `<div class="course-chip">${label}</div>`;

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
            if (i < courses.length - 1) {
                inner += `<div class="course-separator ${sepClass}">${sepText}</div>`;
            }
        }

        return `<li class="course-item"><div class="${boxClass}">${inner}</div>${notesHtml}</li>`;
    }

    if (type === "nested") {
        const joins = Array.isArray(group.joins) ? group.joins : null;
        let nestedHtml = "";
        for (let i = 0; i < group.groups.length; i++) {
            nestedHtml += renderCourseGroup(group.groups[i]);

            if (i < group.groups.length - 1) {
                const join = (joins && (joins[i] === "and" || joins[i] === "or"))
                    ? joins[i]
                    : (String(group.join || "or").toLowerCase());
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

function resetDropdowns(level) {
    clearArticulations();

    if (level <= 1) { // Reset Category
        clearDropdown(categorySelect, `Select a ${currentState.viewBy === "ge" ? "category" : currentState.viewBy}...`);
        disableDropdown(categorySelect);
        currentState.selectedCategory = null;
    }

    if (level <= 2) { // Reset Items
        clearDropdown(itemSelect, `Select a ${currentState.viewBy === 'subject' ? 'course' : 'requirement'}...`);
        disableDropdown(itemSelect);
        currentState.selectedItem = null;
    }
}

universitySelect.addEventListener("change", async (e) => {
    const universityName = e.target.options[e.target.selectedIndex].text

    console.log("University selected:", universityName);
    currentState.selectedUniversity = universityName;
    resetDropdowns(1);

    if (universityName) {
        await populateCategories(universityName);
    }
});

viewBySelect.addEventListener("change", async (e) => {
    currentState.viewBy = e.target.value;
    currentState.selectedCategory = null;
    currentState.selectedItem = null;

    if (currentState.viewBy === "subject") {
        categoryLabel.textContent = "Subject";
        itemLabel.textContent = "Course";
    } else if (currentState.viewBy === "major") {
        categoryLabel.textContent = "Major";
        itemLabel.textContent = "Requirement";
    } else if (currentState.viewBy === "ge") {
        categoryLabel.textContent = "GE Category";
        itemLabel.textContent = "Area";
    }

    resetDropdowns(1);

    if (currentState.selectedUniversity) {
        await populateCategories(currentState.selectedUniversity);
    }
});

categorySelect.addEventListener("change", async (e) => {
    const categoryVal = e.target.value;

    console.log("Subject selected:", categoryVal);
    currentState.selectedCategory = categoryVal;
    resetDropdowns(2);

    if (categoryVal && currentState.selectedUniversity) {
        await populateItems(currentState.selectedUniversity, categoryVal);
        loadRegistry().catch(console.error);
    }
});

itemSelect.addEventListener("change", async (e) => {
    const itemKey = e.target.value;
    currentState.selectedItem = itemKey;
    clearArticulations();

    if (itemKey && currentState.selectedUniversity && currentState.selectedCategory) {
        resultsSection.style.display = "block";
        loadingDiv.style.display = "flex";

        try {
            await loadRegistry();
            const targetItem = currentItemsMap.get(itemKey);

            const articulationData = {
                courseFull: buildCourseFullLabel(targetItem, true),
                articulations: targetItem ? normalizeArticulations(targetItem) : []
            };

            displayArticulations(articulationData, articulationData.courseFull);
        } catch (error) {
            console.error("Error fetching articulations:", error);
            alert("Failed to load articulations. Please try again.");
            loadingDiv.style.display = "none";
        }
    }
});

window.addEventListener("DOMContentLoaded", async () => {
    setTimeout(() => {
        body.classList.remove("no-transition");
    }, 100);

    await populateUniversities();
});