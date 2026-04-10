const API = "/api/v1";
let myProfileId = localStorage.getItem("ttmm_profile_id");
let currentRequestTab = "received";
let requestModalTarget = null;
let currentView = localStorage.getItem("ttmm_view") || "cards";
let defaults = {};
let selectedPlaces = []; // selected default places
let customPlaces = [];   // custom places not in defaults
let suppressPlaceEvents = false; // prevent recursive event handling
let filtersVisible = false;
let activeFilters = {
    levels: [],
    places: [],
    day: "",
    timeFrom: "",
    timeTo: "",
    preferences: [], // selected preference filters
    exactDate: "" // exact date filter (YYYY-MM-DD)
};
let currentSort = { column: "name", asc: true };
let matchMode = false; // when true, only show matching profiles
let matchScores = {}; // profileId -> score
let selectedPreferences = []; // user's selected preferences

// Configure marked.js for markdown rendering
if (typeof marked !== "undefined") {
    marked.setOptions({
        breaks: true,
        gfm: true,
    });
}

function renderMarkdown(text) {
    if (typeof marked !== "undefined" && text) {
        return marked.parse(text);
    }
    // Fallback: basic bold and inline code
    return text
        .replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>")
        .replace(/`(.*?)`/g, "<code>$1</code>");
}

// ========== INITIALIZATION ==========
document.addEventListener("DOMContentLoaded", async () => {
    await loadDefaults();
    setupNavigation();
    setupProfileForm();

    // Prevent multiple profile modal instances
    document.getElementById("profileModal").addEventListener("hidden.bs.modal", () => {
        document.querySelectorAll(".modal-backdrop").forEach(el => el.remove());
        document.body.classList.remove("modal-open");
        document.body.style.paddingRight = "";
    });
    setupRequestTabs();
    setupConfirmRequest();
    setupViewToggle();
    setupPlaceAnywhere();
    setupFilters();
    setupChat();
    // Show Find Matches button if user already has a profile
    if (myProfileId) {
        const btn = document.getElementById("find-matches-btn");
        if (btn) btn.style.display = "inline-block";
    }
    navigateTo("profiles");
});

async function loadDefaults() {
    try {
        const res = await fetch("/static/defaults.json");
        defaults = await res.json();
    } catch {
        defaults = { places: [], contact_types: ["Telegram", "Phone"], levels: ["beginner","intermediate","advanced","professional"] };
    }
}

function setupPlaceAnywhere() {
    document.getElementById("place-anywhere").addEventListener("change", (e) => {
        const disabled = e.target.checked;
        document.querySelectorAll(".default-place-cb").forEach(cb => {
            cb.disabled = disabled;
            cb.closest('.form-check').classList.toggle('text-muted', disabled);
        });
        document.getElementById("custom-place-group").classList.toggle("d-none", disabled);
        document.getElementById("selected-places").classList.toggle("d-none", disabled);
    });
}

function syncCheckboxesToArrays() {
    // Read all checkboxes and rebuild arrays from their state
    document.querySelectorAll(".default-place-cb").forEach(cb => {
        if (cb.checked && !selectedPlaces.includes(cb.value)) {
            selectedPlaces.push(cb.value);
        } else if (!cb.checked) {
            selectedPlaces = selectedPlaces.filter(p => p !== cb.value);
        }
    });
    renderSelectedPlaces();
}

function renderDefaultPlaces() {
    const container = document.getElementById("default-places");
    container.innerHTML = defaults.places.map(place => `
        <div class="form-check">
            <input class="form-check-input default-place-cb" type="checkbox" value="${place}" id="place-${place.replace(/\s/g, '_')}">
            <label class="form-check-label" for="place-${place.replace(/\s/g, '_')}">${place}</label>
        </div>
    `).join("");

    container.querySelectorAll(".default-place-cb").forEach(cb => {
        cb.addEventListener("change", () => {
            if (suppressPlaceEvents) return;
            if (cb.checked) {
                if (!selectedPlaces.includes(cb.value)) selectedPlaces.push(cb.value);
            } else {
                selectedPlaces = selectedPlaces.filter(p => p !== cb.value);
            }
            renderSelectedPlaces();
        });
    });
}

