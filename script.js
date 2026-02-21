let currentState = {
    viewBy: "subject",
    selectedUniversity: null,
    selectedCategory: null,
    selectedItem: null
};

let REGISTRY = { colleges: {}, courses: {} }

const universitySelect = document.getElementById("university-select");
const viewBySelect = document.getElementById("view-by-select")
const categorySelect = document.getElementById("category-select")
const itemSelect = document.getElementById("item-select")

const categoryLabel = document.getElementById("category-label")
const itemLabel = document.getElementById("item-label")

const universityLoader = document.getElementById("university-loader");
const categoryLoader = document.getElementById("category-loader");
const itemLoader = document.getElementById("item-loader");

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
        CACHE.set(key, await fetcher());
    }

    return CACHE.get(key);
}

async function loadRegistry() {
    try {
        REGISTRY = await fetchWithCache("registry", () => getJson(DATA_PATHS.ccRegistry));
        console.log("Loaded CC registry:", Object.keys(REGISTRY.colleges || {}).length, "colleges")
    } catch (e) {
        console.error("Failed to load CC registry:", e);
    }
}

function enableDropdown(dropdownElement) {
    dropdownElement.disabled = false;
}

function disableDropdown(dropdownElement) {
    dropdownElement.disabled = true;
}

function clearDropdown(element, defaultText) {
    while (element.options.length > 0) {
        element.remove(0);
    }

    const defaultOption = document.createElement("option");
    defaultOption.value = "";
    defaultOption.textContent = defaultText;
    defaultOption.disabled = true;
    defaultOption.selected = true;
    defaultOption.hidden = true;

    element.appendChild(defaultOption);
}

function showLoader(loaderElement) {
    loaderElement.style.display = "block";
}

function hideLoader(loaderElement) {
    loaderElement.style.display = "none";
}

async function fetchInstitutions() {
    console.log("Fetching universities...");
    return getJson(DATA_PATHS.institutions)
}

async function fetchSubjects(universityName) {
    console.log("Fetching subjects for university:", universityName);

    let list = SUBJECT_CACHE.get(universityName);
    if (!list) {
        list = await getJson(DATA_PATHS.subjects(universityName))
        SUBJECT_CACHE.set(universityName, list);
    }

    return list;
}

function coursesCacheKey(universityName, subjectCode) {
    return `${universityName}|${subjectCode}`;
}

