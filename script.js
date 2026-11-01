/*
===========================================================
EDULINK - PHASE 2 FRONTEND
===========================================================

Features:
- FastAPI backend connection
- JWT authentication
- Email/password login
- Email/password registration
- Google Sign-In
- Questions
- Answers
- Question voting
- Helpful answer voting
- Resources
- Notices
- Help requests
- Saved questions/resources
- Profile
- Admin dashboard
- Search
- Responsive navigation
- No fake users
- No fake community data

Backend:
http://127.0.0.1:8000
===========================================================
*/


/* =========================================================
   CONFIGURATION
========================================================= */

const API_BASE =
    window.EDULINK_CONFIG?.API_BASE ||
    "http://127.0.0.1:8000";

const GOOGLE_CLIENT_ID =
    window.EDULINK_CONFIG?.GOOGLE_CLIENT_ID ||
    "";

const SAVED_KEY = "edulink_saved_items";


/* =========================================================
   AUTH STATE
========================================================= */

let authToken =
    localStorage.getItem("edulink_token");

let currentUser =
    readJSON("edulink_user", null);


/* =========================================================
   APPLICATION DATA
========================================================= */

let cachedData = {
    questions: [],
    resources: [],
    notices: [],
    procedures: [],
    helpRequests: []
};

let pendingQuestion = null;


/* =========================================================
   DOM ELEMENTS
========================================================= */

const content =
    document.getElementById("content");

const sidebar =
    document.getElementById("sidebar");

const modalOverlay =
    document.getElementById("modalOverlay");

const modalTitle =
    document.getElementById("modalTitle");

const modalFields =
    document.getElementById("modalFields");

const modalForm =
    document.getElementById("modalForm");

const toast =
    document.getElementById("toast");

const searchInput =
    document.getElementById("searchInput");


/* =========================================================
   UTILITY FUNCTIONS
========================================================= */

function readJSON(key, fallback = null) {

    try {

        const value =
            localStorage.getItem(key);

        if (value === null) {
            return fallback;
        }

        return JSON.parse(value);

    } catch (error) {

        console.error(
            "JSON read error:",
            error
        );

        return fallback;
    }
}


function escapeHTML(value = "") {

    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");
}


function initials(name = "Guest") {

    return name
        .trim()
        .split(/\s+/)
        .filter(Boolean)
        .map(part => part[0])
        .join("")
        .slice(0, 2)
        .toUpperCase() || "G";
}


function formatDate(value) {

    if (!value) {
        return "";
    }

    const date =
        new Date(value);

    if (Number.isNaN(date.getTime())) {
        return "";
    }

    return date.toLocaleDateString(
        undefined,
        {
            day: "numeric",
            month: "short",
            year: "numeric"
        }
    );
}


function showToast(message) {

    if (!toast) {
        return;
    }

    toast.textContent = message;

    toast.classList.remove("hidden");

    clearTimeout(
        window.__toastTimer
    );

    window.__toastTimer =
        setTimeout(() => {

            toast.classList.add("hidden");

        }, 2800);
}


function showAuthMessage(
    message,
    type = "error"
) {

    const element =
        document.getElementById(
            "authMessage"
        );

    if (!element) {
        return;
    }

    element.className =
        type === "success"
            ? "auth-success"
            : "auth-error";

    element.textContent =
        message;

    element.style.display =
        "block";
}


function setActivePage(page) {

    document
        .querySelectorAll(".nav-item")
        .forEach(item => {

            item.classList.toggle(
                "active",
                item.dataset.page === page
            );

        });
}


function emptyState(
    icon,
    title,
    description,
    buttonText = "",
    action = ""
) {

    return `
        <div class="empty-card">

            <div class="empty-icon-large">
                ${escapeHTML(icon)}
            </div>

            <h3>
                ${escapeHTML(title)}
            </h3>

            <p>
                ${escapeHTML(description)}
            </p>

            ${
                buttonText
                    ? `
                        <button
                            class="btn primary"
                            data-action="${escapeHTML(action)}"
                        >
                            ${escapeHTML(buttonText)}
                        </button>
                    `
                    : ""
            }

        </div>
    `;
}


/* =========================================================
   SAVED ITEMS
========================================================= */

function savedItems() {

    return readJSON(
        SAVED_KEY,
        []
    );
}


function saveItems(items) {

    localStorage.setItem(
        SAVED_KEY,
        JSON.stringify(items)
    );
}


function isSaved(type, id) {

    return savedItems()
        .includes(`${type}:${id}`);
}


/* =========================================================
   API REQUEST
========================================================= */

async function apiRequest(
    endpoint,
    options = {}
) {

    const config = {
        ...options,

        headers: {
            "Content-Type":
                "application/json",

            ...(options.headers || {})
        }
    };


    if (authToken) {

        config.headers.Authorization =
            `Bearer ${authToken}`;
    }


    let response;


    try {

        response =
            await fetch(
                `${API_BASE}${endpoint}`,
                config
            );

    } catch (error) {

        throw new Error(
            "Cannot connect to EduLink backend. " +
            "Make sure FastAPI is running on port 8000."
        );
    }


    let data = {};


    try {

        data =
            await response.json();

    } catch (error) {

        data = {};
    }


    if (!response.ok) {

        if (response.status === 401) {
            clearAuth(false);
        }

        let message = `Request failed (${response.status})`;

        if (typeof data.detail === "string") {
            message = data.detail;
        } else if (Array.isArray(data.detail)) {
            // FastAPI/Pydantic validation errors (422)
            message = data.detail
                .map(item => {
                    const field = Array.isArray(item.loc)
                        ? item.loc[item.loc.length - 1]
                        : "";
                    const text = item.msg || "Invalid value";
                    return field ? `${field}: ${text}` : text;
                })
                .join("; ");
        } else if (data.detail?.message) {
            message = data.detail.message;
        }

        const error = new Error(message);

        error.status = response.status;
        error.payload = data.detail;
        throw error;
    }


    return data;
}


/* =========================================================
   AUTHENTICATION
========================================================= */

function setAuth(data) {

    authToken =
        data.access_token;

    currentUser =
        data.user;


    localStorage.setItem(
        "edulink_token",
        authToken
    );


    localStorage.setItem(
        "edulink_user",
        JSON.stringify(currentUser)
    );


    updateUserUI();
}


function clearAuth(reload = true) {

    authToken = null;

    currentUser = null;


    localStorage.removeItem(
        "edulink_token"
    );

    localStorage.removeItem(
        "edulink_user"
    );


    updateUserUI();


    if (reload) {

        showLogin(
            "You have been logged out."
        );
    }
}


function logout() {

    clearAuth(true);

    showToast(
        "Logged out successfully."
    );
}


/* =========================================================
   REGISTER
========================================================= */

async function registerUser(
    name,
    email,
    password
) {

    const data =
        await apiRequest(
            "/auth/register",
            {
                method: "POST",

                body: JSON.stringify({
                    full_name: name,
                    email: email,
                    password: password
                })
            }
        );


    setAuth(data);

    return data;
}


/* =========================================================
   LOGIN
========================================================= */

async function loginUser(
    email,
    password
) {

    const data =
        await apiRequest(
            "/auth/login",
            {
                method: "POST",

                body: JSON.stringify({
                    email: email,
                    password: password
                })
            }
        );


    setAuth(data);

    return data;
}


/* =========================================================
   GOOGLE LOGIN
========================================================= */

async function loginWithGoogle(
    credential
) {

    const data =
        await apiRequest(
            "/auth/google",
            {
                method: "POST",

                body: JSON.stringify({
                    credential: credential
                })
            }
        );


    setAuth(data);

    return data;
}


/* =========================================================
   LOGIN REQUIREMENT
========================================================= */