function renderSelectedPlaces() {
    const container = document.getElementById("selected-places");
    const allPlaces = [...new Set([...selectedPlaces, ...customPlaces])];
    if (allPlaces.length === 0) {
        container.innerHTML = "";
        return;
    }
    container.innerHTML = allPlaces.map(p => {
        const safeP = p.replace(/'/g, "\\'");
        return `<span class="badge bg-primary me-1 mb-1">
            ${p}
            <button type="button" class="btn-close btn-close-white" style="font-size:0.5rem" onclick="removePlace('${safeP}')"></button>
        </span>`;
    }).join("");
}

function removePlace(place) {
    suppressPlaceEvents = true;
    if (selectedPlaces.includes(place)) {
        selectedPlaces = selectedPlaces.filter(p => p !== place);
        const cb = document.querySelector(`.default-place-cb[value="${place.replace(/'/g, "\\'")}"]`);
        if (cb) cb.checked = false;
    }
    if (customPlaces.includes(place)) {
        customPlaces = customPlaces.filter(p => p !== place);
    }
    suppressPlaceEvents = false;
    renderSelectedPlaces();
}

function addCustomPlace() {
    const input = document.getElementById("custom-place");
    const value = input.value.trim();
    if (!value) return;
    const allKnown = [...defaults.places, ...selectedPlaces, ...customPlaces];
    if (allKnown.includes(value)) {
        input.value = "";
        return;
    }
    customPlaces.push(value);
    input.value = "";
    renderSelectedPlaces();
}

function collectPlaces() {
    if (document.getElementById("place-anywhere").checked) return ["anywhere"];
    return [...selectedPlaces, ...customPlaces];
}

function setPlacesFromData(places) {
    suppressPlaceEvents = true;
    selectedPlaces = [];
    customPlaces = [];

    document.getElementById("place-anywhere").checked = false;
    document.getElementById("place-anywhere").dispatchEvent(new Event("change"));

    if (!places || places.length === 0) {
        suppressPlaceEvents = false;
        renderSelectedPlaces();
        return;
    }

    if (places.includes("anywhere")) {
        document.getElementById("place-anywhere").checked = true;
        document.getElementById("place-anywhere").dispatchEvent(new Event("change"));
        suppressPlaceEvents = false;
        renderSelectedPlaces();
        return;
    }

    places.forEach(p => {
        if (defaults.places.includes(p)) {
            selectedPlaces.push(p);
        } else {
            customPlaces.push(p);
        }
    });

    // Now sync checkboxes
    document.querySelectorAll(".default-place-cb").forEach(cb => {
        cb.checked = selectedPlaces.includes(cb.value);
    });

    suppressPlaceEvents = false;
    renderSelectedPlaces();
}

// ========== PREFERENCES (PROFILE FORM) ==========
function renderPreferences() {
    const container = document.getElementById("preferences-section");
    if (!container || !defaults.preferences) return;
    const prefs = defaults.preferences;

    let html = `<div class="card bg-light"><div class="card-body py-2 px-3">`;
    html += `<div class="mb-2"><strong>Game Mode</strong></div>`;
    (prefs.game_modes || []).forEach(p => {
        const checked = selectedPreferences.includes(p) ? "checked" : "";
        html += `<div class="form-check">
            <input class="form-check-input pref-cb" type="checkbox" value="${p}" id="pref-${p.replace(/[\s()]/g, '_')}" ${checked}>
            <label class="form-check-label" for="pref-${p.replace(/[\s()]/g, '_')}">${p}</label>
        </div>`;
    });
    html += `<div class="mb-2 mt-2"><strong>Time Commitment</strong></div>`;
    (prefs.time_commitment || []).forEach(p => {
        const checked = selectedPreferences.includes(p) ? "checked" : "";
        html += `<div class="form-check">
            <input class="form-check-input pref-cb" type="checkbox" value="${p}" id="pref-${p.replace(/[\s()<+>]/g, '_')}" ${checked}>
            <label class="form-check-label" for="pref-${p.replace(/[\s()<+>]/g, '_')}">${p}</label>
        </div>`;
    });
    html += `</div></div>`;
    container.innerHTML = html;

    container.querySelectorAll(".pref-cb").forEach(cb => {
        cb.addEventListener("change", () => {
            if (cb.checked) {
                if (!selectedPreferences.includes(cb.value)) selectedPreferences.push(cb.value);
            } else {
                selectedPreferences = selectedPreferences.filter(p => p !== cb.value);
            }
        });
    });
}

function collectPreferences() {
    return [...selectedPreferences];
}

function setPreferencesFromData(prefs) {
    selectedPreferences = Array.isArray(prefs) ? [...prefs] : [];
    document.querySelectorAll(".pref-cb").forEach(cb => {
        cb.checked = selectedPreferences.includes(cb.value);
    });
}

// ========== PREFERENCES FILTER ==========
function renderPrefFilters() {
    const modesContainer = document.getElementById("filter-pref-modes");
    const timeContainer = document.getElementById("filter-pref-time");
    if (!modesContainer || !defaults.preferences) return;

    const prefs = defaults.preferences;
    modesContainer.innerHTML = `<div class="text-muted fst-italic mb-1">Game Mode</div>` +
        (prefs.game_modes || []).map(p => `
            <div class="form-check">
                <input class="form-check-input filter-pref-cb" type="checkbox" value="${p}" id="fpref-${p.replace(/[\s()]/g, '_')}">
                <label class="form-check-label" for="fpref-${p.replace(/[\s()]/g, '_')}">${p}</label>
            </div>
        `).join("");

    timeContainer.innerHTML = `<div class="text-muted fst-italic mb-1">Time Commitment</div>` +
        (prefs.time_commitment || []).map(p => `
            <div class="form-check">
                <input class="form-check-input filter-pref-cb" type="checkbox" value="${p}" id="fpref-${p.replace(/[\s()<+>]/g, '_')}">
                <label class="form-check-label" for="fpref-${p.replace(/[\s()<+>]/g, '_')}">${p}</label>
            </div>
        `).join("");

    modesContainer.querySelectorAll(".filter-pref-cb").forEach(cb => {
        cb.addEventListener("change", () => {
            if (cb.checked) {
                if (!activeFilters.preferences.includes(cb.value)) activeFilters.preferences.push(cb.value);
            } else {
                activeFilters.preferences = activeFilters.preferences.filter(p => p !== cb.value);
            }
            applyFilters();
        });
    });
    timeContainer.querySelectorAll(".filter-pref-cb").forEach(cb => {
        cb.addEventListener("change", () => {
            if (cb.checked) {
                if (!activeFilters.preferences.includes(cb.value)) activeFilters.preferences.push(cb.value);
            } else {
                activeFilters.preferences = activeFilters.preferences.filter(p => p !== cb.value);
            }
            applyFilters();
        });
    });
}

function clearPrefFilter() {
    activeFilters.preferences = [];
    document.querySelectorAll(".filter-pref-cb").forEach(cb => cb.checked = false);
    applyFilters();
}

function clearExactDateFilter() {
    const el = document.getElementById("filter-exact-date");
    if (el) el.value = "";
    applyFilters();
}

function clearTimeFilters() {
    clearTimeFilter();
    clearExactDateFilter();
}

function switchTimeFilterTab(tab, e) {
    e.preventDefault();
    document.querySelectorAll("#time-filter-tabs .nav-link").forEach(l => l.classList.remove("active"));
    e.target.classList.add("active");

    document.getElementById("time-filter-dayofweek").style.display = tab === "dayofweek" ? "" : "none";
    document.getElementById("time-filter-exactdate").style.display = tab === "exactdate" ? "" : "none";

    // Clear the inactive filter
    if (tab === "exactdate") {
        document.getElementById("filter-day").value = "";
        activeFilters.day = "";
    } else {
        document.getElementById("filter-exact-date").value = "";
        activeFilters.exactDate = "";
    }
    applyFilters();
}

function profileMatchesPreferences(profile) {
    if (activeFilters.preferences.length === 0) return true;
    const profilePrefs = Array.isArray(profile.preferences) ? profile.preferences : [];
    if (profilePrefs.length === 0) return false;
    // At least one filter must match one of profile's preferences
    return activeFilters.preferences.some(fp => profilePrefs.includes(fp));
}

// ========== FILTERS ==========
function setupFilters() {
    // Build skill level checkboxes
    const levelContainer = document.getElementById("filter-levels");
    if (!levelContainer) return;
    levelContainer.innerHTML = defaults.levels.map(level => `
        <div class="form-check">
            <input class="form-check-input filter-level-cb" type="checkbox" value="${level}" id="filter-level-${level}">
            <label class="form-check-label" for="filter-level-${level}">${level.charAt(0).toUpperCase() + level.slice(1)}</label>
        </div>
    `).join("");

    levelContainer.querySelectorAll(".filter-level-cb").forEach(cb => {
        cb.addEventListener("change", () => {
            if (cb.checked) {
                if (!activeFilters.levels.includes(cb.value)) activeFilters.levels.push(cb.value);
            } else {
                activeFilters.levels = activeFilters.levels.filter(l => l !== cb.value);
            }
            applyFilters();
        });
    });

    // Build place checkboxes (from defaults + "anywhere")
    const placeContainer = document.getElementById("filter-places");
    const filterPlaces = [...defaults.places, "anywhere"];
    placeContainer.innerHTML = filterPlaces.map(place => `
        <div class="form-check">
            <input class="form-check-input filter-place-cb" type="checkbox" value="${place}" id="filter-place-${place.replace(/\s/g, '_')}">
            <label class="form-check-label" for="filter-place-${place.replace(/\s/g, '_')}">${place === "anywhere" ? "Anywhere" : place}</label>
        </div>
    `).join("");

    placeContainer.querySelectorAll(".filter-place-cb").forEach(cb => {
        cb.addEventListener("change", () => {
            if (cb.checked) {
                if (!activeFilters.places.includes(cb.value)) activeFilters.places.push(cb.value);
            } else {
                activeFilters.places = activeFilters.places.filter(p => p !== cb.value);
            }
            applyFilters();
        });
    });

    // Preferences filter
    renderPrefFilters();

    // Time filters
    document.getElementById("filter-day").addEventListener("change", (e) => {
        activeFilters.day = e.target.value;
        applyFilters();
    });
    document.getElementById("filter-time-from").addEventListener("change", (e) => {
        activeFilters.timeFrom = e.target.value;
        applyFilters();
    });
    document.getElementById("filter-time-to").addEventListener("change", (e) => {
        activeFilters.timeTo = e.target.value;
        applyFilters();
    });

    // Exact date filter
    document.getElementById("filter-exact-date").addEventListener("change", (e) => {
        activeFilters.exactDate = e.target.value;
        applyFilters();
    });
}

function toggleFilters() {
    filtersVisible = !filtersVisible;
    const panel = document.getElementById("filters-panel");
    const btn = document.getElementById("toggle-filters-btn");
    panel.classList.toggle("d-none", !filtersVisible);
    btn.classList.toggle("active", filtersVisible);
}

function clearLevelFilter() {
    activeFilters.levels = [];
    document.querySelectorAll(".filter-level-cb").forEach(cb => cb.checked = false);
    applyFilters();
}

function clearPlaceFilter() {
    activeFilters.places = [];
    document.querySelectorAll(".filter-place-cb").forEach(cb => cb.checked = false);
    applyFilters();
}

function clearTimeFilter() {
    activeFilters.day = "";
    activeFilters.timeFrom = "";
    activeFilters.timeTo = "";
    document.getElementById("filter-day").value = "";
    document.getElementById("filter-time-from").value = "";
    document.getElementById("filter-time-to").value = "";
    applyFilters();
}

function clearAllFilters() {
    clearLevelFilter();
    clearPlaceFilter();
    clearPrefFilter();
    clearExactDateFilter();
    clearTimeFilter();
    clearMatchFilter();
}

function clearMatchFilter() {
    matchMode = false;
    matchScores = {};
    // Reset sorting when exiting match mode
    currentSort = { column: "name", asc: true };
    const btn = document.getElementById("find-matches-btn");
    if (btn) {
        btn.classList.remove("active");
        btn.innerHTML = '<i class="bi bi-stars"></i> Find Matches';
        btn.onclick = () => findMatches();
    }
    renderProfiles();
}

async function findMatches() {
    if (!myProfileId) return;

    try {
        const myProfile = await apiGet(`/profiles/${myProfileId}`);
        const allProfiles = await apiGet("/profiles");

        const levelOrder = { beginner: 0, intermediate: 1, advanced: 2, professional: 3 };
        const myLevel = levelOrder[myProfile.level] ?? 0;
        const myPlaces = Array.isArray(myProfile.desired_place) ? myProfile.desired_place.map(p => p.toLowerCase()) : [];
        const myTimes = myProfile.available_time || [];

        const matches = allProfiles
            .filter(p => p.id !== myProfileId)
            .map(p => {
                let score = 0;
                let details = [];

                // Level match (same level or ±1)
                const theirLevel = levelOrder[p.level] ?? 0;
                const levelDiff = Math.abs(myLevel - theirLevel);
                if (levelDiff === 0) { score += 3; details.push("same level"); }
                else if (levelDiff === 1) { score += 1; details.push(`level ±1`); }

                // Place match
                const theirPlaces = Array.isArray(p.desired_place) ? p.desired_place : [];
                const placeOverlap = theirPlaces.filter(tp =>
                    myPlaces.includes(tp.toLowerCase()) || tp.toLowerCase() === "anywhere"
                ).length;
                if (placeOverlap > 0) { score += placeOverlap * 2; details.push(`${placeOverlap} place match`); }

                // Time overlap
                const theirTimes = p.available_time || [];
                let timeMatches = 0;
                myTimes.forEach(mt => {
                    const mFrom = timeToMinutes(mt.start_time);
                    const mTo = timeToMinutes(mt.end_time);
                    if (mFrom === null || mTo === null) return;

                    theirTimes.forEach(tt => {
                        const tFrom = timeToMinutes(tt.start_time);
                        const tTo = timeToMinutes(tt.end_time);
                        if (tFrom === null || tTo === null) return;

                        const mtType = mt.type || "weekly";
                        const ttType = tt.type || "weekly";

                        if (mtType === "weekly" && ttType === "weekly") {
                            // Both weekly: match on same day
                            if (mt.day === tt.day && mFrom <= tTo && tFrom <= mTo) timeMatches++;
                        } else if (mtType === "exact" && ttType === "exact") {
                            // Both exact: match on same date
                            if (mt.date === tt.date && mFrom <= tTo && tFrom <= mTo) timeMatches++;
                        } else if (mtType === "weekly" && ttType === "exact") {
                            // My weekly, their exact: check if their date falls on my day
                            const slotDate = new Date(tt.date);
                            const dayNames = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
                            if (dayNames[slotDate.getUTCDay()] === mt.day && mFrom <= tTo && tFrom <= mTo) timeMatches++;
                        } else if (mtType === "exact" && ttType === "weekly") {
                            // My exact, their weekly: check if my date falls on their day
                            const slotDate = new Date(mt.date);
                            const dayNames = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
                            if (dayNames[slotDate.getUTCDay()] === tt.day && mFrom <= tTo && tFrom <= mTo) timeMatches++;
                        }
                    });
                });
                if (timeMatches > 0) { score += timeMatches; details.push(`${timeMatches} time slot match`); }

                return { profile: p, score, details };
            })
            .filter(m => m.score > 0)
            .sort((a, b) => b.score - a.score);

        if (matches.length === 0) {
            showAlert("No matching players found. Try expanding your preferences!", "warning");
            return;
        }

        // Switch to match mode
        matchMode = true;
        matchScores = {};
        const matchedProfiles = matches.map(m => {
            matchScores[m.profile.id] = m.score;
            return m.profile;
        });
        window._matchProfiles = matchedProfiles;
        const btn = document.getElementById("find-matches-btn");
        btn.classList.add("active");
        btn.innerHTML = `<i class="bi bi-x-circle"></i> Show All (${matches.length}/${allProfiles.length - 1})`;
        btn.onclick = () => clearMatchFilter();

        // Render
        if (currentView === "cards") {
            document.getElementById("profiles-cards").classList.remove("d-none");
            document.getElementById("profiles-table").classList.add("d-none");
        } else {
            document.getElementById("profiles-cards").classList.add("d-none");
            document.getElementById("profiles-table").classList.remove("d-none");
        }
        renderProfiles(window._matchProfiles);
    } catch (err) {
        showAlert(`Failed to find matches: ${err.message}`, "danger");
    }
}

function sortBy(column) {
    if (currentSort.column === column) {
        currentSort.asc = !currentSort.asc;
    } else {
        currentSort.column = column;
        currentSort.asc = true;
    }
    renderProfiles();
}

function sortProfiles(profiles) {
    const levelOrder = { beginner: 0, intermediate: 1, advanced: 2, professional: 3 };

    return [...profiles].sort((a, b) => {
        let va, vb;
        switch (currentSort.column) {
            case "name":
                va = a.name.toLowerCase();
                vb = b.name.toLowerCase();
                break;
            case "level":
                va = levelOrder[a.level] ?? 0;
                vb = levelOrder[b.level] ?? 0;
                break;
            case "place":
                const pa = Array.isArray(a.desired_place) ? a.desired_place : [];
                const pb = Array.isArray(b.desired_place) ? b.desired_place : [];
                va = pa.join(", ");
                vb = pb.join(", ");
                break;
            case "time":
                const ta = (a.available_time || []).map(s => s.day + s.start_time).join(",");
                const tb = (b.available_time || []).map(s => s.day + s.start_time).join(",");
                va = ta;
                vb = tb;
                break;
            case "status":
                const reqA = getRequestState(a.id);
                const reqB = getRequestState(b.id);
                const statusOrder = { received: 0, approved: 1, sent: 2, none: 3 };
                va = statusOrder[reqA.type] ?? 3;
                vb = statusOrder[reqB.type] ?? 3;
                break;
            case "score":
                va = matchScores[a.id] ?? 0;
                vb = matchScores[b.id] ?? 0;
                break;
            default:
                return 0;
        }

        let cmp = 0;
        if (typeof va === "number") {
            cmp = va - vb;
        } else {
            cmp = String(va).localeCompare(String(vb));
        }
        return currentSort.asc ? cmp : -cmp;
    });
}

function updateSortIndicators() {
    ["name", "level", "place", "time", "score", "status"].forEach(col => {
        const el = document.getElementById(`sort-${col}`);
        if (!el) return;
        if (col === currentSort.column) {
            el.textContent = currentSort.asc ? " ▲" : " ▼";
        } else {
            el.textContent = "";
        }
    });
    // Show/hide score column based on match mode
    document.querySelectorAll(".match-score-col").forEach(el => {
        el.style.display = matchMode ? "" : "none";
    });
}

function timeToMinutes(timeStr) {
    if (!timeStr) return null;
    const [h, m] = timeStr.split(":").map(Number);
    return h * 60 + m;
}

function profileMatchesFilters(profile) {
    // Skill level filter
    if (activeFilters.levels.length > 0) {
        if (!activeFilters.levels.includes(profile.level)) return false;
    }

    // Place filter
    if (activeFilters.places.length > 0) {
        const profilePlaces = Array.isArray(profile.desired_place) ? profile.desired_place : [];
        if (profilePlaces.length === 0) {
            // Profile has no places set — only match if user explicitly filters for profiles without a place
            // "anywhere" filter should NOT match empty places
            return false;
        } else {
            // Check if profile has "anywhere" — they match any place filter
            if (profilePlaces.includes("anywhere")) return true;

            // Check if any selected place matches any of profile's places
            const hasMatch = activeFilters.places.some(fp => profilePlaces.includes(fp));
            if (!hasMatch) return false;
        }
    }

    // Preferences filter
    if (!profileMatchesPreferences(profile)) return false;

    // Exact date filter — show players with exact date slots on that date, plus players who have matching weekly slots
    if (activeFilters.exactDate) {
        const profileSlots = profile.available_time || [];
        const hasExactMatch = profileSlots.some(s =>
            s.type === "exact" && s.date === activeFilters.exactDate
        );
        if (!hasExactMatch) {
            // Also check if any weekly slot matches the day of week of the selected date
            const filterDate = new Date(activeFilters.exactDate + "T00:00:00Z");
            const dayNames = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
            const filterDayName = dayNames[filterDate.getUTCDay()];
            const hasWeeklyMatch = profileSlots.some(s =>
                (s.type === "weekly" || !s.type) && s.day === filterDayName
            );
            if (!hasWeeklyMatch) return false;
        }
    }

    // Time filter
    const filterDay = activeFilters.day;
    const filterFrom = timeToMinutes(activeFilters.timeFrom);
    const filterTo = timeToMinutes(activeFilters.timeTo);

    if (filterDay || filterFrom !== null || filterTo !== null) {
        const profileSlots = profile.available_time || [];
        const today = new Date();
        const hasMatch = profileSlots.some(slot => {
            const slotType = slot.type || "weekly";
            const slotFrom = timeToMinutes(slot.start_time);
            const slotTo = timeToMinutes(slot.end_time);

            // Day check
            if (filterDay) {
                if (slotType === "weekly") {
                    if (slot.day !== filterDay) return false;
                } else if (slotType === "exact") {
                    // Check if the exact date falls on the selected day of week
                    const slotDate = new Date(slot.date);
                    const dayNames = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"];
                    const slotDayName = dayNames[slotDate.getUTCDay()];
                    if (slotDayName !== filterDay) return false;
                }
            }

            // Time overlap check
            if (slotFrom === null || slotTo === null) return true;

            // Check overlap: filter range overlaps with slot range
            if (filterFrom !== null && filterTo !== null) {
                return slotFrom <= filterTo && filterFrom <= slotTo;
            } else if (filterFrom !== null) {
                return slotTo >= filterFrom;
            } else if (filterTo !== null) {
                return slotFrom <= filterTo;
            }
            return true; // no time range set, day matched
        });
        if (!hasMatch) return false;
    }

    return true;
}

function applyFilters() {
    // Use match results if in match mode, otherwise use full profile list
    const baseProfiles = matchMode ? (window._matchProfiles || []) : (window._profilesCache || []);
    const filtered = baseProfiles.filter(profileMatchesFilters);

    // Update active filters count
    let count = 0;
    if (activeFilters.levels.length > 0) count++;
    if (activeFilters.places.length > 0) count++;
    if (activeFilters.preferences.length > 0) count++;
    if (activeFilters.exactDate) count++;
    if (activeFilters.day) count++;
    if (activeFilters.timeFrom) count++;
    if (activeFilters.timeTo) count++;

    const countBadge = document.getElementById("active-filters-count");
    const clearAllBtn = document.getElementById("clear-all-filters");
    if (count > 0) {
        countBadge.style.display = "inline-block";
        countBadge.textContent = `${count} active`;
        clearAllBtn.style.display = "inline-block";
    } else {
        countBadge.style.display = "none";
        clearAllBtn.style.display = "none";
    }

    // Re-render with filtered data
    renderProfiles(filtered);
}

function setupViewToggle() {
    // Restore saved view button state
    document.querySelectorAll("#view-toggle button").forEach(btn => {
        btn.classList.toggle("active", btn.dataset.view === currentView);
        btn.addEventListener("click", () => {
            document.querySelectorAll("#view-toggle button").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            currentView = btn.dataset.view;
            localStorage.setItem("ttmm_view", currentView);
            renderProfiles();
        });
    });
}

function setupNavigation() {
    document.querySelectorAll(".nav-link[data-page]").forEach(link => {
        link.addEventListener("click", e => {
            e.preventDefault();
            navigateTo(link.dataset.page);
        });
    });
}

function navigateTo(page) {
    document.querySelectorAll(".page").forEach(p => p.classList.add("d-none"));
    document.querySelectorAll(".nav-link").forEach(l => l.classList.remove("active"));

    const pageEl = document.getElementById(`page-${page}`);
    if (pageEl) pageEl.classList.remove("d-none");

    const navLink = document.querySelector(`.nav-link[data-page="${page}"]`);
    if (navLink) navLink.classList.add("active");

    switch(page) {
        case "profiles": loadProfiles(); break;
        case "my-profile": loadMyProfile(); break;
        case "requests":
            updateSortArrow();
            loadRequests();
            break;
        case "faq": break; // static page, no data needed
    }
}

function updateSortArrow() {
    // Show arrow on the currently active sort button
    document.querySelectorAll("#request-sort-btns .sort-arrow").forEach(a => a.remove());
    const activeBtn = document.querySelector("#request-sort-btns button.active");
    if (activeBtn) {
        const arrow = document.createElement("span");
        arrow.className = "sort-arrow";
        arrow.textContent = currentRequestSortAsc ? " ▲" : " ▼";
        activeBtn.appendChild(arrow);
    }
}

function showMyProfile() {
    navigateTo("my-profile");
}

// ========== ALERTS ==========
function showAlert(message, type = "success") {
    const container = document.getElementById("alert-container");
    const alert = document.createElement("div");
    alert.className = `alert alert-${type} alert-dismissible fade show`;
    alert.innerHTML = `
        ${renderMarkdown(message)}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    container.appendChild(alert);
    setTimeout(() => alert.remove(), 8000);
}

// ========== REQUEST STATE HELPER ==========
function getRequestState(profileId) {
    if (!myProfileId) return { type: "none" };

    const req = _userRequests.find(r =>
        (r.sender_id === myProfileId && r.receiver_id === profileId) ||
        (r.sender_id === profileId && r.receiver_id === myProfileId)
    );

    if (!req) return { type: "none" };

    const isMutual = req.status === "approved";
    const isSentByMe = req.sender_id === myProfileId;
    const isReceivedByMe = req.receiver_id === myProfileId;

    if (isMutual) return { type: "approved", request: req };
    if (isSentByMe && req.status === "pending") return { type: "sent", request: req };
    if (isReceivedByMe && req.status === "pending") return { type: "received", request: req };

    // declined or other — allow re-send
    return { type: "none" };
}

function renderRequestButton(profileId, profileName, compact = false) {
    const state = getRequestState(profileId);
    const safeName = profileName.replace(/'/g, "\\'");

    switch (state.type) {
        case "none":
            return compact
                ? `<button class="btn btn-sm btn-primary" title="Send Request" onclick="event.stopPropagation(); openRequestModal('${profileId}', '${safeName}')">
                        <i class="bi bi-send"></i>
                   </button>`
                : `<button class="btn btn-sm btn-primary" title="Send Request" onclick="event.stopPropagation(); openRequestModal('${profileId}', '${safeName}')">
                        <i class="bi bi-send"></i> Send Request
                   </button>`;
        case "sent":
            return compact
                ? `<button class="btn btn-sm btn-secondary" disabled title="Waiting for approval">
                        <i class="bi bi-hourglass-split"></i>
                   </button>`
                : `<button class="btn btn-sm btn-secondary" disabled title="Waiting for approval">
                        <i class="bi bi-hourglass-split"></i> Waiting
                   </button>`;
        case "received":
            return compact
                ? `<div class="btn-group btn-group-sm">
                        <button class="btn btn-success" title="Approve" onclick="event.stopPropagation(); inlineApprove('${state.request.id}', '${safeName}', true)">
                            <i class="bi bi-check-lg"></i>
                        </button>
                        <button class="btn btn-danger" title="Decline" onclick="event.stopPropagation(); inlineApprove('${state.request.id}', '${safeName}', false)">
                            <i class="bi bi-x-lg"></i>
                        </button>
                   </div>`
                : `<div class="btn-group btn-group-sm">
                        <button class="btn btn-success" title="Approve" onclick="event.stopPropagation(); inlineApprove('${state.request.id}', '${safeName}', true)">
                            <i class="bi bi-check-lg"></i> Approve
                        </button>
                        <button class="btn btn-danger" title="Decline" onclick="event.stopPropagation(); inlineApprove('${state.request.id}', '${safeName}', false)">
                            <i class="bi bi-x-lg"></i> Decline
                        </button>
                   </div>`;
        case "approved":
            return compact
                ? `<button class="btn btn-sm btn-success" title="Show Contacts" onclick="event.stopPropagation(); inlineShowContacts('${state.request.id}')">
                        <i class="bi bi-eye"></i>
                   </button>`
                : `<button class="btn btn-sm btn-success" title="Show Contacts" onclick="event.stopPropagation(); inlineShowContacts('${state.request.id}')">
                        <i class="bi bi-eye"></i> Contacts
                   </button>`;
    }
}

// Inline approve/decline (from profile list)
async function inlineApprove(requestId, playerName, approve) {
    try {
        await apiPost(`/match-requests/${requestId}/respond`, {
            approved: approve,
            user_id: myProfileId
        });
        showAlert(approve
            ? `Request from ${playerName} approved!`
            : `Request from ${playerName} declined.`);
        // Refresh requests cache and re-render
        if (myProfileId) {
            const [received, sent] = await Promise.all([
                apiGet(`/match-requests/received/${myProfileId}`),
                apiGet(`/match-requests/sent/${myProfileId}`),
            ]);
            _userRequests = [...received, ...sent];
        }
        renderProfiles();
    } catch (err) {
        showAlert(`Failed: ${err.message}`, "danger");
    }
}

async function inlineShowContacts(requestId) {
    try {
        const data = await apiGet(`/match-requests/${requestId}/contacts?user_id=${myProfileId}`);
        // Close profile modal first if open
        const profileModalEl = document.getElementById("profileModal");
        const profileModal = bootstrap.Modal.getInstance(profileModalEl);
        if (profileModal) profileModal.hide();

        // Close any existing contacts modal to prevent stacking
        const contactsModalEl = document.getElementById("contactsModal");
        const existingModal = bootstrap.Modal.getInstance(contactsModalEl);
        if (existingModal) existingModal.dispose();

        // Determine the other person's info
        const isSender = data.sender_id === myProfileId;
        const otherName = isSender ? data.receiver_name : data.sender_name;
        const otherContact = isSender ? data.receiver_contact : data.sender_contact;

        const body = document.getElementById("contacts-modal-body");
        body.innerHTML = `
            <div class="text-center">
                <h6><i class="bi bi-person-circle"></i> ${otherName}</h6>
                <ul class="list-unstyled contacts-list">
                    ${Object.entries(otherContact).map(([k,v]) => `<li class="contact-item"><strong>${k}:</strong> <span class="text-break">${v}</span></li>`).join("") || '<li class="text-muted">No contacts</li>'}
                </ul>
            </div>
        `;
        setTimeout(() => new bootstrap.Modal(contactsModalEl).show(), 400);
    } catch (err) {
        showAlert(`Failed to load contacts: ${err.message}`, "danger");
    }
}

// ========== PROFILES LIST ==========
let _userRequests = []; // cache of current user's requests

async function loadProfiles() {
    const cardsContainer = document.getElementById("profiles-cards");
    const tableContainer = document.getElementById("profiles-table");

    // Only show loading in the currently visible container
    if (currentView === "cards") {
        cardsContainer.classList.remove("d-none");
        tableContainer.classList.add("d-none");
        cardsContainer.innerHTML = '<div class="text-center py-4"><div class="spinner-border"></div></div>';
    } else {
        cardsContainer.classList.add("d-none");
        tableContainer.classList.remove("d-none");
        document.getElementById("profiles-table-body").innerHTML = '<tr><td colspan="5" class="text-center py-4"><div class="spinner-border"></div></td></tr>';
    }

    try {
        const profiles = await apiGet("/profiles");
        if (profiles.length === 0) {
            const emptyHtml = '<div class="col-12 text-center text-muted py-5">No players yet. Create your profile first!</div>';
            cardsContainer.innerHTML = emptyHtml;
            document.getElementById("profiles-table-body").innerHTML = '<tr><td colspan="5" class="text-center text-muted py-4">No players yet.</td></tr>';
            window._profilesCache = [];
            return;
        }

        // Fetch user requests to determine button state per profile
        _userRequests = [];
        if (myProfileId) {
            try {
                const [received, sent] = await Promise.all([
                    apiGet(`/match-requests/received/${myProfileId}`),
                    apiGet(`/match-requests/sent/${myProfileId}`),
                ]);
                _userRequests = [...received, ...sent];
            } catch { /* no requests yet */ }
        }

        window._profilesCache = profiles;
        applyFilters();
    } catch (err) {
        const errMsg = `<div class="alert alert-danger">Failed to load profiles: ${err.message}</div>`;
        cardsContainer.innerHTML = errMsg;
        document.getElementById("profiles-table-body").innerHTML = `<tr><td colspan="5">${errMsg}</td></tr>`;
    }
}

function renderProfiles(profiles) {
    // Determine base profiles: match results if in match mode, otherwise full list
    const baseProfiles = matchMode ? (window._matchProfiles || []) : (window._profilesCache || []);
    const allProfiles = profiles !== undefined ? profiles : baseProfiles;
    const sorted = sortProfiles(allProfiles);
    updateSortIndicators();

    const cardsContainer = document.getElementById("profiles-cards");
    const tableBody = document.getElementById("profiles-table-body");
    const tableContainer = document.getElementById("profiles-table");

    if (sorted.length === 0) {
        cardsContainer.innerHTML = '<div class="col-12 text-center text-muted py-5">No players found matching your filters.</div>';
        tableBody.innerHTML = '<tr><td colspan="6" class="text-center text-muted py-4">No players found matching your filters.</td></tr>';
    } else {
        cardsContainer.innerHTML = sorted.map(p => createProfileCard(p)).join("");
        tableBody.innerHTML = sorted.map(p => createProfileRow(p)).join("");
    }

    // Click handler for cards/rows to open detail modal
    document.querySelectorAll(".profile-detail-trigger").forEach(el => {
        el.addEventListener("click", (e) => {
            if (e.target.closest("button")) return; // don't intercept Send Request button
            openProfileModal(el.dataset.profileId);
        });
    });

    // Toggle visibility based on current view
    if (currentView === "cards") {
        cardsContainer.classList.remove("d-none");
        tableContainer.classList.add("d-none");
    } else {
        cardsContainer.classList.add("d-none");
        tableContainer.classList.remove("d-none");
    }
}

function createProfileCard(profile) {
    const isMe = profile.id === myProfileId;
    const levelClass = `level-${profile.level}`;
    const timeSlots = (profile.available_time || []).slice(0, 4).map(t => {
        if (t.type === "exact") {
            return `<span class="badge bg-light text-dark me-1" title="${t.date}"><i class="bi bi-calendar-event"></i> ${t.date} ${t.start_time}-${t.end_time}</span>`;
        }
        return `<span class="badge bg-light text-dark me-1">${t.day} ${t.start_time}-${t.end_time}</span>`;
    }).join("") + ((profile.available_time || []).length > 4 ? ` <small class="text-muted">+${(profile.available_time || []).length - 4} more</small>` : "");
    const places = Array.isArray(profile.desired_place) ? profile.desired_place : [];
    const placesBadges = places.length > 0
        ? places.map(p => p === "anywhere"
            ? '<span class="badge bg-success me-1"><i class="bi bi-geo-alt"></i> Anywhere</span>'
            : `<span class="badge bg-info text-dark me-1"><i class="bi bi-geo-alt"></i> ${p}</span>`
        ).join("")
        : "";
    const matchBadge = matchMode && matchScores[profile.id]
        ? `<span class="badge bg-warning text-dark float-end" title="Match score"><i class="bi bi-stars"></i> ${matchScores[profile.id]}</span>`
        : "";

    return `
        <div class="col-md-6 col-lg-4">
            <div class="card profile-card profile-detail-trigger shadow-sm h-100" data-profile-id="${profile.id}" style="cursor:pointer">
                <div class="card-body">
                    ${matchBadge}
                    <div class="d-flex justify-content-between align-items-start mb-2">
                        <h5 class="card-title mb-0">${profile.name} ${isMe ? '<span class="badge bg-primary">You</span>' : ''}</h5>
                        <span class="level-badge ${levelClass}">${profile.level}</span>
                    </div>
                    ${placesBadges ? `<div class="mb-1">${placesBadges}</div>` : ''}
                    ${timeSlots ? `<div class="mb-2">${timeSlots}</div>` : ''}
                    <div class="mt-3">
                        ${!isMe && myProfileId ? renderRequestButton(profile.id, profile.name, false) : ''}
                        ${!myProfileId ? `<small class="text-muted">Create profile to interact</small>` : ''}
                    </div>
                </div>
            </div>
        </div>
    `;
}

function createProfileRow(profile) {
    const isMe = profile.id === myProfileId;
    const levelClass = `level-${profile.level}`;
    const timeSlots = (profile.available_time || []).slice(0, 3).map(t => {
        if (t.type === "exact") {
            return `<span class="badge bg-light text-dark me-1" title="${t.date}"><i class="bi bi-calendar-event"></i> ${t.date} ${t.start_time}-${t.end_time}</span>`;
        }
        return `<span class="badge bg-light text-dark me-1">${t.day} ${t.start_time}-${t.end_time}</span>`;
    }).join("") + ((profile.available_time || []).length > 3 ? ` <small class="text-muted">+${(profile.available_time || []).length - 3} more</small>` : "");
    const places = Array.isArray(profile.desired_place) ? profile.desired_place : [];
    const placesBadges = places.length > 0
        ? places.map(p => p === "anywhere"
            ? '<span class="badge bg-success me-1">Anywhere</span>'
            : `<span class="badge bg-info text-dark me-1">${p}</span>`
        ).join("")
        : '<span class="text-muted">Not set</span>';
    const matchBadge = matchMode && matchScores[profile.id]
        ? `<span class="badge bg-warning text-dark" title="Match score"><i class="bi bi-stars"></i> ${matchScores[profile.id]}</span> `
        : "";

    return `
        <tr class="profile-detail-trigger" data-profile-id="${profile.id}" style="cursor:pointer">
            <td><strong>${profile.name}</strong> ${isMe ? '<span class="badge bg-primary">You</span>' : ''}</td>
            <td><span class="level-badge ${levelClass}">${profile.level}</span></td>
            <td>${placesBadges}</td>
            <td>${timeSlots || '<span class="text-muted">Not set</span>'}</td>
            <td class="match-score-col" style="display:${matchMode ? '' : 'none'}">
                ${matchScores[profile.id] ? `<span class="badge bg-warning text-dark"><i class="bi bi-stars"></i> ${matchScores[profile.id]}</span>` : '<span class="text-muted">—</span>'}
            </td>
            <td>
                ${!isMe && myProfileId ? renderRequestButton(profile.id, profile.name, true) : ''}
                ${!myProfileId ? `<small class="text-muted">—</small>` : ''}
            </td>
        </tr>
    `;
}

// ========== MY PROFILE ==========
async function loadMyProfile() {
    renderDefaultPlaces();
    renderPreferences();

    const formEl = document.getElementById("profile-form");
    const msgEl = document.getElementById("auth-required-msg");

    // Always show form by default, hide if not auth
    if (msgEl) msgEl.style.display = "none";
    if (formEl) formEl.style.display = "block";

    if (!myProfileId) {
        // Not authenticated
        if (msgEl) msgEl.style.display = "block";
        if (formEl) formEl.style.display = "none";
        document.getElementById("profile-title").textContent = "My Profile";
        document.getElementById("delete-profile-btn").style.display = "none";
        document.getElementById("find-matches-btn").style.display = "none";
        return;
    }

    try {
        const profile = await apiGet(`/profiles/${myProfileId}`);
        document.getElementById("profile-title").textContent = "Edit Profile";
        document.getElementById("profile-name").value = profile.name;
        document.getElementById("profile-level").value = profile.level;
        document.getElementById("delete-profile-btn").style.display = "inline-block";
        document.getElementById("find-matches-btn").style.display = "inline-block";

        // Places
        setPlacesFromData(profile.desired_place);

        // Preferences
        renderPreferences();
        setPreferencesFromData(profile.preferences || []);

        // Load time slots
        clearTimeSlots();
        if (profile.available_time.length === 0) {
            addTimeSlot();
        } else {
            profile.available_time.forEach(t => {
                if (t.type === "exact") {
                    addExactTimeSlot(t.date, t.start_time, t.end_time);
                } else {
                    addTimeSlot(t.day, t.start_time, t.end_time);
                }
            });
        }

        // We can't read contact_info from public endpoint, so we keep what's in localStorage
        loadStoredContacts();

        // Additional info: handle both string and dict (OAuth metadata)
        const addInfo = profile.additional_info;
        if (typeof addInfo === "string") {
            document.getElementById("profile-additional").value = addInfo;
        } else if (addInfo && typeof addInfo === "object" && addInfo.about_text) {
            document.getElementById("profile-additional").value = addInfo.about_text;
        } else {
            document.getElementById("profile-additional").value = "";
        }
    } catch (err) {
        // Profile fetch failed - show auth required banner
        console.error("Profile load error:", err);
        if (msgEl) msgEl.style.display = "block";
        if (formEl) formEl.style.display = "none";
        document.getElementById("profile-title").textContent = "My Profile";
        // Clear stale data
        myProfileId = null;
        localStorage.removeItem("ttmm_profile_id");
        updateAuthUI();
    }
}

function loadStoredContacts() {
    clearContactFields();
    const stored = localStorage.getItem("ttmm_contacts");
    if (stored) {
        try {
            const contacts = JSON.parse(stored);
            if (Object.keys(contacts).length === 0) {
                addContactField();
            } else {
                Object.entries(contacts).forEach(([key, value]) => {
                    addContactField(key, value);
                });
            }
        } catch {
            addContactField();
        }
    } else {
        addContactField();
    }
}

function setupProfileForm() {
    let isSaving = false;

    document.getElementById("profile-form").addEventListener("submit", async (e) => {
        e.preventDefault();

        if (isSaving) return; // Prevent double submission
        isSaving = true;

        const saveBtn = document.querySelector("#profile-form button[type='submit']");
        if (saveBtn) {
            saveBtn.disabled = true;
            saveBtn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>Saving...';
        }
        
        if (!document.getElementById("profile-name").value.trim()) {
            showAlert("Name is required", "warning");
            return;
        }
        
        // additional_info: get from form, merge with existing OAuth metadata if present
        const aboutText = document.getElementById("profile-additional").value.trim() || null;
        
        // Fetch current profile to get any existing OAuth metadata
        const currentProfile = await apiGet(`/profiles/${myProfileId}`);
        let finalAdditionalInfo = aboutText;
        if (currentProfile.additional_info && typeof currentProfile.additional_info === "object") {
            // Has OAuth metadata - merge about_text into it
            if (aboutText) {
                finalAdditionalInfo = { ...currentProfile.additional_info, about_text: aboutText };
            } else {
                // Remove about_text if user cleared it
                const { about_text, ...rest } = currentProfile.additional_info;
                finalAdditionalInfo = Object.keys(rest).length > 0 ? rest : null;
            }
        }

        const data = {
            name: document.getElementById("profile-name").value.trim(),
            level: document.getElementById("profile-level").value,
            desired_place: collectPlaces(),
            preferences: collectPreferences(),
            available_time: collectTimeSlots(),
            additional_info: finalAdditionalInfo,
            contact_info: collectContacts(),
        };

        // Ensure no null/undefined values
        if (!data.desired_place) data.desired_place = [];
        if (!data.available_time) data.available_time = [];
        if (data.contact_info === null || data.contact_info === undefined) data.contact_info = {};

        console.log("Submitting profile data:", JSON.stringify(data));
        
        try {
            let profile;
            if (myProfileId) {
                profile = await apiPut(`/profiles/${myProfileId}`, data);
                showAlert("Profile updated!");
            } else {
                profile = await apiPost("/profiles", data);
                myProfileId = profile.id;
                localStorage.setItem("ttmm_profile_id", myProfileId);
                document.getElementById("delete-profile-btn").style.display = "inline-block";
                document.getElementById("find-matches-btn").style.display = "inline-block";
                document.getElementById("profile-title").textContent = "Edit Profile";
                showAlert("Profile created!");
            }
            
            // Store contacts locally for future edits
            localStorage.setItem("ttmm_contacts", JSON.stringify(data.contact_info));

            // Navigate to players page and open own profile
            navigateTo("profiles");
            setTimeout(() => {
                if (myProfileId) openProfileModal(myProfileId);
            }, 300);
        } catch (err) {
            console.error("Profile save error:", err);
            let errorMsg = err.message || String(err);
            // Check for moderation rejection
            if (errorMsg.includes("Profile content not acceptable")) {
                const reason = errorMsg.split("Profile content not acceptable: ")[1] || "";
                showAlert(
                    `⚠️ **Profile content needs improvement:** ${reason}\n\nPlease remove inappropriate language, threats, or irrelevant content and try again.`,
                    "warning"
                );
            } else {
                showAlert(`Failed to save profile: ${errorMsg}`, "danger");
            }
        } finally {
            isSaving = false;
            if (saveBtn) {
                saveBtn.disabled = false;
                saveBtn.innerHTML = '<i class="bi bi-save"></i> Save Profile';
            }
        }
    });
}

async function deleteProfile() {
    if (!myProfileId) return;
    if (!confirm("Are you sure you want to delete your profile?")) return;
    
    try {
        await apiDelete(`/profiles/${myProfileId}`);
        localStorage.removeItem("ttmm_profile_id");
        localStorage.removeItem("ttmm_contacts");
        myProfileId = null;
        document.getElementById("find-matches-btn").style.display = "none";
        clearMatchFilter();
        showAlert("Profile deleted");
        navigateTo("profiles");
    } catch (err) {
        showAlert("Failed to delete profile", "danger");
    }
}

// ========== TIME SLOTS ==========
function addTimeSlot(day = "", start = "", end = "") {
    const container = document.getElementById("time-slots");
    const div = document.createElement("div");
    div.className = "time-slot";
    div.dataset.slotType = "weekly";
    div.innerHTML = `
        <span class="badge bg-primary me-1"><i class="bi bi-arrow-repeat"></i></span>
        <select class="form-select form-select-sm slot-day" style="max-width:120px">
            ${["Monday","Tuesday","Wednesday","Thursday","Friday","Saturday","Sunday"].map(d =>
                `<option value="${d}" ${d === day ? "selected" : ""}>${d}</option>`
            ).join("")}
        </select>
        <input type="time" class="form-control form-control-sm slot-start" value="${start}">
        <span class="text-muted small">–</span>
        <input type="time" class="form-control form-control-sm slot-end" value="${end}">
        <button type="button" class="btn btn-sm btn-outline-danger" onclick="this.parentElement.remove()">
            <i class="bi bi-x"></i>
        </button>
    `;
    container.appendChild(div);
}

function addExactTimeSlot(date = "", start = "", end = "") {
    const container = document.getElementById("time-slots");
    const today = new Date().toISOString().split("T")[0];
    const div = document.createElement("div");
    div.className = "time-slot";
    div.dataset.slotType = "exact";
    div.innerHTML = `
        <span class="badge bg-success me-1"><i class="bi bi-calendar-event"></i></span>
        <input type="date" class="form-control form-control-sm slot-date" value="${date}" min="${today}" style="max-width:150px">
        <input type="time" class="form-control form-control-sm slot-start" value="${start}">
        <span class="text-muted small">–</span>
        <input type="time" class="form-control form-control-sm slot-end" value="${end}">
        <button type="button" class="btn btn-sm btn-outline-danger" onclick="this.parentElement.remove()">
            <i class="bi bi-x"></i>
        </button>
    `;
    container.appendChild(div);
}

function collectTimeSlots() {
    const slots = [];
    document.querySelectorAll("#time-slots .time-slot").forEach(row => {
        const type = row.dataset.slotType || "weekly";
        const start_time = row.querySelector(".slot-start")?.value;
        const end_time = row.querySelector(".slot-end")?.value;

        if (type === "weekly") {
            const day = row.querySelector(".slot-day")?.value;
            if (day && start_time && end_time) {
                slots.push({ type: "weekly", day, start_time, end_time });
            }
        } else {
            const date = row.querySelector(".slot-date")?.value;
            if (date && start_time && end_time) {
                slots.push({ type: "exact", date, start_time, end_time });
            }
        }
    });
    return slots;
}

function clearTimeSlots() {
    document.getElementById("time-slots").innerHTML = "";
}

// ========== CONTACT FIELDS ==========
function addContactField(key = "", value = "") {
    const container = document.getElementById("contact-fields");
    const div = document.createElement("div");
    div.className = "contact-field";
    div.innerHTML = `
        <input type="text" class="form-control form-control-sm contact-key" placeholder="Type (e.g. telegram)" value="${key}" style="max-width:150px">
        <input type="text" class="form-control form-control-sm contact-value" placeholder="Value" value="${value}">
        <button type="button" class="btn btn-sm btn-outline-danger" onclick="this.parentElement.remove()">
            <i class="bi bi-x"></i>
        </button>
    `;
    container.appendChild(div);
}

function collectContacts() {
    const contacts = {};
    document.querySelectorAll("#contact-fields .contact-field").forEach(row => {
        const key = row.querySelector(".contact-key").value.trim();
        const value = row.querySelector(".contact-value").value.trim();
        if (key && value) {
            contacts[key] = value;
        }
    });
    return contacts;
}

function clearContactFields() {
    document.getElementById("contact-fields").innerHTML = "";
}

// ========== ADDITIONAL FIELDS ==========
function addAdditionalField(key = "", value = "") {
    const container = document.getElementById("additional-fields");
    const div = document.createElement("div");
    div.className = "additional-field";
    div.innerHTML = `
        <input type="text" class="form-control form-control-sm addtl-key" placeholder="Key" value="${key}" style="max-width:150px">
        <input type="text" class="form-control form-control-sm addtl-value" placeholder="Value" value="${value}">
        <button type="button" class="btn btn-sm btn-outline-danger" onclick="this.parentElement.remove()">
            <i class="bi bi-x"></i>
        </button>
    `;
    container.appendChild(div);
}

function collectAdditionalFields() {
    const fields = {};
    document.querySelectorAll("#additional-fields .additional-field").forEach(row => {
        const key = row.querySelector(".addtl-key").value.trim();
        const value = row.querySelector(".addtl-value").value.trim();
        if (key && value) {
            fields[key] = value;
        }
    });
    return fields;
}

function clearAdditionalFields() {
    document.getElementById("additional-fields").innerHTML = "";
}

// ========== MATCH REQUESTS ==========
let currentRequestSort = "status"; // status, name, date
let currentRequestSortAsc = true;

function setupRequestTabs() {
    document.querySelectorAll("#request-tabs .nav-link").forEach(tab => {
        tab.addEventListener("click", e => {
            e.preventDefault();
            document.querySelectorAll("#request-tabs .nav-link").forEach(t => t.classList.remove("active"));
            tab.classList.add("active");
            currentRequestTab = tab.dataset.tab;
            updateSortArrow();
            loadRequests();
        });
    });
}

function sortRequests(by) {
    // Toggle direction if clicking the same button
    if (currentRequestSort === by) {
        currentRequestSortAsc = !currentRequestSortAsc;
    } else {
        currentRequestSort = by;
        // Default directions: status asc (pending first), name asc, date desc (newest first)
        currentRequestSortAsc = by !== "date";
    }

    // Update active button and arrow
    document.querySelectorAll("#request-sort-btns button").forEach(b => b.classList.remove("active"));
    const activeBtn = document.querySelector(`#request-sort-btns button[data-sort="${by}"]`);
    if (activeBtn) {
        activeBtn.classList.add("active");
        // Remove old arrows
        document.querySelectorAll("#request-sort-btns .sort-arrow").forEach(a => a.remove());
        const arrow = document.createElement("span");
        arrow.className = "sort-arrow";
        arrow.textContent = currentRequestSortAsc ? " ▲" : " ▼";
        activeBtn.appendChild(arrow);
    }

    loadRequests();
}

async function loadRequests() {
    if (!myProfileId) {
        document.getElementById("requests-list").innerHTML =
            '<div class="alert alert-warning">Create a profile first to see requests.</div>';
        return;
    }

    const container = document.getElementById("requests-list");
    container.innerHTML = '<div class="text-center py-4"><div class="spinner-border"></div></div>';

    try {
        const endpoint = currentRequestTab === "received" ? "received" : "sent";
        let requests = await apiGet(`/match-requests/${endpoint}/${myProfileId}`);

        if (requests.length === 0) {
            container.innerHTML = '<div class="text-center text-muted py-5">No requests yet.</div>';
            return;
        }

        // Sort requests
        const statusOrder = { pending: 0, approved: 1, declined: 2 };
        switch (currentRequestSort) {
            case "status":
                requests.sort((a, b) => {
                    const sa = statusOrder[a.status] ?? 3;
                    const sb = statusOrder[b.status] ?? 3;
                    if (sa !== sb) return currentRequestSortAsc ? sa - sb : sb - sa;
                    return currentRequestSortAsc ? new Date(a.created_at) - new Date(b.created_at) : new Date(b.created_at) - new Date(a.created_at);
                });
                break;
            case "name":
                requests.sort((a, b) => {
                    const na = currentRequestTab === "received" ? (a.sender_name || "") : (a.receiver_name || "");
                    const nb = currentRequestTab === "received" ? (b.sender_name || "") : (b.receiver_name || "");
                    return currentRequestSortAsc ? na.localeCompare(nb) : nb.localeCompare(na);
                });
                break;
            case "date":
                requests.sort((a, b) =>
                    currentRequestSortAsc ? new Date(a.created_at) - new Date(b.created_at) : new Date(b.created_at) - new Date(a.created_at)
                );
                break;
        }

        container.innerHTML = requests.map(r => createRequestCard(r, currentRequestTab)).join("");
    } catch (err) {
        container.innerHTML = `<div class="alert alert-danger">Failed to load requests: ${err.message}</div>`;
    }
}

function createRequestCard(request, tab) {
    const otherName = tab === "received" ? request.sender_name : request.receiver_name;
    const otherId = tab === "received" ? request.sender_id : request.receiver_id;
    let actions = "";

    if (tab === "received" && request.status === "pending") {
        actions = `
            <button class="btn btn-sm btn-success me-2" onclick="event.stopPropagation(); respondToRequest('${request.id}', true)">
                <i class="bi bi-check-lg"></i> Approve
            </button>
            <button class="btn btn-sm btn-danger" onclick="event.stopPropagation(); respondToRequest('${request.id}', false)">
                <i class="bi bi-x-lg"></i> Decline
            </button>
        `;
    }

    if (request.status === "approved") {
        actions = `
            <button class="btn btn-sm btn-success" onclick="event.stopPropagation(); showContacts('${request.id}')">
                <i class="bi bi-eye"></i> View Contacts
            </button>
        `;
    }

    const statusBadge = {
        pending: '<span class="badge bg-warning">Pending</span>',
        approved: '<span class="badge bg-success">Approved</span>',
        declined: '<span class="badge bg-danger">Declined</span>'
    }[request.status];

    return `
        <div class="card request-card ${request.status} shadow-sm mb-2 profile-detail-trigger" data-profile-id="${otherId}" style="cursor:pointer" onclick="openProfileModal('${otherId}')">
            <div class="card-body d-flex justify-content-between align-items-center">
                <div>
                    <strong><i class="bi bi-person-circle"></i> ${otherName}</strong>
                    ${statusBadge}
                    <div class="text-muted small">${new Date(request.created_at).toLocaleString()}</div>
                </div>
                <div>${actions}</div>
            </div>
        </div>
    `;
}

async function respondToRequest(requestId, approved) {
    try {
        await apiPost(`/match-requests/${requestId}/respond`, { 
            approved, 
            user_id: myProfileId 
        });
        showAlert(approved ? "Request approved! Contacts will be shared once both parties approve." : "Request declined.");
        loadRequests();
    } catch (err) {
        showAlert(`Failed to respond: ${err.message}`, "danger");
    }
}

async function showContacts(requestId) {
    try {
        const data = await apiGet(`/match-requests/${requestId}/contacts?user_id=${myProfileId}`);
        // Determine the other person's info
        const isSender = data.sender_id === myProfileId;
        const otherName = isSender ? data.receiver_name : data.sender_name;
        const otherContact = isSender ? data.receiver_contact : data.sender_contact;

        const body = document.getElementById("contacts-modal-body");
        body.innerHTML = `
            <div class="text-center">
                <h6><i class="bi bi-person-circle"></i> ${otherName}</h6>
                <ul class="list-unstyled contacts-list">
                    ${Object.entries(otherContact).map(([k,v]) => `<li class="contact-item"><strong>${k}:</strong> <span class="text-break">${v}</span></li>`).join("") || '<li class="text-muted">No contacts</li>'}
                </ul>
            </div>
        `;
        new bootstrap.Modal(document.getElementById("contactsModal")).show();
    } catch (err) {
        showAlert(`Failed to load contacts: ${err.message}`, "danger");
    }
}

// ========== PROFILE DETAIL MODAL ==========
async function openProfileModal(profileId) {
    // Clean up any existing modal instance and backdrops
    const modalEl = document.getElementById("profileModal");
    const existingModal = bootstrap.Modal.getInstance(modalEl);
    if (existingModal) existingModal.dispose();
    document.querySelectorAll(".modal-backdrop").forEach(el => el.remove());
    document.body.classList.remove("modal-open");
    document.body.style.paddingRight = "";

    const modal = new bootstrap.Modal(modalEl);
    const body = document.getElementById("profile-modal-body");
    const title = document.getElementById("profile-modal-title");
    const sendBtn = document.getElementById("profile-modal-send-request");

    title.textContent = "Loading...";
    body.innerHTML = '<div class="text-center py-3"><div class="spinner-border"></div></div>';
    sendBtn.style.display = "none";
    modal.show();

    try {
        const profile = await apiGet(`/profiles/${profileId}`);
        const isMe = profile.id === myProfileId;
        title.textContent = profile.name;

        const levelClass = `level-${profile.level}`;
        const places = Array.isArray(profile.desired_place) ? profile.desired_place : [];
        const timeSlots = profile.available_time;

        let html = `
            <div class="mb-3">
                <span class="level-badge ${levelClass} fs-6">${profile.level}</span>
            </div>
        `;

        if (places.length > 0) {
            html += `<h6 class="mt-3">Preferred Places</h6><div class="mb-2">`;
            html += places.map(p => p === "anywhere"
                ? '<span class="badge bg-success me-1 mb-1 fs-6">Anywhere</span>'
                : `<span class="badge bg-info text-dark me-1 mb-1 fs-6">${p}</span>`
            ).join("");
            html += `</div>`;
        }

        if (timeSlots.length > 0) {
            html += `<h6 class="mt-3">Available Time</h6><ul class="list-group">`;
            html += timeSlots.map(t => {
                if (t.type === "exact") {
                    return `<li class="list-group-item"><i class="bi bi-calendar-event"></i> <strong>${t.date}</strong> ${t.start_time} – ${t.end_time}</li>`;
                }
                return `<li class="list-group-item"><i class="bi bi-clock"></i> <strong>${t.day}</strong> ${t.start_time} – ${t.end_time}</li>`;
            }).join("");
            html += `</ul>`;
        } else {
            html += `<p class="text-muted mt-3">No available time set.</p>`;
        }

        if (profile.additional_info) {
            const info = profile.additional_info;
            if (typeof info === "string" && info.trim()) {
                html += `<h6 class="mt-3">About</h6><div class="text-muted">${renderMarkdown(info)}</div>`;
            } else if (typeof info === "object" && info.about_text) {
                html += `<h6 class="mt-3">About</h6><div class="text-muted">${renderMarkdown(info.about_text)}</div>`;
            }
        }

        body.innerHTML = html;

        // Update footer button based on request state
        // Only show action buttons if NOT viewing own profile
        if (!isMe && myProfileId) {
            const state = getRequestState(profile.id);
            const footer = document.querySelector("#profileModal .modal-footer");
            // Remove old send request button if exists
            const old = document.getElementById("profile-modal-action");
            if (old) old.remove();

            const actionBtn = document.createElement("div");
            actionBtn.id = "profile-modal-action";

            switch (state.type) {
                case "none":
                    actionBtn.innerHTML = `<button class="btn btn-primary" id="profile-modal-send-request" title="Send Request">
                        <i class="bi bi-send"></i>
                    </button>`;
                    actionBtn.querySelector("button").onclick = () => {
                        modal.hide();
                        openRequestModal(profile.id, profile.name);
                    };
                    break;
                case "sent":
                    actionBtn.innerHTML = `<button class="btn btn-secondary" disabled title="Waiting for approval">
                        <i class="bi bi-hourglass-split"></i>
                    </button>`;
                    break;
                case "received":
                    actionBtn.innerHTML = `<div class="btn-group">
                        <button class="btn btn-success" id="modal-approve-btn" title="Approve"><i class="bi bi-check-lg"></i></button>
                        <button class="btn btn-danger" id="modal-decline-btn" title="Decline"><i class="bi bi-x-lg"></i></button>
                    </div>`;
                    actionBtn.querySelector("#modal-approve-btn").onclick = () => inlineApproveFromModal(state.request.id, profile.name, true);
                    actionBtn.querySelector("#modal-decline-btn").onclick = () => inlineApproveFromModal(state.request.id, profile.name, false);
                    break;
                case "approved":
                    actionBtn.innerHTML = `<button class="btn btn-success" id="modal-contacts-btn" title="Show Contacts"><i class="bi bi-eye"></i></button>`;
                    actionBtn.querySelector("#modal-contacts-btn").onclick = () => inlineShowContacts(state.request.id);
                    break;
            }
            footer.appendChild(actionBtn);
        } else {
            // Viewing own profile — remove action button
            const old = document.getElementById("profile-modal-action");
            if (old) old.remove();
        }
    } catch (err) {
        body.innerHTML = `<div class="alert alert-danger">Failed to load profile: ${err.message}</div>`;
    }
}

async function inlineApproveFromModal(requestId, playerName, approve) {
    try {
        await apiPost(`/match-requests/${requestId}/respond`, {
            approved: approve,
            user_id: myProfileId
        });
        showAlert(approve
            ? `Request from ${playerName} approved!`
            : `Request from ${playerName} declined.`);
        if (myProfileId) {
            const [received, sent] = await Promise.all([
                apiGet(`/match-requests/received/${myProfileId}`),
                apiGet(`/match-requests/sent/${myProfileId}`),
            ]);
            _userRequests = [...received, ...sent];
        }
        renderProfiles();
        // Find the profile and re-open modal with updated state
        const allProfiles = window._profilesCache || [];
        const target = allProfiles.find(p => p.name === playerName);
        bootstrap.Modal.getInstance(document.getElementById("profileModal")).hide();
        if (target) setTimeout(() => openProfileModal(target.id), 300);
    } catch (err) {
        showAlert(`Failed: ${err.message}`, "danger");
    }
}

// ========== SEND REQUEST MODAL ==========
function openRequestModal(targetId, targetName) {
    requestModalTarget = targetId;
    document.getElementById("request-target-name").textContent = targetName;
    new bootstrap.Modal(document.getElementById("requestModal")).show();
}

function setupConfirmRequest() {
    document.getElementById("confirm-request-btn").addEventListener("click", async () => {
        if (!requestModalTarget || !myProfileId) return;

        try {
            await apiPost("/match-requests", {
                receiver_id: requestModalTarget,
                sender_id: myProfileId
            });
            showAlert("Request sent!");
            bootstrap.Modal.getInstance(document.getElementById("requestModal")).hide();

            // Refresh request cache and re-render
            const [received, sent] = await Promise.all([
                apiGet(`/match-requests/received/${myProfileId}`),
                apiGet(`/match-requests/sent/${myProfileId}`),
            ]);
            _userRequests = [...received, ...sent];
            renderProfiles();
        } catch (err) {
            showAlert(`Failed to send request: ${err.message}`, "danger");
        }
    });
}

// ========== API HELPERS ==========
async function apiGet(path) {
    const res = await fetch(`${API}${path}`);
    if (!res.ok) throw new Error(await res.text());
    return res.json();
}

async function apiPost(path, data) {
    const res = await fetch(`${API}${path}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data)
    });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
}

async function apiPut(path, data) {
    const res = await fetch(`${API}${path}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data)
    });
    if (!res.ok) {
        const text = await res.text();
        console.error("PUT error response:", res.status, text);
        throw new Error(text);
    }
    return res.json();
}