async function fetchCourses(universityName, subjectCode) {
    console.log("Fetching courses for university:", universityName, "subject:", subjectCode);
    const key = coursesCacheKey(universityName, subjectCode);

    let list = COURSE_CACHE.get(key);
    if (!list) {
        list = await getJson(DATA_PATHS.courses(universityName, subjectCode));
        COURSE_CACHE.set(key, list)
    }

    return list
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

function buildCourseFullLabel(item) {
    if (!item) {
        return "";
    }

    if (item.course_id !== undefined) {
        return `${item.prefix} ${item.number} - ${item.title}`;
    }

    if (item.courses) {
        const names = item.courses.map(c => c.title || `${c.prefix} ${c.number}`).join(", ");
        return `${item.name || "Series"} - ${names}`;
    }

    if (item.area_type) {
        return `GE: ${item.code} - ${item.name}`;
    }

    if (item.name) {
        return `Requirement: ${item.name}`;
    }

    return "Unknown Item";
}

async function fetchArticulations(universityName, subjectCode, courseKey) {
    const list = await fetchCourses(universityName, subjectCode);
    const course = (list || []).find(c => c.key === courseKey || getItemKey(c) === courseKey);
    const courseFull = buildCourseFullLabel(course);
    const articulations = course ? normalizeArticulations(course) : [];
    return {courseFull, articulations};
}

async function populateUniversities() {
    try {
        showLoader(universityLoader);
        disableDropdown(universitySelect);

        let universities = await fetchWithCache("institutions", () => getJson(DATA_PATHS.institutions));
        universities = universities.filter(u => u.category !== "CCC");

        const CATEGORY_ORDER = ["UC", "CSU", "AICCU"];
        const orderIndex = (category) => {
            const i = CATEGORY_ORDER.indexOf(category);
            return i === -1 ? CATEGORY_ORDER.length : i;
        }

        const sorted = universities.sort((a, b) => {
            const categoryDiff = orderIndex(a.category) - orderIndex(b.category);

            if (categoryDiff !== 0) {
                return categoryDiff;
            }

            return a.name.localeCompare(b.name, undefined, {sensitivity: "base"});
        })

        clearDropdown(universitySelect, "Select a university...");
        const categories = [
            { key: "UC", label: "University of California" },
            { key: "CSU", label: "California State University" },
            { key: "AICCU", label: "Independent (AICCU)" }
        ]

        for (const category of categories) {
            const groupItems = sorted.filter(u => u.category === category.key);

            if (!groupItems.length) {
                continue;
            }

            const optgroup = document.createElement("optgroup");
            optgroup.label = category.label;

            for (const university of groupItems) {
                const option = document.createElement("option");
                option.value = university.id;
                option.textContent = university.name;
                optgroup.appendChild(option);
            }

            universitySelect.appendChild(optgroup);
        }

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

        let optionsData = [];

        if (view === "subject") {
            const subjects = await fetchWithCache(`subjectCategories:${universityName}`, () => getJson(DATA_PATHS.subjectCategories(universityName)));
            optionsData = subjects.map(s => ({ value: s.prefix, label: `${s.prefix} - ${s.name}` }));
        } else if (view === "major") {
            const majors = await fetchWithCache(`majorCategories:${universityName}`, () => getJson(DATA_PATHS.majorCategories(universityName)));
            optionsData = majors.map(m => ({ value: m, label: m }));
        } else if (view === "ge") {
            const ges = await fetchWithCache(`geCategories:${universityName}`, () => getJson(DATA_PATHS.geCategories(universityName)));
            optionsData = ges.map(g => ({ value: g.name, label: g.name }));
        }

        optionsData.forEach(opt => {
            const option = document.createElement("option");
            option.value = opt.value;
            option.textContent = opt.label;
            categorySelect.appendChild(option);
        });

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

        items.forEach(course => {
            const key = getItemKey(course);
            course._key = key;

            const option = document.createElement("option");
            option.value = key;
            option.textContent = buildCourseFullLabel(course);
            itemSelect.appendChild(option);
        });

        enableDropdown(itemSelect);
        console.log("Populated course dropdown with", items.length, "options");
    } catch (error) {
        console.error("Error loading items:", error);
        alert("Failed to load items. Please try again.");
    } finally {
        hideLoader(itemLoader);
    }
}

function toCourseChip(item) {
    const label = `${item.prefix} ${item.number} - ${item.title}`.replace(/\s+/g, " ").trim();
    const notes = Array.isArray(item.notes) ? item.notes : [];
    return {label, notes};
}

const conjToType = (c) => (String(c || "").toUpperCase() === "AND" ? "and" : (c ? "or" : null));

function normalizeSendingNode(node) {
    const type = String(node?.type || "").toUpperCase();
    const items = Array.isArray(node?.items) ? node.items : [];
    const notes = Array.isArray(node?.notes) ? node.notes : [];
    const joinType = conjToType(node?.conjunction);
    const joinsArr = Array.isArray(node?.conjunctions)
        ? node.conjunctions.map(conjToType) // normalized to "and"/"or"
        : null;

    if (type === "SET") {
        const chips = items.map(toCourseChip);
        if (chips.length <= 1) {
            return { type: "single", courses: chips.length ? [chips[0]] : [], notes };
        }
        if (joinType) {
            return { type: joinType, courses: chips, notes };
        }
        return { type: "single", courses: chips, notes }; // default to single when unspecified
    }

    if (type === "GROUP") {
        const childGroups = items.map(normalizeSendingNode);

        // If a per-edge joins array exists, prefer it and avoid collapsing
        if (joinsArr && childGroups.length > 0) {
            // joinsArr should have length childGroups.length - 1; tolerate mismatch gracefully
            return {
                type: "nested",
                join: null,            // no uniform join
                joins: joinsArr,       // per-edge joins: ["and" | "or", ...]
                groups: childGroups,
                notes
            };
        }

        // Legacy uniform behavior: collapse GROUP of singles with a uniform join
        const allSingles = childGroups.length > 0 && childGroups.every(g => g.type === "single");
        if (allSingles && joinType) {
            const flat = childGroups.flatMap(g => g.courses || []);
            return { type: joinType, courses: flat, notes };
        }

        return {
            type: "nested",
            join: joinType || "or",   // default to "or" if unspecified
            groups: childGroups,
            notes
        };
    }

    return { type: "single", courses: [], notes: [] };
}


function normalizeArticulations(course) {
    const raw = Array.isArray(course?.articulations) ? course.articulations : [];
    const byCollege = new Map();

    raw.flat().forEach(artItem => {
        const collegeId = artItem.sending_id;
        const collegeName = REGISTRY.colleges[collegeId] || `Unknown College (${collegeId})`;
        const articulation = artItem.articulation;

        if (!articulation) {
            return;
        }

        const globalNotes = articulation.notes || [];
        const conjunctions = articulation.conjunctions || [];
        const items = articulation.items || [];

        const groups = items.map(series => {
            const seriesNotes = series.notes || [];
            const joinType = (series.conjunction || "OR").toLowerCase();

            const courses = (series.courses || []).map(sc => {
                const ccCourse = REGISTRY.courses[sc.course_id];
                let label = `Unknown Course (${sc.course_id})`;
                if (ccCourse) {
                    label = `${ccCourse.prefix} ${ccCourse.number} - ${ccCourse.title}`;
                }
                return { label, notes: sc.notes || [] };
            });

            if (courses.length <= 1) {
                return { type: "single", courses: courses, notes: seriesNotes };
            }
            return { type: joinType, courses: courses, notes: seriesNotes };
        });

        let topLevelNode = null;

        if (groups.length === 0) {
            return;
        } else if (groups.length === 1) {
            topLevelNode = groups[0];
            if (globalNotes.length) {
                topLevelNode.notes = [...globalNotes, ...(topLevelNode.notes || [])];
            }
        } else {
            const mappedJoins = conjunctions.map(c => (c || "OR").toLowerCase());
            topLevelNode = {
                type: "nested",
                joins: mappedJoins,
                groups: groups,
                notes: globalNotes
            };
        }

        if (!byCollege.has(collegeName)) {
            byCollege.set(collegeName, []);
        }
        byCollege.get(collegeName).push(topLevelNode);
    });

    return Array.from(byCollege.entries()).map(([college, groups]) => ({
        college,
        groupJoin: "or",
        groups
    }));
}

function clearArticulations() {
    const resultsSection = document.getElementById("articulation-results");
    const articulationCards = document.getElementById("articulation-cards");
    const noArticulations = document.getElementById("no-articulations");

    resultsSection.style.display = "none";
    articulationCards.innerHTML = "";
    noArticulations.style.display = "none";
}

function renderNotes(notes, position = "below") {
    if (!notes || notes.length === 0) {
        return "";
    }

    const className = position === "above" ? "course-notes-above" : "course-notes";
    const notesHtml = notes.map(note =>
        `
        <div class="note-item">
            <span class="note-text">${note}</span>
        </div>
        `
    ).join("");

    return `<div class="${className}">${notesHtml}</div>`;
}

function groupSepMeta(join) {
    const t = String(join || "or").trim().toLowerCase() === "and" ? "and" : "or";
    return {
        className: t === "and" ? "group-separator-and" : "group-separator-or",
        text: t.toUpperCase(),
    };
}

function createArticulationCard(collegeData) {
    const { college, groups, groupJoin } = collegeData;

    const groupItems = groups.map((group, index) => {
        let html = renderCourseGroup(group);

        if (index < groups.length - 1) {
            const { className, text } = groupSepMeta(groupJoin);
            html += `<li class="${className}">${text}</li>`;
        }

        return html;
    }).join("");

    return `
    <div class="articulation-card">
        <div class="card-header">
            <h3 class="college-name">${college}</h3>
        </div>
        <div class="card-body">
            <ul class="course-list">
                ${groupItems}
            </ul>
        </div>
    </div>
  `;
}


function displayArticulations(articulationData, selectedCourse) {
    const resultsSection = document.getElementById("articulation-results");
    const selectedCourseDisplay = document.getElementById("selected-course-display");
    const articulationCards = document.getElementById("articulation-cards");
    const noArticulations = document.getElementById("no-articulations");
    const loadingDiv = document.getElementById("articulation-loading");

    loadingDiv.style.display = "none";
    resultsSection.style.display = "block";
    selectedCourseDisplay.textContent = `Showing articulations for: ${selectedCourse}`;

    const {articulations} = articulationData;

    if (articulations.length === 0) {
        articulationCards.innerHTML = "";
        noArticulations.style.display = "block";
    } else {
        noArticulations.style.display = "none";
        articulationCards.innerHTML = articulations.map(collegeData => createArticulationCard(collegeData)).join("");
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
        return `<li class="course-item"><div class="group-box-single">${chipHtml}${notesHtml}</div></li>`;
    }

    if (type === "and" || type === "or") {
        const sepText = type.toUpperCase();
        const sepClass = type === "and" ? "separator-and" : "separator-or";
        const boxClass = type === "and" ? "group-box-and" : "group-box-or";
        const notesHtml = renderNotes(notes, "below");

        const inner = courses.map((c, i) => {
            let html = renderCourseItem(c);
            if (i < courses.length - 1) {
                html += `<div class="course-separator ${sepClass}">${sepText}</div>`;
            }
            return html;
        }).join("");

        return `<li class="course-item"><div class="${boxClass}">${inner}</div>${notesHtml}</li>`;
    }

    if (type === "nested") {
        const joins = Array.isArray(group.joins) ? group.joins : null;
        return group.groups.map((g, i) => {
            let html = renderCourseGroup(g);
            if (i < group.groups.length - 1) {
                const join = (joins && (joins[i] === "and" || joins[i] === "or"))
                    ? joins[i]
                    : (String(group.join || "or").toLowerCase());
                if (join === "and" || join === "or") {
                    const { className, text } = groupSepMeta(join);
                    html += `<li class="${className}">${text}</li>`;
                }
            }
            return html;
        }).join("");
    }

    return "";
}

viewBySelect.addEventListener("change", async (e) => {
    currentState.viewBy = e.target.value;
    currentState.selectedCategory = null;
    currentState.selectedItem = null;

    // Update Labels
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

    clearArticulations();
    clearDropdown(categorySelect, `Select a ${currentState.viewBy === 'ge' ? 'category' : currentState.viewBy}...`);
    disableDropdown(categorySelect);
    clearDropdown(itemSelect, `Select a ${currentState.viewBy === 'subject' ? 'course' : 'requirement'}...`);
    disableDropdown(itemSelect);

    if (currentState.selectedUniversity) {
        await populateCategories(currentState.selectedUniversity);
    }
});

universitySelect.addEventListener("change", async (e) => {
    const universityName = e.target.options[e.target.selectedIndex].text

    console.log("University selected:", universityName);
    currentState.selectedUniversity = universityName;
    currentState.selectedCategory = null;
    currentState.selectedItem = null;

    clearArticulations();

    clearDropdown(categorySelect, `Select a ${currentState.viewBy === "ge" ? "category" : currentState.viewBy}...`);
    disableDropdown(categorySelect);
    clearDropdown(itemSelect, `Select a ${currentState.viewBy === 'subject' ? 'course' : 'requirement'}...`);
    disableDropdown(itemSelect);

    if (universityName) {
        await populateCategories(universityName);
    }
});

categorySelect.addEventListener("change", async (e) => {
    const categoryVal = e.target.value;

    console.log("Subject selected:", categoryVal);
    currentState.selectedCategory = categoryVal;
    currentState.selectedItem = null;

    clearArticulations();
    clearDropdown(itemSelect, `Select a ${currentState.viewBy === 'subject' ? 'course' : 'requirement'}...`);
    disableDropdown(itemSelect);

    if (categoryVal && currentState.selectedUniversity) {
        await populateItems(currentState.selectedUniversity, categoryVal);
    }
});

itemSelect.addEventListener("change", async (e) => {
    const itemKey = e.target.value;
    currentState.selectedItem = itemKey;
    clearArticulations();

    if (itemKey && currentState.selectedUniversity && currentState.selectedCategory) {
        const resultsSection = document.getElementById("articulation-results");
        const loadingDiv = document.getElementById("articulation-loading");
        resultsSection.style.display = "block";
        loadingDiv.style.display = "flex";

        try {
            const itemsList = await getItemsData(currentState.selectedUniversity, currentState.selectedCategory);
            const targetItem = itemsList.find(c => c._key === itemKey || getItemKey(c) === itemKey);

            const articulationData = {
                courseFull: buildCourseFullLabel(targetItem),
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
    await loadRegistry();
    populateUniversities();
});