function requireLogin() {

    if (
        !currentUser ||
        !authToken
    ) {

        showLogin(
            "Login or register to continue."
        );

        return false;
    }

    return true;
}


/* =========================================================
   NAVIGATION
========================================================= */

function navigate(page) {

    if (sidebar) {
        sidebar.classList.remove("open");
    }


    if (
        ![
            "dashboard",
            "search",
            "login"
        ].includes(page) &&
        !currentUser
    ) {

        showLogin(
            "Login to use this EduLink feature."
        );

        return;
    }


    setActivePage(page);


    const pages = {

        dashboard:
            showDashboard,

        ask:
            showAsk,

        questions:
            showQuestions,

        search:
            () =>
                showSearchPage(
                    searchInput
                        ? searchInput.value
                        : ""
                ),

        resources:
            showResources,

        procedures:
            showProcedures,

        notices:
            showNotices,

        help:
            showHelp,

        profile:
            showProfile,

        saved:
            showSaved,

        admin:
            showAdmin
    };


    if (pages[page]) {

        pages[page]();

    } else {

        showDashboard();
    }
}


/* =========================================================
   USER UI
========================================================= */

function updateUserUI() {

    const avatar =
        document.getElementById(
            "topAvatar"
        );

    const name =
        document.getElementById(
            "topProfileName"
        );

    const logoutButton =
        document.querySelector(
            ".logout-top"
        );

    const adminNav =
        document.getElementById(
            "adminNav"
        );


    if (avatar) {

        avatar.textContent =
            currentUser
                ? initials(
                    currentUser.full_name ||
                    currentUser.name
                )
                : "G";
    }


    if (name) {

        name.textContent =
            currentUser
                ? (
                    currentUser.full_name ||
                    currentUser.name
                )
                : "Guest";
    }


    if (logoutButton) {

        logoutButton.classList.toggle(
            "hidden",
            !currentUser
        );
    }


    if (adminNav) {

        adminNav.classList.toggle(
            "hidden",
            !currentUser ||
            currentUser.role !== "admin"
        );
    }
}


/* =========================================================
   DASHBOARD
========================================================= */

function showDashboard() {

    const firstName =
        currentUser
            ? escapeHTML(
                (
                    currentUser.full_name ||
                    currentUser.name ||
                    ""
                ).split(" ")[0]
            )
            : "there";


    const questions =
        cachedData.questions;


    content.innerHTML = `

        <div class="welcome-grid">

            <section class="welcome-panel">

                <h1>
                    Welcome
                    ${
                        currentUser
                            ? `, ${firstName}`
                            : ""
                    }
                    👋
                </h1>

                <p>
                    EduLink brings student questions,
                    answers, academic resources and
                    college information into one place.
                </p>

                <div class="action-row">

                    ${
                        currentUser

                            ? `
                                <button
                                    class="btn primary"
                                    data-action="ask-question"
                                >
                                    + Ask a Question
                                </button>
                            `

                            : `
                                <button
                                    class="btn primary"
                                    data-action="login"
                                >
                                    Login / Register
                                </button>
                            `
                    }


                    <button
                        class="btn secondary"
                        data-page="questions"
                    >
                        Browse Questions
                    </button>

                </div>

            </section>


            <section class="quick-links">

                <h3>
                    Explore EduLink
                </h3>


                <button
                    class="quick-link"
                    data-page="resources"
                >
                    <span>Resources</span>
                    <span>→</span>
                </button>


                <button
                    class="quick-link"
                    data-page="procedures"
                >
                    <span>Procedures</span>
                    <span>→</span>
                </button>


                <button
                    class="quick-link"
                    data-page="notices"
                >
                    <span>Notices</span>
                    <span>→</span>
                </button>


                <button
                    class="quick-link"
                    data-page="help"
                >
                    <span>Help Requests</span>
                    <span>→</span>
                </button>

            </section>

        </div>


        <div class="page-header">

            <h1>
                Community Activity
            </h1>

            <p>
                Content appears here only after
                students or college staff add it.
            </p>

        </div>


        ${
            questions.length

                ? renderQuestionList(
                    questions.slice(0, 5)
                )

                : emptyState(
                    "?",
                    "No questions yet",
                    "EduLink has no questions yet. " +
                    "Start the first discussion when you are ready.",
                    currentUser
                        ? "Ask the First Question"
                        : "Login / Register",
                    currentUser
                        ? "ask-question"
                        : "login"
                )
        }

    `;


    updateRightSidebar();
}


/* =========================================================
   LOGIN PAGE
========================================================= */

function showLogin(
    message = ""
) {

    setActivePage("");


    content.innerHTML = `

        <div class="login-screen">

            <div class="auth-card">

                <div class="auth-brand">

                    <div class="brand-mark">
                        E
                    </div>

                    <h1>
                        Welcome to EduLink
                    </h1>

                    <p>
                        ${
                            escapeHTML(
                                message ||
                                "Login or create your student account."
                            )
                        }
                    </p>

                </div>


                <div class="auth-tabs">

                    <button
                        class="auth-tab active"
                        data-auth-tab="login"
                    >
                        Login
                    </button>


                    <button
                        class="auth-tab"
                        data-auth-tab="register"
                    >
                        Register
                    </button>

                </div>


                <div
                    id="authMessage"
                    class="auth-error"
                    style="display:none"
                ></div>


                <form
                    id="authForm"
                    data-auth-mode="login"
                >

                    <div id="authFields"></div>


                    <button
                        class="btn primary"
                        style="width:100%"
                        type="submit"
                    >
                        Login
                    </button>

                </form>


                <div class="auth-note">

                    Secure authentication is handled
                    by the EduLink FastAPI backend.
                    Google Sign-In uses Google's
                    identity service.

                </div>

            </div>

        </div>

    `;


    renderAuthFields("login");
}


/* =========================================================
   AUTH FORM FIELDS
========================================================= */

function renderAuthFields(mode) {

    const fields =
        document.getElementById(
            "authFields"
        );

    const form =
        document.getElementById(
            "authForm"
        );


    if (!fields || !form) {
        return;
    }


    form.dataset.authMode =
        mode;


    const submitButton =
        form.querySelector(
            "button[type=submit]"
        );


    if (submitButton) {

        submitButton.textContent =
            mode === "login"
                ? "Login"
                : "Create Account";
    }


    if (mode === "login") {

        fields.innerHTML = `

            <div class="form-group">

                <label>
                    Email
                </label>

                <input
                    name="email"
                    type="email"
                    required
                    autocomplete="email"
                    placeholder="you@example.com"
                >

            </div>


            <div class="form-group">

                <label>
                    Password
                </label>

                <input
                    name="password"
                    type="password"
                    required
                    autocomplete="current-password"
                    placeholder="Enter password"
                >

            </div>


            <div class="auth-divider">
                <span>or</span>
            </div>


            <div
                class="auth-google-wrap"
                id="googleSignIn"
            ></div>

        `;

    } else {

        fields.innerHTML = `

            <div class="form-group">

                <label>
                    Full name
                </label>

                <input
                    name="name"
                    required
                    autocomplete="name"
                    placeholder="Your full name"
                >

            </div>


            <div class="form-group">

                <label>
                    Email
                </label>

                <input
                    name="email"
                    type="email"
                    required
                    autocomplete="email"
                    placeholder="you@example.com"
                >

            </div>


            <div class="form-group">

                <label>
                    Password
                </label>

                <input
                    name="password"
                    type="password"
                    minlength="6"
                    required
                    autocomplete="new-password"
                    placeholder="Minimum 6 characters"
                >

            </div>


            <div class="auth-divider">
                <span>or</span>
            </div>


            <div
                class="auth-google-wrap"
                id="googleSignIn"
            ></div>

        `;
    }


    initializeGoogleButton();
}


