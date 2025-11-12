let currentState = {
    selectedUniversity: null,
    selectedSubject: null,
    selectedCourse: null
};

const universitySelect = document.getElementById("university-select");
const subjectSelect = document.getElementById("subject-select");
const courseSelect = document.getElementById("course-select");
const universityLoader = document.getElementById("university-loader");
const subjectLoader = document.getElementById("subject-loader");
const courseLoader = document.getElementById("course-loader");

const DATA_PATHS = {
    institutions: "./data/institutions.json",
    subjects: (universityName) => `./data/${encodeURIComponent(universityName)}/subjects.json`,
    courses: (universityName, subjectCode) => `./data/${encodeURIComponent(universityName)}/${encodeURIComponent(subjectCode)}/courses.json`
}

const SUBJECT_CACHE = new Map();
const COURSE_CACHE = new Map();

async function getJson(url) {
    const res = await fetch(url)

    if (!res.ok) {
        const detail = await res.text().catch(() => "");
        throw new Error(`Fetch failed ${res.status}: ${detail || res.statusText}`)
    }

    return res.json()
}

function enableDropdown(dropdownElement) {
    dropdownElement.disabled = false;
}

function disableDropdown(dropdownElement) {
    dropdownElement.disabled = true;
}

function clearDropdown(dropdownElement) {
    while (dropdownElement.options.length > 1) {
        dropdownElement.remove(1);
    }

    dropdownElement.selectedIndex = 0;
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

async function fetchArticulations(universityName, subjectCode, courseKey) {
    const list = await fetchCourses(universityName, subjectCode);
    const course = (list || []).find(c => c.key === courseKey);
    const courseFull = buildCourseFullLabel(course);
    const articulations = course ? normalizeArticulations(course) : [];
    return {courseFull, articulations};
}

async function populateUniversities() {
    try {
        showLoader(universityLoader);
        disableDropdown(universitySelect);

        let universities = await fetchInstitutions();
        const sorted = universities
            .filter(u => u.category !== "CCC")
            .sort((a, b) => a.name.localeCompare(b.name, undefined, {sensitivity: "base"}));

        for (const university of sorted) {
            const option = document.createElement("option");
            option.value = university.id;
            option.textContent = university.name;
            universitySelect.appendChild(option);
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

async function populateSubjects(universityName) {
    try {
        showLoader(subjectLoader);
        disableDropdown(subjectSelect);
        clearDropdown(subjectSelect);

        const subjects = await fetchSubjects(universityName);

        subjects.forEach(subject => {
            const option = document.createElement("option");
            option.value = subject.prefix;
            option.textContent = `${subject.prefix} - ${subject.name}`;
            subjectSelect.appendChild(option);
        });

        enableDropdown(subjectSelect);
        console.log("Subject dropdown populated with", subjects.length, "options");
    } catch (error) {
        console.error("Error loading subjects:", error);

        if (error.message.includes("404")) {
            alert("This university has no articulation information. Please choose a different one.")
        } else {
            alert("Failed to load subjects. Please try again.");
        }
    } finally {
        hideLoader(subjectLoader);
    }
}

async function populateCourses(universityId, subjectCode) {
    try {
        showLoader(courseLoader);
        disableDropdown(courseSelect);
        clearDropdown(courseSelect);

        const courses = await fetchCourses(universityId, subjectCode);

        courses.forEach(course => {
            const option = document.createElement("option");
            option.value = course.key;

            option.textContent = `${course.key}`;

            if (course.type === "COURSE") {
                option.textContent += ` - ${course.title}`
            } else if (course.type === "SERIES") {
                option.textContent += ` - `
                for (let i = 0; i < course.courses.length; i++) {
                    option.textContent += course.courses[i].title;

                    if (i !== course.courses.length - 1) {
                        option.textContent += ", "
                    }
                }
            }

            courseSelect.appendChild(option);
        });

        enableDropdown(courseSelect);
        console.log("Populated course dropdown with", courses.length, "options");
    } catch (error) {
        console.error("Error loading courses:", error);
        alert("Failed to load courses. Please try again.");
    } finally {
        hideLoader(courseLoader);
    }
}

function buildCourseFullLabel(course) {
    if (!course) {
        return "";
    }

    if (course.type === "COURSE") {
        return `${course.key} - ${course.title || ""}`.trim();
    }

    if (course.type === "SERIES") {
        const names = (course.courses || []).map(c => c.title).join(", ");
        return `${course.key} - ${names}`;
    }

    return course.key || "";
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

    raw.forEach((row) => {
        const college = row.sending_name;
        const group = normalizeSendingNode(row.sending_articulation || {});

        if (!byCollege.has(college)) {
            byCollege.set(college, []);
        }

        byCollege.get(college).push(group);
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
    console.log("Cleared articulation results");
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
        console.log("No articulations available for this course");
    } else {
        noArticulations.style.display = "none";
        articulationCards.innerHTML = articulations.map(collegeData => createArticulationCard(collegeData)).join("");
        console.log("Displayed", articulations.length, "articulation cards");
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
        const notesHtml = renderNotes(notes, "above");

        const inner = courses.map((c, i) => {
            let html = renderCourseItem(c);
            if (i < courses.length - 1) {
                html += `<div class="course-separator ${sepClass}">${sepText}</div>`;
            }
            return html;
        }).join("");

        return `<li class="course-item">${notesHtml}<div class="${boxClass}">${inner}</div></li>`;
    }

    if (type === "nested") {
        // Support per-edge joins array; fallback to uniform join
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


universitySelect.addEventListener("change", async (e) => {
    const universityName = e.target.item(e.target.selectedIndex).label

    console.log("University selected:", universityName);
    currentState.selectedUniversity = universityName;
    currentState.selectedSubject = null;
    currentState.selectedCourse = null;

    clearArticulations();

    clearDropdown(subjectSelect);
    disableDropdown(subjectSelect);
    clearDropdown(courseSelect);
    disableDropdown(courseSelect);

    if (universityName) {
        await populateSubjects(universityName);
    }
});

subjectSelect.addEventListener("change", async (e) => {
    const subjectCode = e.target.value;

    console.log("Subject selected:", subjectCode);
    currentState.selectedSubject = subjectCode;
    currentState.selectedCourse = null;

    clearArticulations();

    clearDropdown(courseSelect);
    disableDropdown(courseSelect);
    if (subjectCode && currentState.selectedUniversity) {
        await populateCourses(currentState.selectedUniversity, subjectCode);
    }
});

courseSelect.addEventListener("change", async (e) => {
    const courseCode = e.target.value;

    console.log("Course selected:", courseCode);
    currentState.selectedCourse = courseCode;

    clearArticulations();

    if (courseCode && currentState.selectedUniversity && currentState.selectedSubject) {
        const resultsSection = document.getElementById("articulation-results");
        const loadingDiv = document.getElementById("articulation-loading");
        resultsSection.style.display = "block";
        loadingDiv.style.display = "flex";

        try {
            const articulationData = await fetchArticulations(
                currentState.selectedUniversity,
                currentState.selectedSubject,
                courseCode
            );
            displayArticulations(articulationData, articulationData.courseFull);
        } catch (error) {
            console.error("Error fetching articulations:", error);
            alert("Failed to load articulations. Please try again.");
            loadingDiv.style.display = "none";
        }
    }
});

window.addEventListener("DOMContentLoaded", () => {
    console.log("Loading universities...");
    populateUniversities();
});