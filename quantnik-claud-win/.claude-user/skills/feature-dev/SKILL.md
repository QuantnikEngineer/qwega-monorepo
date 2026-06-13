---
name: feature-dev
description: Pulls Epics and User Stories from Jira and generates a full-stack application scaffold — React JS frontend with modern fintech design (inspired by CRED/BankBazaar/Groww/Paytm) and Node.js/Express backend — writing all source files to disk.
---

When this skill is invoked, follow the steps below in strict order. Do not skip a step or move to the next until the current one is complete.

---

## Step 1 — Authenticate & discover the Atlassian workspace

Call `atlassianUserInfo` to confirm the user is authenticated. If it fails, call `getAccessibleAtlassianResources` and follow the auth flow. Extract the `cloudId` from the accessible resources — you need it for every subsequent Jira call.

---

## Step 2 — Select the Jira project

Call `getVisibleJiraProjects` and display results as a numbered list:

```
Available Jira projects:

1. [Project name] ([KEY])
2. [Project name] ([KEY])
...
```

Ask: "Which Jira project contains the stories you want to build? Enter the number or project key."

Wait for the user's response.

---

## Step 3 — Fetch Epics from the project

Call `searchJiraIssuesUsingJql` with:

```
project = [KEY] AND issuetype = Epic ORDER BY created ASC
```

Display the results as a numbered list:

```
Epics in [PROJECT NAME]:

1. [[KEY-n]] [Epic summary]
2. [[KEY-n]] [Epic summary]
...
```

Ask: "Which epic(s) should I build? Enter numbers separated by commas, or 'all' for everything."

Wait for the user's response.

---

## Step 4 — Fetch all Stories under the selected Epic(s)

For each selected epic, call `searchJiraIssuesUsingJql`:

```
project = [KEY] AND issuetype = Story AND "Epic Link" = [EPIC-KEY] ORDER BY created ASC
```

If the above returns zero results, retry with the parent field:

```
project = [KEY] AND issuetype = Story AND parent = [EPIC-KEY] ORDER BY created ASC
```

For each story returned, call `getJiraIssue` to fetch the full description and acceptance criteria.

Display a compact summary to the user:

```
Found [n] stories across [m] epic(s):

Epic: [EPIC-KEY] [Epic name]
  • [KEY-n] [Story summary] ([x] pts, [priority])
  • [KEY-n] [Story summary] ([x] pts, [priority])

Epic: [EPIC-KEY] [Epic name]
  • ...
```

Ask: "Ready to generate the full-stack code for these stories? I'll create a React JS + Node.js project. Confirm with 'yes' or tell me any preferences (e.g., project folder name, port numbers, dark/light theme)."

Wait for the user's confirmation and any preferences before generating code.

---

## Step 5 — Plan the architecture

Before writing any file, derive the application architecture from the stories:

**Analyse each story and extract:**
- UI screens/pages required (one screen per major user-facing story)
- API endpoints needed (derive from acceptance criteria)
- Data models (entities and fields referenced in stories)
- Auth flows (OTP, login, session handling if mentioned)
- Key UI interactions (filters, forms, comparisons, modals)

**Define the project structure:**

```
[project-name]/
├── frontend/                    # React JS (Vite)
│   ├── src/
│   │   ├── components/          # Reusable UI components
│   │   ├── pages/               # One file per screen/epic
│   │   ├── hooks/               # Custom React hooks
│   │   ├── services/            # API call functions (axios)
│   │   ├── context/             # React context for global state
│   │   ├── utils/               # Helpers, formatters
│   │   ├── styles/              # Global CSS / Tailwind config
│   │   ├── App.jsx
│   │   └── main.jsx
│   ├── index.html
│   ├── vite.config.js
│   ├── tailwind.config.js
│   └── package.json
│
└── backend/                     # Node.js / Express
    ├── src/
    │   ├── routes/              # One router file per epic domain
    │   ├── controllers/         # Business logic per domain
    │   ├── middleware/          # Auth, validation, error handling
    │   ├── models/              # Data models (JSON/in-memory or Mongoose schemas)
    │   ├── services/            # External integrations, shared logic
    │   └── utils/               # Helpers
    ├── app.js
    ├── server.js
    └── package.json
```

Print the planned structure to the user before writing files, so they can spot mismatches early.

---

## Step 6 — Generate the frontend

### Design principles

Apply a **modern fintech aesthetic** throughout:

- **Colour palette:** Deep navy (`#0A0F1E`) primary background, electric blue (`#3B82F6`) accent, emerald green (`#10B981`) for success/positive states, amber (`#F59E0B`) for warnings, rose (`#F43F5E`) for errors. Offer a clean white (`#FFFFFF`) surface variant with slate borders for card sections.
- **Typography:** Inter or DM Sans — bold headings, medium labels, regular body. Large hero numbers for amounts/limits.
- **Cards:** Rounded-2xl with subtle glass-morphism (`backdrop-blur`, semi-transparent backgrounds) for premium feel. Inspired by CRED's dark card surfaces.
- **Buttons:** Full-width CTA buttons with gradient fills on key actions; ghost buttons for secondary actions.
- **Micro-interactions:** Hover scale transforms, smooth 200ms transitions, skeleton loaders on data-fetch states.
- **Mobile-first:** Responsive grid, sticky headers, bottom-sheet modals on small screens.