/* =========================================================
   GOOGLE BUTTON
========================================================= */

function initializeGoogleButton() {

    const container =
        document.getElementById(
            "googleSignIn"
        );


    if (!container) {
        return;
    }


    if (
        !window.google ||
        !window.google.accounts ||
        !window.google.accounts.id
    ) {

        setTimeout(
            initializeGoogleButton,
            400
        );

        return;
    }


    container.innerHTML = "";


    google.accounts.id.initialize({

        client_id:
            GOOGLE_CLIENT_ID,

        callback:
            handleGoogleCredential,

        ux_mode:
            "popup"
    });


    google.accounts.id.renderButton(

        container,

        {
            theme: "outline",
            size: "large",
            width: 360,
            text: "continue_with",
            shape: "rectangular"
        }
    );
}


/* =========================================================
   GOOGLE CALLBACK
========================================================= */

async function handleGoogleCredential(
    response
) {

    try {

        showAuthMessage(
            "Signing in with Google...",
            "success"
        );


        await loginWithGoogle(
            response.credential
        );


        showToast(
            "Google login successful."
        );


        await refreshData();


        navigate("dashboard");

    } catch (error) {

        showAuthMessage(
            error.message,
            "error"
        );
    }
}


/* =========================================================
   EMAIL AUTH HANDLER
========================================================= */

async function handleAuth(event) {

    event.preventDefault();


    const form =
        event.target;


    const data =
        new FormData(form);


    const mode =
        form.dataset.authMode;


    const email =
        String(
            data.get("email") || ""
        )
        .trim()
        .toLowerCase();


    const password =
        String(
            data.get("password") || ""
        );


    try {

        if (mode === "register") {

            const name =
                String(
                    data.get("name") || ""
                ).trim();


            if (name.length < 2) {

                throw new Error(
                    "Please enter your full name."
                );
            }


            await registerUser(
                name,
                email,
                password
            );


            showToast(
                "Account created successfully."
            );

        } else {

            await loginUser(
                email,
                password
            );


            showToast(
                "Login successful."
            );
        }


        await refreshData();


        navigate("dashboard");

    } catch (error) {

        showAuthMessage(
            error.message,
            "error"
        );
    }
}


/* =========================================================
   LOAD ALL API DATA
========================================================= */

async function refreshData() {

    const requests = [

        apiRequest(
            "/questions"
        ),

        apiRequest(
            "/resources"
        ),

        apiRequest(
            "/notices"
        ),

        apiRequest(
            "/procedures"
        ),

        apiRequest(
            "/help-requests"
        )
    ];


    const results =
        await Promise.allSettled(
            requests
        );


    cachedData.questions =
        results[0].status === "fulfilled"
            ? results[0].value
            : [];


    cachedData.resources =
        results[1].status === "fulfilled"
            ? results[1].value
            : [];


    cachedData.notices =
        results[2].status === "fulfilled"
            ? results[2].value
            : [];


    cachedData.procedures =
        results[3].status === "fulfilled"
            ? results[3].value
            : [];


    cachedData.helpRequests =
        results[4].status === "fulfilled"
            ? results[4].value
            : [];
}


/* =========================================================
   QUESTION LIST
========================================================= */

function renderQuestionList(
    list
) {

    return list.map(q => `

        <article class="post">

            <div class="vote">

                <button
                    data-action="vote-question"
                    data-id="${q.id}"
                    data-vote="1"
                    title="Helpful"
                >
                    ▲
                </button>


                <b>
                    ${q.votes || 0}
                </b>


                <button
                    data-action="vote-question"
                    data-id="${q.id}"
                    data-vote="-1"
                    title="Vote"
                >
                    ▼
                </button>

            </div>


            <div class="postbody">

                <div class="meta">

                    ${escapeHTML(
                        q.author_name ||
                        "Student"
                    )}

                    ·

                    ${escapeHTML(
                        q.category ||
                        "Other"
                    )}

                </div>


                <h2>
                    ${escapeHTML(q.title)}
                </h2>


                <p>
                    ${escapeHTML(q.body)}
                </p>


                <div class="postactions">

                    <button
                        data-action="open-question"
                        data-id="${q.id}"
                    >
                        ◯
                        ${q.answers || 0}
                        Answers
                    </button>


                    <button
                        data-action="save-question"
                        data-id="${q.id}"
                    >
                        ${
                            isSaved(
                                "question",
                                q.id
                            )
                                ? "★ Saved"
                                : "☆ Save"
                        }
                    </button>

                </div>

            </div>

        </article>

    `).join("");
}


/* =========================================================
   QUESTIONS PAGE
========================================================= */

async function showQuestions() {

    content.innerHTML =
        emptyState(
            "…",
            "Loading questions",
            "Fetching the latest EduLink questions."
        );


    try {

        cachedData.questions =
            await apiRequest(
                "/questions"
            );

    } catch (error) {

        content.innerHTML =
            emptyState(
                "!",
                "Could not load questions",
                error.message
            );

        updateRightSidebar();

        return;
    }


    content.innerHTML = `

        <div class="page-header">

            <div class="header-row">

                <div>

                    <h1>
                        Questions & Answers
                    </h1>

                    <p>
                        Ask, answer and find useful
                        information from the EduLink community.
                    </p>

                </div>


                ${
                    currentUser
                        ? `
                            <button
                                class="btn primary"
                                data-action="ask-question"
                            >
                                + Ask Question
                            </button>
                        `
                        : ""
                }

            </div>

        </div>


        ${
            cachedData.questions.length

                ? renderQuestionList(
                    cachedData.questions
                )

                : emptyState(
                    "?",
                    "No questions yet",
                    "There are no questions in EduLink yet. " +
                    "Once students ask questions, they will appear here.",
                    currentUser
                        ? "Ask the First Question"
                        : "Login / Register",
                    currentUser
                        ? "ask-question"
                        : "login"
                )
        }

    `;


    updateRightSidebar();
}


/* =========================================================
   ASK QUESTION
========================================================= */

function showAsk() {

    if (!requireLogin()) {
        return;
    }

    pendingQuestion = null;

    content.innerHTML = `

        <div class="page-header">
            <h1>Ask the Community</h1>
            <p>
                EduLink checks existing questions before you post
                so useful answers are easier to find.
            </p>
        </div>

        <section class="item">

            <form id="questionForm">

                <div class="form-group">
                    <label>Question title</label>
                    <input
                        name="title"
                        required
                        maxlength="200"
                        placeholder="e.g. How do I apply for a bonafide certificate?"
                    >
                </div>

                <div class="form-group">
                    <label>Tell us more</label>
                    <textarea
                        name="body"
                        required
                        maxlength="5000"
                        placeholder="Add details that will help other students..."
                    ></textarea>
                </div>

                <div class="form-group">
                    <label>Category</label>
                    <select name="category">
                        <option>Academic</option>
                        <option>Examinations</option>
                        <option>Resources</option>
                        <option>Placements</option>
                        <option>Other</option>
                    </select>
                </div>

                <button class="btn primary" type="submit">
                    Check & Post Question
                </button>

            </form>

            <div id="similarQuestionPanel"></div>

        </section>
    `;

    const form = document.getElementById("questionForm");

    form.addEventListener("submit", async event => {
        event.preventDefault();

        const data = new FormData(event.currentTarget);
        const payload = {
            title: String(data.get("title") || "").trim(),
            body: String(data.get("body") || "").trim(),
            category: String(data.get("category") || "Other").trim()
        };

        try {
            const result = await apiRequest(
                "/questions/similar",
                {
                    method: "POST",
                    body: JSON.stringify(payload)
                }
            );

            if (result.matches?.length) {
                pendingQuestion = payload;
                renderSimilarQuestionPanel(
                    result.matches,
                    result.duplicate_threshold
                );
                return;
            }

            await createQuestion(payload, false);
        } catch (error) {
            showToast(error.message);
        }
    });
}