async function apiDelete(path) {
    const res = await fetch(`${API}${path}`, { method: "DELETE" });
    if (!res.ok) throw new Error(await res.text());
}

// ========== CHAT / AGENT ==========
let chatActionPending = null;

function setupChat() {
    // Add welcome message when navigating to agent page
}

function navigateToAgent() {
    const container = document.getElementById("chat-messages");
    if (container.children.length === 0) {
        addChatMessage("agent", "Hey! 👋 I'm your TTMM assistant. I can help you:\n\n🔍 **Find players** — \"find intermediate players\"\n📩 **Send requests** — \"send request to Alice\"\n📋 **Check requests** — \"show my requests\"\n✅ **Approve** — \"approve request from Bob\"\n✏️ **Update profile** — \"change my level to advanced\"\n📊 **Stats** — \"show statistics\"\n\nJust ask naturally!");
    }
}

function addChatMessage(sender, text) {
    const container = document.getElementById("chat-messages");
    const div = document.createElement("div");
    div.className = `mb-2 ${sender === "user" ? "text-end" : ""}`;

    const bubble = document.createElement("div");
    bubble.className = `d-inline-block px-3 py-2 rounded-3 ${sender === "user" ? "bg-primary text-white" : "bg-white border"}`;
    bubble.style.maxWidth = "85%";
    bubble.style.whiteSpace = "normal";

    bubble.innerHTML = renderMarkdown(text);

    div.appendChild(bubble);
    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
}