### Files to generate (map each to its story)

For every **page** identified in Step 5, create `frontend/src/pages/[PageName].jsx`. Each page must:
1. Import and use shared components from `components/`
2. Call the matching backend API via `services/api.js`
3. Handle loading, error, and empty states
4. Implement the acceptance criteria from the corresponding Jira story as the functional behaviour

For every **reusable element** used across two or more pages, create a dedicated component in `components/`.

Also generate:
- `frontend/src/services/api.js` — centralised Axios instance with base URL from env, request/response interceptors, and one exported function per API endpoint
- `frontend/src/context/AppContext.jsx` — global state (user session, selected items, comparison basket if relevant)
- `frontend/src/App.jsx` — React Router v6 route configuration
- `frontend/src/main.jsx` — Vite entry point
- `frontend/tailwind.config.js` — extended theme with the fintech colour tokens above
- `frontend/vite.config.js` — proxy `/api` to `http://localhost:[backend-port]`
- `frontend/package.json` — dependencies: react, react-dom, react-router-dom, axios, tailwindcss, @headlessui/react, lucide-react, framer-motion

### Code quality rules

- Functional components with hooks only — no class components
- PropTypes or JSDoc types on every component
- All magic strings in a `constants.js` file
- No inline styles — use Tailwind classes exclusively
- Every form must have client-side validation matching the story's AC
- Accessibility: `aria-label` on all interactive elements, keyboard-navigable modals

---

## Step 7 — Generate the backend

### API design

For every **domain** (roughly one per epic), create:
- `backend/src/routes/[domain].js` — Express Router with routes derived from the AC
- `backend/src/controllers/[domain].js` — handler functions, one per route
- `backend/src/models/[domain].js` — data model (use an in-memory store or Mongoose schema depending on story complexity; default to in-memory JSON with a comment showing the Mongoose equivalent)

### Files to always generate

- `backend/app.js` — Express app setup: CORS (allow localhost frontend port), JSON body parser, route mounting, global error handler
- `backend/server.js` — `app.listen` with port from `process.env.PORT || 3001`
- `backend/src/middleware/errorHandler.js` — standard error response shape `{ success: false, message, code }`
- `backend/src/middleware/validate.js` — request validation using express-validator; call this in routes that accept form data
- `backend/src/middleware/auth.js` — placeholder JWT middleware (verify token from `Authorization: Bearer …` header; return 401 if missing/invalid)
- `backend/package.json` — dependencies: express, cors, dotenv, express-validator, jsonwebtoken, bcryptjs, uuid

### Route conventions

- `GET /api/[resource]` — list with optional query params for filter/sort
- `GET /api/[resource]/:id` — single item
- `POST /api/[resource]` — create
- `PUT /api/[resource]/:id` — update
- `DELETE /api/[resource]/:id` — delete
- `POST /api/[resource]/:id/[action]` — non-CRUD operations (e.g. submit, verify, apply)

Every route handler must:
1. Validate input using the validate middleware
2. Return `{ success: true, data: {...} }` on success
3. Call `next(error)` on failure (caught by the global error handler)

OTP flows required by stories: generate a 6-digit OTP, store it in-memory with a 5-minute TTL, expose `POST /api/otp/send` and `POST /api/otp/verify`.

---

## Step 8 — Write all files to disk

Ask the user: "Where should I write the project? Enter an absolute path or press Enter to use `~/projects/[project-name]`."

Wait for the response, then use the **Write** tool to create every file planned in Steps 5–7. Write files in this order:

1. Both `package.json` files
2. Config files (`vite.config.js`, `tailwind.config.js`, `.env.example`)
3. Backend entry files (`app.js`, `server.js`)
4. Backend middleware (error handler, validate, auth)
5. Backend models → controllers → routes (one epic domain at a time)
6. Frontend entry files (`main.jsx`, `App.jsx`, `tailwind.config.js`)
7. Frontend context and services
8. Frontend components (shared first, then page-specific)
9. Frontend pages (one per story group / screen)
10. Root `README.md` with setup instructions

After writing each group, print a one-line progress update:
```
✓ Backend middleware written (3 files)
✓ Backend: card-catalog domain written (3 files)
...
```

---

## Step 9 — Report and next steps

Print a final summary:

```
Done. Full-stack project generated at [path]:

Frontend (React JS + Vite + Tailwind)
  Pages:      [n] screens mapped to [m] stories
  Components: [n] reusable components
  Services:   1 centralised API client

Backend (Node.js + Express)
  Domains:    [n] route domains mapped to [m] epics
  Endpoints:  [list all routes in METHOD /path format]
  Middleware: error handler, validator, auth (JWT placeholder)

To run locally:
  cd [path]/backend && npm install && npm run dev
  cd [path]/frontend && npm install && npm run dev

Open http://localhost:5173 in your browser.
```

Ask: "Would you like me to add more screens, wire up a real database, add tests, or generate a Docker Compose setup?"