function renderSimilarQuestionPanel(matches, duplicateThreshold = 0.72) {

    const panel = document.getElementById("similarQuestionPanel");

    if (!panel) {
        return;
    }

    const duplicateCount = matches.filter(
        item => item.similarity >= duplicateThreshold
    ).length;

    panel.innerHTML = `

        <div class="smart-match-panel">

            <div class="smart-match-header">
                <div>
                    <span class="smart-eyebrow">EDULINK SMART CHECK</span>
                    <h3>
                        ${
                            duplicateCount
                                ? "Possible duplicate questions found"
                                : "Similar questions found"
                        }
                    </h3>
                    <p>
                        Review these existing discussions before posting.
                    </p>
                </div>
            </div>

            <div class="smart-match-list">

                ${matches.map(match => `

                    <div class="smart-match">

                        <div class="smart-match-score">
                            ${match.similarity_percent}%
                        </div>

                        <div class="smart-match-content">
                            <strong>
                                ${escapeHTML(match.title)}
                            </strong>

                            <p>
                                ${escapeHTML(
                                    (match.body || "").slice(0, 180)
                                )}${
                                    (match.body || "").length > 180
                                        ? "…"
                                        : ""
                                }
                            </p>

                            <span class="item-meta">
                                ${escapeHTML(match.category || "General")}
                                ·
                                ${
                                    match.possible_duplicate
                                        ? "Possible duplicate"
                                        : "Similar discussion"
                                }
                            </span>
                        </div>

                        <button
                            class="btn secondary small"
                            data-action="open-question"
                            data-id="${match.id}"
                        >
                            View
                        </button>

                    </div>

                `).join("")}

            </div>

            <div class="smart-match-actions">
                <button
                    class="btn secondary"
                    data-action="cancel-pending-question"
                >
                    Go Back
                </button>

                <button
                    class="btn primary"
                    data-action="continue-question"
                >
                    Continue Anyway
                </button>
            </div>

        </div>
    `;
}


async function createQuestion(payload, forceCreate = false) {

    await apiRequest(
        "/questions",
        {
            method: "POST",
            body: JSON.stringify({
                ...payload,
                force_create: forceCreate
            })
        }
    );

    pendingQuestion = null;

    showToast("Question posted successfully.");

    await refreshData();
    navigate("questions");
}


async function continuePendingQuestion() {

    if (!pendingQuestion) {
        showToast("No pending question.");
        return;
    }

    try {
        await createQuestion(pendingQuestion, true);
    } catch (error) {
        showToast(error.message);
    }
}


/* =========================================================
   QUESTION DETAILS
========================================================= */

async function showQuestionDetails(
    id
) {

    const questionId =
        Number(id);


    if (!Number.isInteger(questionId)) {

        showToast(
            "Invalid question."
        );

        return;
    }


    try {

        const q =
            await apiRequest(
                `/questions/${Number(questionId)}`
            );


        const answers =
            await apiRequest(
                `/questions/${Number(questionId)}/answers`
            );

        const similarResponse =
            await apiRequest(
                `/questions/${Number(questionId)}/similar`
            );

        const similarQuestions =
            similarResponse.matches || [];


        content.innerHTML = `

            <div class="page-header">

                <button
                    class="btn secondary small"
                    data-page="questions"
                >
                    ← Back to Questions
                </button>

            </div>


            <article class="item">

                <h1
                    style="
                        font-size:22px;
                        margin-bottom:10px
                    "
                >
                    ${escapeHTML(q.title)}
                </h1>


                <p>
                    ${escapeHTML(q.body)}
                </p>


                <div class="item-meta">

                    Asked by
                    ${escapeHTML(
                        q.author_name ||
                        "Student"
                    )}

                    ·

                    ${escapeHTML(
                        q.category ||
                        "Other"
                    )}

                </div>


                <div class="item-actions">

                    <div class="vote-box">

                        <button
                            class="vote-btn"
                            data-action="vote-question"
                            data-id="${q.id}"
                            data-vote="1"
                        >
                            ▲
                        </button>


                        <span>
                            ${q.votes || 0}
                        </span>


                        <button
                            class="vote-btn"
                            data-action="vote-question"
                            data-id="${q.id}"
                            data-vote="-1"
                        >
                            ▼
                        </button>

                    </div>


                    <button
                        class="btn secondary small"
                        data-action="save-question"
                        data-id="${q.id}"
                    >
                        ${
                            isSaved(
                                "question",
                                q.id
                            )
                                ? "★ Saved"
                                : "☆ Save"
                        }
                    </button>

                </div>

            </article>


            ${
                similarQuestions.length
                    ? `
                        <section class="smart-related">

                            <div class="page-header compact">
                                <h2>Similar Questions</h2>
                                <p>
                                    Existing discussions that may already answer this question.
                                </p>
                            </div>

                            ${similarQuestions.map(item => `
                                <article class="smart-related-item">

                                    <div>
                                        <strong>
                                            ${escapeHTML(item.title)}
                                        </strong>

                                        <p>
                                            ${escapeHTML(
                                                (item.body || "").slice(0, 160)
                                            )}${
                                                (item.body || "").length > 160
                                                    ? "…"
                                                    : ""
                                            }
                                        </p>
                                    </div>

                                    <div class="smart-related-actions">
                                        <span>${item.similarity_percent}% similar</span>
                                        <button
                                            class="btn secondary small"
                                            data-action="open-question"
                                            data-id="${item.id}"
                                        >
                                            View
                                        </button>
                                    </div>

                                </article>
                            `).join("")}

                        </section>
                    `
                    : ""
            }


            <div class="page-header">

                <div class="header-row">

                    <div>

                        <h1>
                            Answers
                        </h1>

                        <p>
                            ${answers.length}
                            answer
                            ${
                                answers.length === 1
                                    ? ""
                                    : "s"
                            }
                        </p>

                        ${
                            answers.length
                                ? `
                                    <span class="smart-answer-note">
                                        Answers are ranked by helpful votes, verification and recency.
                                    </span>
                                `
                                : ""
                        }

                    </div>


                    ${
                        currentUser

                            ? `
                                <button
                                    class="btn primary"
                                    data-action="answer-question"
                                    data-id="${q.id}"
                                >
                                    + Write Answer
                                </button>
                            `

                            : ""
                    }

                </div>

            </div>


            ${
                answers.length

                    ? answers.map(a => `

                        <article class="item">

                            <div
                                class="
                                    answer
                                    ${
                                        a.faculty_verified
                                            ? "verified"
                                            : ""
                                    }
                                "
                            >

                                <div class="answer-head">

                                    <strong>
                                        ${escapeHTML(
                                            a.author_name ||
                                            "Student"
                                        )}
                                    </strong>


                                    ${
                                        a.faculty_verified

                                            ? `
                                                <span
                                                    class="verified-label"
                                                >
                                                    ✓ Faculty Verified
                                                </span>
                                            `

                                            : ""
                                    }

                                </div>


                                <p>
                                    ${escapeHTML(
                                        a.body
                                    )}
                                </p>


                                <div class="item-meta">

                                    Helpful votes:
                                    ${a.helpful_votes || 0}

                                </div>


                                <div class="item-actions">

                                    ${
                                        currentUser

                                            ? `
                                                <button
                                                    class="vote-btn"
                                                    data-action="vote-answer"
                                                    data-id="${a.id}"
                                                    data-question="${q.id}"
                                                >
                                                    ▲ Helpful
                                                </button>
                                            `

                                            : ""
                                    }

                                </div>

                            </div>

                        </article>

                    `).join("")

                    : (
                        currentUser

                            ? emptyState(
                                "✓",
                                "No answers yet",
                                "Be the first student to answer this question.",
                                "Write the First Answer",
                                "answer-question"
                            )

                            : emptyState(
                                "✓",
                                "No answers yet",
                                "Be the first student to answer this question."
                            )
                    )
            }

        `;


    } catch (error) {

        content.innerHTML =
            emptyState(
                "!",
                "Question unavailable",
                error.message,
                "Back to Questions",
                "questions"
            );
    }
}