async function sendMessage() {
    const input = document.getElementById("chat-input");
    const text = input.value.trim();
    if (!text) return;

    addChatMessage("user", text);
    input.value = "";

    // Hide confirm bar
    document.getElementById("chat-confirm-bar").classList.add("d-none");
    chatActionPending = null;

    try {
        const data = await apiPost("/chat", {
            message: text,
            user_id: myProfileId || null
        });

        addChatMessage("agent", data.text);

        if (data.requires_confirmation && data.action) {
            chatActionPending = data.action;
            document.getElementById("chat-confirm-text").innerHTML = renderMarkdown(data.text);
            document.getElementById("chat-confirm-bar").classList.remove("d-none");
            // Scroll to bottom
            const container = document.getElementById("chat-messages");
            container.scrollTop = container.scrollHeight;
        }
    } catch (err) {
        addChatMessage("agent", `Error: ${err.message}`);
    }
}

async function confirmAction(confirmed) {
    document.getElementById("chat-confirm-bar").classList.add("d-none");

    if (!confirmed) {
        addChatMessage("agent", "Action cancelled. Is there anything else I can help with?");
        chatActionPending = null;
        return;
    }

    if (!chatActionPending) return;
    const action = chatActionPending;
    chatActionPending = null;

    // Execute the confirmed action directly (no LLM roundtrip)
    try {
        if (action.tool === "send_request") {
            if (!myProfileId) {
                addChatMessage("agent", "You need to create a profile first.");
                return;
            }
            const profiles = await apiGet("/profiles");
            const target = profiles.find(p => p.name.toLowerCase() === (action.target_name || "").toLowerCase());
            if (!target) {
                addChatMessage("agent", `Player "${action.target_name}" not found.`);
                return;
            }
            await apiPost("/match-requests", {
                sender_id: myProfileId,
                receiver_id: target.id
            });
            addChatMessage("agent", `✅ Request sent to **${action.target_name}**! They'll see it in their requests and can approve or decline.`);
            // Notify LLM that action was completed
            apiPost("/chat", {
                message: "[System: The request was sent successfully. Acknowledge this briefly.]",
                user_id: myProfileId || null
            }).catch(() => {});
        } else if (action.tool === "approve_request_by_name") {
            if (!myProfileId) {
                addChatMessage("agent", "You need to be logged in to approve requests.");
                return;
            }
            const received = await apiGet(`/match-requests/received/${myProfileId}`);
            const allProfiles = window._profilesCache || [];
            const match = received.find(r => r.status === "pending");
            if (!match) {
                addChatMessage("agent", `No pending request found from **${action.player_name}**.`);
                return;
            }
            const senderProfile = allProfiles.find(p => p.id === match.sender_id);
            const senderName = senderProfile ? senderProfile.name : action.player_name;
            const result = await apiPost(`/match-requests/${match.id}/respond`, {
                approved: true,
                user_id: myProfileId
            });
            if (result.status === "approved") {
                addChatMessage("agent", `✅ Approved! You and **${senderName}** can now see each other's contacts.`);
            } else {
                addChatMessage("agent", `Request status: ${result.status}.`);
            }
            // Notify LLM that action was completed
            apiPost("/chat", {
                message: `[System: The request from ${senderName} was approved successfully. Status: ${result.status}. Acknowledge this briefly.]`,
                user_id: myProfileId || null
            }).catch(() => {});
            // Refresh request cache
            const [r, s] = await Promise.all([
                apiGet(`/match-requests/received/${myProfileId}`),
                apiGet(`/match-requests/sent/${myProfileId}`),
            ]);
            _userRequests = [...r, ...s];
        } else if (action.tool === "approve_request" && action.request_id) {
            if (!myProfileId) {
                addChatMessage("agent", "You need to be logged in to approve requests.");
                return;
            }
            const result = await apiPost(`/match-requests/${action.request_id}/respond`, {
                approved: true,
                user_id: myProfileId
            });
            const otherName = result.sender_id === myProfileId ? result.receiver_name : result.sender_name;
            if (result.status === "approved") {
                addChatMessage("agent", `✅ Approved! You and **${otherName}** can now see each other's contacts.`);
            } else {
                addChatMessage("agent", `Request status: ${result.status}.`);
            }
            // Notify LLM that action was completed
            apiPost("/chat", {
                message: `[System: The request was approved successfully. Status: ${result.status}. Acknowledge this briefly.]`,
                user_id: myProfileId || null
            }).catch(() => {});
            const [r, s] = await Promise.all([
                apiGet(`/match-requests/received/${myProfileId}`),
                apiGet(`/match-requests/sent/${myProfileId}`),
            ]);
            _userRequests = [...r, ...s];
        } else {
            addChatMessage("agent", `Action "${action.tool}" not yet supported for direct execution.`);
        }
    } catch (err) {
        addChatMessage("agent", `Failed to execute action: ${err.message}`);
    }
}