/* =========================================================
   SEARCH
========================================================= */

function showSearchPage(
    query = ""
) {

    const term =
        query.trim().toLowerCase();


    const all = [

        ...cachedData.questions.map(
            item => ({
                type: "Question",
                title: item.title,
                description: item.body,
                id: item.id
            })
        ),


        ...cachedData.resources.map(
            item => ({
                type: "Resource",
                title: item.title,
                description: item.description,
                id: item.id
            })
        ),


        ...cachedData.notices.map(
            item => ({
                type: "Notice",
                title: item.title,
                description: item.body,
                id: item.id
            })
        ),


        ...cachedData.helpRequests.map(
            item => ({
                type: "Help Request",
                title: item.title,
                description: item.description,
                id: item.id
            })
        )

    ];


    const results =
        term

            ? all.filter(item =>
                `${item.title} ${
                    item.description || ""
                }`
                .toLowerCase()
                .includes(term)
            )

            : [];


    let body;


    if (!term) {

        body =
            emptyState(
                "⌕",
                "Start searching",
                "Enter a keyword in the search bar above."
            );

    } else if (!results.length) {

        body =
            emptyState(
                "⌕",
                "No results found",
                "Try another search term."
            );

    } else {

        body =
            results.map(item => `

                <article class="item">

                    <div class="item-meta">
                        ${escapeHTML(item.type)}
                    </div>

                    <h3>
                        ${escapeHTML(item.title)}
                    </h3>

                    <p>
                        ${escapeHTML(
                            item.description || ""
                        )}
                    </p>

                </article>

            `).join("");
    }


    content.innerHTML = `

        <div class="page-header">

            <h1>
                Search
            </h1>

            <p>
                Search across questions,
                resources, notices and help requests.
            </p>

        </div>


        ${body}

    `;
}


/* =========================================================
   RESOURCES
========================================================= */

async function showResources() {

    try {

        cachedData.resources =
            await apiRequest(
                "/resources"
            );

    } catch (error) {

        content.innerHTML =
            emptyState(
                "!",
                "Could not load resources",
                error.message
            );

        return;
    }


    content.innerHTML = `

        <div class="page-header">

            <div class="header-row">

                <div>

                    <h1>
                        Resources
                    </h1>

                    <p>
                        Notes, study materials,
                        question papers and useful
                        academic resources.
                    </p>

                </div>


                ${
                    currentUser
                        ? `
                            <button
                                class="btn primary"
                                data-action="add-resource"
                            >
                                + Share Resource
                            </button>
                        `
                        : ""
                }

            </div>

        </div>


        ${
            cachedData.resources.length

                ? cachedData.resources.map(r => `

                    <article class="item">

                        <h3>
                            ${escapeHTML(r.title)}
                        </h3>


                        <p>
                            ${escapeHTML(
                                r.description
                            )}
                        </p>


                        ${
                            r.url

                                ? `
                                    <div class="item-meta">

                                        Link:

                                        <a
                                            href="${escapeHTML(r.url)}"
                                            target="_blank"
                                            rel="noopener noreferrer"
                                        >
                                            ${escapeHTML(r.url)}
                                        </a>

                                    </div>
                                `

                                : ""
                        }


                        <div class="item-meta">

                            Shared by
                            ${escapeHTML(
                                r.author_name ||
                                "Student"
                            )}

                        </div>

                    </article>

                `).join("")

                : emptyState(
                    "▣",
                    "No resources yet",
                    "Resources appear after students share useful material.",
                    currentUser
                        ? "Share the First Resource"
                        : "Login / Register",
                    currentUser
                        ? "add-resource"
                        : "login"
                )
        }

    `;
}


/* =========================================================
   NOTICES
========================================================= */

async function showNotices() {

    try {

        cachedData.notices =
            await apiRequest(
                "/notices"
            );

    } catch (error) {

        content.innerHTML =
            emptyState(
                "!",
                "Could not load notices",
                error.message
            );

        return;
    }


    content.innerHTML = `

        <div class="page-header">

            <h1>
                Notices
            </h1>

            <p>
                Official college announcements
                and important information.
            </p>

        </div>


        ${
            cachedData.notices.length

                ? cachedData.notices.map(
                    notice => `

                        <article class="item">

                            <h3>
                                ${escapeHTML(
                                    notice.title
                                )}
                            </h3>


                            <p>
                                ${escapeHTML(
                                    notice.body
                                )}
                            </p>


                            <div class="item-meta">

                                ${escapeHTML(
                                    notice.author_name ||
                                    "College Administration"
                                )}

                            </div>

                        </article>

                    `
                ).join("")

                : emptyState(
                    "▤",
                    "No notices yet",
                    "Official notices will appear here when they are published."
                )
        }

    `;
}


/* =========================================================
   PROCEDURES
========================================================= */

async function showProcedures() {

    content.innerHTML = emptyState(
        "…",
        "Loading procedures",
        "Fetching verified college procedures."
    );

    try {
        cachedData.procedures = await apiRequest("/procedures");
    } catch (error) {
        content.innerHTML = emptyState(
            "!",
            "Could not load procedures",
            error.message
        );
        return;
    }

    content.innerHTML = `

        <div class="page-header">
            <h1>Procedures</h1>
            <p>
                College processes and verified instructions.
            </p>
        </div>

        ${
            cachedData.procedures.length
                ? cachedData.procedures.map(item => `
                    <article class="item">

                        <div class="item-meta">
                            ${
                                item.verified
                                    ? "✓ Verified procedure"
                                    : "Procedure"
                            }
                            ·
                            ${escapeHTML(item.creator_name || "College Administration")}
                        </div>

                        <h3>${escapeHTML(item.title)}</h3>

                        <p>${escapeHTML(item.description)}</p>

                        <details class="procedure-details">
                            <summary>View procedure</summary>
                            <p>${escapeHTML(item.content)}</p>
                        </details>

                    </article>
                `).join("")
                : emptyState(
                    "☷",
                    "No procedures yet",
                    "Verified college procedures will appear here when they are added."
                )
        }
    `;
}


/* =========================================================
   HELP REQUESTS
========================================================= */

async function showHelp() {

    if (!requireLogin()) {
        return;
    }

    try {
        cachedData.helpRequests =
            await apiRequest("/help-requests");
    } catch (error) {
        content.innerHTML = emptyState(
            "!",
            "Could not load help requests",
            error.message
        );
        return;
    }

    content.innerHTML = `

        <div class="page-header">

            <div class="header-row">

                <div>
                    <h1>Help Requests</h1>
                    <p>
                        Ask other students for help or offer help when you can.
                    </p>
                </div>

                <button
                    class="btn primary"
                    data-action="create-help"
                >
                    + Ask for Help
                </button>

            </div>

        </div>

        ${
            cachedData.helpRequests.length
                ? cachedData.helpRequests.map(item => `
                    <article class="item">

                        <div class="item-meta">
                            ${escapeHTML(item.category || "General")}
                            ·
                            ${escapeHTML(item.status || "open")}
                        </div>

                        <h3>${escapeHTML(item.title)}</h3>

                        <p>${escapeHTML(item.description)}</p>

                        <div class="item-meta">
                            Requested by
                            ${escapeHTML(item.author_name || "Student")}
                            ·
                            ${item.helpers || 0}
                            helper${item.helpers === 1 ? "" : "s"}
                        </div>

                        <div class="item-actions">

                            ${
                                item.author_id !== currentUser.id
                                    ? `
                                        <button
                                            class="btn secondary small"
                                            data-action="offer-help"
                                            data-id="${item.id}"
                                        >
                                            🤝 Offer Help
                                        </button>
                                    `
                                    : ""
                            }

                            ${
                                item.author_id === currentUser.id ||
                                currentUser.role === "faculty" ||
                                currentUser.role === "admin"
                                    ? `
                                        <button
                                            class="btn secondary small"
                                            data-action="toggle-help-status"
                                            data-id="${item.id}"
                                            data-status="${
                                                item.status === "open"
                                                    ? "resolved"
                                                    : "open"
                                            }"
                                        >
                                            ${
                                                item.status === "open"
                                                    ? "Mark Resolved"
                                                    : "Reopen"
                                            }
                                        </button>
                                    `
                                    : ""
                            }

                        </div>

                    </article>
                `).join("")
                : emptyState(
                    "♧",
                    "No help requests yet",
                    "Nobody has requested help yet. You can be the first.",
                    "Create a Help Request",
                    "create-help"
                )
        }
    `;
}


/* =========================================================
   PROFILE
========================================================= */

async function showProfile() {

    if (!requireLogin()) {
        return;
    }


    /*
       Refresh data so profile statistics
       reflect the latest backend data.
    */

    try {

        await refreshData();

    } catch (error) {

        console.error(
            "Profile refresh error:",
            error
        );
    }


    const questionCount =
        cachedData.questions.filter(
            item =>
                item.author_id ===
                currentUser.id
        ).length;


    const resourceCount =
        cachedData.resources.filter(
            item =>
                item.author_id ===
                currentUser.id
        ).length;


    const helpCount =
        cachedData.helpRequests.filter(
            item =>
                item.author_id ===
                currentUser.id
        ).length;


    const userName =
        currentUser.full_name ||
        currentUser.name ||
        "Student";


    content.innerHTML = `

        <div class="page-header">

            <h1>
                Profile
            </h1>

            <p>
                Your EduLink account
                and contribution activity.
            </p>

        </div>


        <section class="profile-card">

            <div class="profile-big">

                <div class="profile-avatar">

                    ${escapeHTML(
                        initials(userName)
                    )}

                </div>


                <div class="profile-details">

                    <h2>
                        ${escapeHTML(userName)}
                    </h2>


                    <p>
                        ${escapeHTML(
                            currentUser.email
                        )}
                    </p>


                    <p>
                        Role:
                        ${escapeHTML(
                            currentUser.role
                        )}
                    </p>

                </div>

            </div>


            <div class="profile-stats">

                <div class="profile-stat">

                    <strong>
                        ${questionCount}
                    </strong>

                    <span>
                        Questions
                    </span>

                </div>


                <div class="profile-stat">

                    <strong>
                        ${resourceCount}
                    </strong>

                    <span>
                        Resources
                    </span>

                </div>


                <div class="profile-stat">

                    <strong>
                        ${helpCount}
                    </strong>

                    <span>
                        Help Requests
                    </span>

                </div>

            </div>


            <div class="action-row">

                <button
                    class="btn danger"
                    data-action="logout"
                >
                    Logout
                </button>

            </div>

        </section>

    `;
}


/* =========================================================
   SAVED ITEMS
========================================================= */

function showSaved() {

    if (!requireLogin()) {
        return;
    }


    const keys =
        savedItems();


    const questions =
        cachedData.questions.filter(
            item =>
                keys.includes(
                    `question:${item.id}`
                )
        );


    const resources =
        cachedData.resources.filter(
            item =>
                keys.includes(
                    `resource:${item.id}`
                )
        );


    const items = [

        ...questions.map(item => `

            <article class="item">

                <div class="item-meta">
                    Question
                </div>

                <h3>
                    ${escapeHTML(item.title)}
                </h3>

                <p>
                    ${escapeHTML(item.body)}
                </p>


                <button
                    class="btn secondary small"
                    data-action="open-question"
                    data-id="${item.id}"
                >
                    Open Question
                </button>

            </article>

        `),


        ...resources.map(item => `

            <article class="item">

                <div class="item-meta">
                    Resource
                </div>

                <h3>
                    ${escapeHTML(item.title)}
                </h3>

                <p>
                    ${escapeHTML(item.description)}
                </p>

            </article>

        `)

    ].join("");


    content.innerHTML = `

        <div class="page-header">

            <h1>
                Saved Items
            </h1>

            <p>
                Useful questions and resources
                saved for later.
            </p>

        </div>


        ${
            items ||

            emptyState(
                "☆",
                "Nothing saved yet",
                "Save useful questions or resources and they will appear here."
            )
        }

    `;
}


/* =========================================================
   ADMIN
========================================================= */

async function showAdmin() {

    if (
        !currentUser ||
        currentUser.role !== "admin"
    ) {

        showToast(
            "Admin access required."
        );

        navigate("dashboard");

        return;
    }


    try {

        const stats =
            await apiRequest(
                "/admin/stats"
            );


        const users =
            await apiRequest(
                "/admin/users"
            );


        content.innerHTML = `

            <div class="page-header">

                <h1>
                    Admin Dashboard
                </h1>

                <p>
                    Manage EduLink users
                    and content.
                </p>

            </div>


            <div class="admin-grid">

                ${adminStat(
                    "Users",
                    stats.users
                )}

                ${adminStat(
                    "Questions",
                    stats.questions
                )}

                ${adminStat(
                    "Answers",
                    stats.answers
                )}

                ${adminStat(
                    "Resources",
                    stats.resources
                )}

            </div>


            ${
                users.length

                    ? users.map(user => `

                        <article class="item">

                            <h3>
                                ${escapeHTML(
                                    user.full_name
                                )}
                            </h3>


                            <p>
                                ${escapeHTML(
                                    user.email
                                )}
                            </p>


                            <div class="item-meta">

                                Role:
                                ${escapeHTML(
                                    user.role
                                )}

                            </div>

                        </article>

                    `).join("")

                    : emptyState(
                        "◎",
                        "No users yet",
                        "Registered users appear here after accounts are created."
                    )
            }

        `;


    } catch (error) {

        content.innerHTML =
            emptyState(
                "!",
                "Admin data unavailable",
                error.message
            );
    }
}


function adminStat(
    label,
    value
) {

    return `

        <div class="admin-stat">

            <span>
                ${escapeHTML(label)}
            </span>

            <strong>
                ${Number(value) || 0}
            </strong>

        </div>

    `;
}


/* =========================================================
   MODAL
========================================================= */

function openModal(
    title,
    type
) {

    if (!requireLogin()) {
        return;
    }


    modalTitle.textContent =
        title;


    modalForm.dataset.type =
        type;


    modalFields.innerHTML =
        getModalFields(type);


    modalOverlay.classList.remove(
        "hidden"
    );


    const first =
        modalFields.querySelector(
            "input, textarea"
        );


    if (first) {

        setTimeout(
            () => first.focus(),
            50
        );
    }
}