// Override navigateTo to handle agent page
const _originalNavigateTo = navigateTo;
navigateTo = function(page) {
    if (page === "agent") {
        navigateToAgent();
    }
    _originalNavigateTo(page);
};

// ─── Authentication ───────────────────────────────────────────────
let currentUser = null;

async function checkAuthStatus() {
    try {
        const resp = await fetch("/auth/me", { credentials: "include" });
        currentUser = await resp.json();
        if (currentUser && currentUser.authenticated) {
            myProfileId = currentUser.user_id;
            localStorage.setItem("ttmm_profile_id", myProfileId);
            updateAuthUI();
            // Refresh the players page with the correct user context
            loadProfiles();
        } else {
            // Not authenticated - clear any stale profile ID
            myProfileId = null;
            localStorage.removeItem("ttmm_profile_id");
            updateAuthUI();
        }
    } catch {
        currentUser = null;
        myProfileId = null;
        localStorage.removeItem("ttmm_profile_id");
        updateAuthUI();
    }
}

function updateAuthUI() {
    const loginBtn = document.getElementById("auth-login-btn");
    const logoutBtn = document.getElementById("auth-logout-btn");
    const userNameEl = document.getElementById("auth-user-name");
    const findMatchesBtn = document.getElementById("find-matches-btn");

    if (currentUser && currentUser.authenticated) {
        // Logged in
        if (loginBtn) loginBtn.style.display = "none";
        if (logoutBtn) logoutBtn.style.display = "inline-block";
        if (userNameEl) {
            userNameEl.textContent = currentUser.name;
            userNameEl.style.display = "inline";
        }
        // Update myProfileId from auth
        myProfileId = currentUser.user_id;
        localStorage.setItem("ttmm_profile_id", myProfileId);
        if (findMatchesBtn) findMatchesBtn.style.display = "inline-block";
    } else {
        // Logged out
        if (loginBtn) loginBtn.style.display = "inline-block";
        if (logoutBtn) logoutBtn.style.display = "none";
        if (userNameEl) userNameEl.style.display = "none";
        if (findMatchesBtn) findMatchesBtn.style.display = "none";
    }
}

function googleLogin() {
    window.location.href = "/auth/login/google";
}

async function logout() {
    try {
        await fetch("/auth/logout", { method: "POST" });
    } catch {}
    currentUser = null;
    myProfileId = null;
    localStorage.removeItem("ttmm_profile_id");
    localStorage.removeItem("ttmm_contacts");
    updateAuthUI();
    navigateTo("profiles");
}

// Run auth check on page load
document.addEventListener("DOMContentLoaded", () => {
    setTimeout(checkAuthStatus, 100);
});