function getModalFields(type) {

    if (type === "answer") {

        return `

            <div class="form-group">

                <label>
                    Your answer
                </label>

                <textarea
                    name="body"
                    required
                    placeholder="Write a useful answer..."
                ></textarea>

            </div>

        `;
    }


    if (type === "resource") {

        return `

            <div class="form-group">

                <label>
                    Resource title
                </label>

                <input
                    name="title"
                    required
                    maxlength="200"
                    placeholder="e.g. Data Structures Notes"
                >

            </div>


            <div class="form-group">

                <label>
                    Description
                </label>

                <textarea
                    name="description"
                    required
                    maxlength="5000"
                    placeholder="Describe this resource..."
                ></textarea>

            </div>


            <div class="form-group">

                <label>
                    Resource link
                    (optional)
                </label>

                <input
                    name="url"
                    type="url"
                    placeholder="https://..."
                >

            </div>

        `;
    }


    if (type === "help") {

        return `

            <div class="form-group">

                <label>
                    Help request title
                </label>

                <input
                    name="title"
                    required
                    maxlength="200"
                    placeholder="What help do you need?"
                >

            </div>


            <div class="form-group">

                <label>
                    Description
                </label>

                <textarea
                    name="description"
                    required
                    maxlength="5000"
                    placeholder="Explain what you need help with..."
                ></textarea>

            </div>


            <div class="form-group">

                <label>
                    Category
                </label>

                <input
                    name="category"
                    value="General"
                    placeholder="Academic, project, college..."
                >

            </div>

        `;
    }


    return `

        <div class="form-group">

            <label>
                Title
            </label>

            <input
                name="title"
                required
            >

        </div>


        <div class="form-group">

            <label>
                Description
            </label>

            <textarea
                name="description"
                required
            ></textarea>

        </div>

    `;
}


function closeModal() {

    modalOverlay.classList.add(
        "hidden"
    );


    modalForm.reset();


    modalForm.dataset.type =
        "";


    modalForm.dataset.questionId =
        "";
}


/* =========================================================
   MODAL SUBMIT
========================================================= */

if (modalForm) {

    modalForm.addEventListener(
        "submit",
        async event => {

            event.preventDefault();


            const data =
                new FormData(
                    modalForm
                );


            const type =
                modalForm.dataset.type;


            try {

                /* ANSWER */

                if (type === "answer") {

                    const questionId =
                        Number(
                            modalForm.dataset.questionId
                        );


                    if (
                        !Number.isInteger(
                            questionId
                        )
                    ) {

                        throw new Error(
                            "Invalid question."
                        );
                    }


                    await apiRequest(
                        `/questions/${Number(questionId)}/answers`,
                        {
                            method: "POST",

                            body: JSON.stringify({
                                body:
                                    String(
                                        data.get("body") ||
                                        ""
                                    ).trim()
                            })
                        }
                    );


                    closeModal();


                    showToast(
                        "Answer posted successfully."
                    );


                    await showQuestionDetails(
                        questionId
                    );


                    return;
                }


                /* RESOURCE */

                if (type === "resource") {

                    await apiRequest(
                        "/resources",
                        {
                            method: "POST",

                            body: JSON.stringify({

                                title:
                                    String(
                                        data.get("title") ||
                                        ""
                                    ).trim(),

                                description:
                                    String(
                                        data.get("description") ||
                                        ""
                                    ).trim(),

                                category:
                                    "Academic",

                                url:
                                    String(
                                        data.get("url") ||
                                        ""
                                    ).trim() ||
                                    null
                            })
                        }
                    );


                    closeModal();


                    showToast(
                        "Resource shared successfully."
                    );


                    await showResources();


                    return;
                }


                /* HELP REQUEST */

                if (type === "help") {

                    await apiRequest(
                        "/help-requests",
                        {
                            method: "POST",

                            body: JSON.stringify({

                                title:
                                    String(
                                        data.get("title") ||
                                        ""
                                    ).trim(),

                                description:
                                    String(
                                        data.get("description") ||
                                        ""
                                    ).trim(),

                                category:
                                    String(
                                        data.get("category") ||
                                        "General"
                                    ).trim() ||
                                    "General"
                            })
                        }
                    );


                    closeModal();


                    showToast(
                        "Help request created successfully."
                    );


                    await showHelp();


                    return;
                }

            } catch (error) {

                showToast(
                    error.message
                );
            }

        }
    );
}


/* =========================================================
   QUESTION VOTING
========================================================= */

async function voteQuestion(
    id,
    value = 1
) {

    if (!requireLogin()) {
        return;
    }


    const questionId =
        Number(id);


    if (
        !Number.isInteger(
            questionId
        )
    ) {

        showToast(
            "Invalid question."
        );

        return;
    }


    try {

        /*
          Backend currently uses a toggle vote.
          The value is kept for frontend compatibility.
        */

        await apiRequest(
            `/questions/${Number(questionId)}/vote`,
            {
                method: "POST"
            }
        );


        showToast(
            "Question vote updated."
        );


        await refreshData();


        /*
          If currently viewing question details,
          refresh that page instead of returning
          to the questions list.
        */

        const detailsButton =
            document.querySelector(
                `[data-action="open-question"][data-id="${questionId}"]`
            );


        if (detailsButton) {

            await showQuestions();

        } else {

            await showQuestionDetails(
                questionId
            );
        }

    } catch (error) {

        showToast(
            error.message
        );
    }
}


/* =========================================================
   ANSWER HELPFUL VOTE
========================================================= */

async function voteAnswer(
    questionId,
    answerId
) {

    if (!requireLogin()) {
        return;
    }


    try {

        await apiRequest(
            `/questions/answers/${Number(answerId)}/helpful`,
            {
                method: "POST"
            }
        );


        showToast(
            "Helpful vote updated."
        );


        await showQuestionDetails(
            Number(questionId)
        );

    } catch (error) {

        showToast(
            error.message
        );
    }
}


/* =========================================================
   SAVE / UNSAVE
========================================================= */

function toggleSave(
    type,
    id
) {

    if (!requireLogin()) {
        return;
    }


    const key =
        `${type}:${id}`;


    const items =
        savedItems();


    const index =
        items.indexOf(key);


    if (index >= 0) {

        items.splice(
            index,
            1
        );


        showToast(
            "Removed from saved items."
        );

    } else {

        items.push(key);


        showToast(
            "Saved for later."
        );
    }


    saveItems(items);


    if (type === "question") {

        /*
          Stay on question details if currently
          viewing a question.
        */

        const questionHeading =
            document.querySelector(
                ".item h1"
            );


        if (questionHeading) {

            showQuestionDetails(
                Number(id)
            );

        } else {

            showQuestions();
        }
    }
}


/* =========================================================
   ANSWER QUESTION
========================================================= */

function answerQuestion(
    id
) {

    if (!requireLogin()) {
        return;
    }


    const questionId =
        Number(id);


    if (
        !Number.isInteger(
            questionId
        )
    ) {

        showToast(
            "Please open a question before answering."
        );

        return;
    }


    modalForm.dataset.questionId =
        questionId;


    openModal(
        "Write an Answer",
        "answer"
    );


    /*
      openModal resets only the type,
      so restore question ID afterwards.
    */

    modalForm.dataset.questionId =
        questionId;
}


async function offerHelp(requestId) {

    if (!requireLogin()) {
        return;
    }

    try {
        const result = await apiRequest(
            `/help-requests/${Number(requestId)}/offer`,
            { method: "POST" }
        );

        showToast(result.message || "Help offer updated.");
        await showHelp();
    } catch (error) {
        showToast(error.message);
    }
}


async function toggleHelpStatus(requestId, status) {

    if (!requireLogin()) {
        return;
    }

    try {
        await apiRequest(
            `/help-requests/${Number(requestId)}`,
            {
                method: "PUT",
                body: JSON.stringify({ status })
            }
        );

        showToast(
            status === "resolved"
                ? "Help request marked resolved."
                : "Help request reopened."
        );

        await showHelp();
    } catch (error) {
        showToast(error.message);
    }
}


/* =========================================================
   RIGHT SIDEBAR
========================================================= */

function updateRightSidebar() {

    const events =
        document.getElementById(
            "todayEvents"
        );


    const trending =
        document.getElementById(
            "trendingTopics"
        );


    const popular =
        document.getElementById(
            "popularContent"
        );


    if (events) {

        events.innerHTML = `

            <div class="empty-icon">
                ◷
            </div>

            <strong>
                No college events yet
            </strong>

            <p>
                Official events will appear here
                when added.
            </p>

        `;
    }


    if (trending) {

        const categories =
            [
                ...new Set(
                    cachedData.questions
                        .map(
                            item =>
                                item.category
                        )
                        .filter(Boolean)
                )
            ]
            .slice(0, 5);


        trending.innerHTML =
            categories.length

                ? categories.map(
                    category => `

                        <p
                            style="
                                margin:7px 0
                            "
                        >
                            #
                            ${escapeHTML(
                                category
                            )}
                        </p>

                    `
                ).join("")

                : `

                    <div class="empty-icon">
                        ⌁
                    </div>

                    <strong>
                        No trends yet
                    </strong>

                    <p>
                        Topics will emerge as
                        students contribute.
                    </p>

                `;
    }


    if (popular) {

        const count =
            cachedData.questions.length +
            cachedData.resources.length +
            cachedData.helpRequests.length;


        popular.innerHTML =
            count

                ? `

                    <strong>
                        ${count}
                        contribution
                        ${
                            count === 1
                                ? ""
                                : "s"
                        }
                    </strong>

                    <p>
                        EduLink is starting to grow.
                    </p>

                `

                : `

                    <div class="empty-icon">
                        ☆
                    </div>

                    <strong>
                        It's quiet here
                    </strong>

                    <p>
                        Useful content will appear
                        as students contribute.
                    </p>

                `;
    }
}


/* =========================================================
   COMMUNITY SIDEBAR
========================================================= */

function updateCommunitySidebar() {

    const communityList =
        document.getElementById(
            "communityList"
        );


    if (!communityList) {
        return;
    }


    communityList.innerHTML = `

        <div class="sidebar-empty">

            <div class="mini-empty-icon">
                ○
            </div>

            <p>
                No communities yet
            </p>

            <button
                class="text-button"
                data-action="create-community"
            >
                Communities will be added later
            </button>

        </div>

    `;
}


/* =========================================================
   GLOBAL CLICK HANDLER
========================================================= */

document.addEventListener(
    "click",
    event => {

        /* PAGE NAVIGATION */

        const page =
            event.target.closest(
                "[data-page]"
            );


        if (page) {

            navigate(
                page.dataset.page
            );

            return;
        }


        /* AUTH TABS */

        const tab =
            event.target.closest(
                "[data-auth-tab]"
            );


        if (tab) {

            document
                .querySelectorAll(
                    ".auth-tab"
                )
                .forEach(item =>
                    item.classList.remove(
                        "active"
                    )
                );


            tab.classList.add(
                "active"
            );


            renderAuthFields(
                tab.dataset.authTab
            );


            return;
        }


        /* ACTION BUTTONS */

        const action =
            event.target.closest(
                "[data-action]"
            );


        if (!action) {
            return;
        }


        const type =
            action.dataset.action;


        const id =
            action.dataset.id;


        if (type === "login") {

            showLogin();

        }


        else if (type === "logout") {

            logout();

        }


        else if (
            type === "ask-question"
        ) {

            showAsk();

        }


        else if (
            type === "open-question"
        ) {

            showQuestionDetails(
                id
            );

        }


        else if (
            type === "answer-question"
        ) {

            answerQuestion(
                id
            );

        }


        else if (
            type === "vote-question"
        ) {

            voteQuestion(
                id,
                action.dataset.vote
            );

        }


        else if (
            type === "vote-answer"
        ) {

            voteAnswer(
                action.dataset.question,
                id
            );

        }


        else if (
            type === "save-question"
        ) {

            toggleSave(
                "question",
                id
            );

        }


        else if (
            type === "add-resource"
        ) {

            openModal(
                "Share a Resource",
                "resource"
            );

        }


        else if (
            type === "create-help"
        ) {

            openModal(
                "Ask for Help",
                "help"
            );

        }


        else if (
            type === "continue-question"
        ) {

            continuePendingQuestion();

        }


        else if (
            type === "cancel-pending-question"
        ) {

            pendingQuestion = null;
            showAsk();

        }


        else if (
            type === "offer-help"
        ) {

            offerHelp(id);

        }


        else if (
            type === "toggle-help-status"
        ) {

            toggleHelpStatus(
                id,
                action.dataset.status
            );

        }


        else if (
            type === "create-community"
        ) {

            showToast(
                "Communities will be added when real college community data is available."
            );
        }

    }
);


/* =========================================================
   AUTH FORM SUBMIT
========================================================= */

document.addEventListener(
    "submit",
    event => {

        if (
            event.target.id ===
            "authForm"
        ) {

            handleAuth(event);
        }

    }
);


/* =========================================================
   SEARCH INPUT
========================================================= */

if (searchInput) {

    searchInput.addEventListener(
        "input",
        () => {

            const value =
                searchInput.value.trim();


            if (value) {

                showSearchPage(
                    value
                );
            }

        }
    );


    searchInput.addEventListener(
        "keydown",
        event => {

            if (
                event.key ===
                "Enter"
            ) {

                event.preventDefault();


                showSearchPage(
                    searchInput.value
                );
            }

        }
    );
}


/* =========================================================
   CTRL + K SEARCH
========================================================= */

document.addEventListener(
    "keydown",
    event => {

        if (
            (event.ctrlKey ||
                event.metaKey) &&
            event.key.toLowerCase() ===
                "k"
        ) {

            event.preventDefault();


            if (searchInput) {

                searchInput.focus();
            }
        }

    }
);


/* =========================================================
   MOBILE MENU
========================================================= */

const mobileMenu =
    document.getElementById(
        "mobileMenu"
    );


if (mobileMenu) {

    mobileMenu.addEventListener(
        "click",
        () => {

            sidebar.classList.toggle(
                "open"
            );

        }
    );
}


/* =========================================================
   NOTIFICATIONS
========================================================= */

const notificationButton =
    document.getElementById(
        "notificationBtn"
    );


if (notificationButton) {

    notificationButton.addEventListener(
        "click",
        () => {

            showToast(
                currentUser
                    ? "No new notifications."
                    : "Login to view notifications."
            );

        }
    );
}


/* =========================================================
   MODAL CONTROLS
========================================================= */

const modalClose =
    document.getElementById(
        "modalClose"
    );


if (modalClose) {

    modalClose.addEventListener(
        "click",
        closeModal
    );
}


const cancelModal =
    document.getElementById(
        "cancelModal"
    );


if (cancelModal) {

    cancelModal.addEventListener(
        "click",
        closeModal
    );
}


if (modalOverlay) {

    modalOverlay.addEventListener(
        "click",
        event => {

            if (
                event.target ===
                modalOverlay
            ) {

                closeModal();
            }

        }
    );
}


/* =========================================================
   INITIALIZATION
========================================================= */

async function initialize() {

    updateUserUI();

    updateCommunitySidebar();


    try {

        await refreshData();

    } catch (error) {

        console.error(
            "Initial data loading failed:",
            error
        );
    }


    if (currentUser && authToken) {

        showDashboard();

    } else {

        /*
          Keep the dashboard publicly visible.
          Login is required only for protected actions.
        */

        showDashboard();
    }
}


/* =========================================================
   START APPLICATION
========================================================= */

initialize();
