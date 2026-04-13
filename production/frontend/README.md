# FlowSync Dashboard — Frontend

A modern, professional Next.js 14 dashboard for the FlowSync AI Customer Support platform.

## Tech Stack

- **Next.js 14** (App Router)
- **TypeScript**
- **Tailwind CSS** (custom brand theme)
- **Lucide React** (icons)

## Features

- 🌗 **Dark/Light mode** toggle with persistence
- 📱 **Fully responsive** — mobile, tablet, desktop
- 🎫 **Submit tickets** with full validation and success animation
- 📋 **My Tickets** — view all tickets by email with status badges
- 🔍 **Track Ticket** — quick status lookup by Ticket ID
- 🎫 **Ticket Detail** — conversation view with AI responses
- ⚡ **Loading skeletons** and toast notifications
- 🎨 **TechCorp brand theme** — blue/teal palette

## Pages

| Route | Description |
|-------|-------------|
| `/` | Landing page + Support form + Recent activity |
| `/my-tickets` | Customer's all tickets (search by email) |
| `/ticket/[id]` | Single ticket detail with conversation |
| `/status` | Quick ticket status checker by ID |

## Getting Started

### 1. Install Dependencies

```bash
cd production/frontend
npm install
```

### 2. Set Environment

The `.env.local` file already has the default:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Change this if your backend runs on a different host/port.

### 3. Run Development Server

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

### 4. Build for Production

```bash
npm run build
npm run start
```

## Connecting to Backend

The frontend connects to the FastAPI backend via the `NEXT_PUBLIC_API_URL` environment variable.

| Backend URL | Frontend Env |
|-------------|-------------|
| `http://localhost:8000` | `NEXT_PUBLIC_API_URL=http://localhost:8000` |
| `http://your-server:8000` | `NEXT_PUBLIC_API_URL=http://your-server:8000` |
| `https://api.flowsync.com` | `NEXT_PUBLIC_API_URL=https://api.flowsync.com` |

The frontend calls these backend endpoints:
- `POST /support/submit` — Submit new ticket
- `GET /support/ticket/{id}` — Get ticket status
- `GET /support/tickets?email=` — List tickets by email
- `GET /health` — Health check

## Project Structure

```
frontend/
├── app/
│   ├── layout.tsx          # Root layout (theme, header, footer)
│   ├── page.tsx            # Landing + support form
│   ├── globals.css         # Global styles + Tailwind components
│   ├── my-tickets/
│   │   └── page.tsx        # My tickets page
│   ├── status/
│   │   └── page.tsx        # Ticket status checker
│   └── ticket/[id]/
│       └── page.tsx        # Ticket detail page
├── components/
│   ├── Header.tsx          # Navigation bar + theme toggle
│   ├── SupportForm.tsx     # Support form with validation
│   ├── TicketCard.tsx      # Ticket display card
│   ├── Dashboard.tsx       # Stats dashboard
│   ├── ActivityFeed.tsx    # Recent activity feed
│   ├── StatsCard.tsx       # Stats card component
│   ├── Toast.tsx           # Toast notification system
│   ├── Skeleton.tsx        # Loading skeleton components
│   └── ThemeProvider.tsx   # Dark/light mode context
├── lib/
│   ├── api.ts              # API client (fetch wrapper)
│   └── utils.ts            # Helpers (dates, status, validation)
├── package.json
├── tailwind.config.ts
├── tsconfig.json
├── next.config.js
└── .env.local
```

## Screenshots

The dashboard features:
- **Gradient hero** with animated background
- **Clean card-based** ticket listings with status/priority badges
- **Chat-style** conversation view for ticket details
- **Toast notifications** for success/error feedback
- **Smooth animations** (fade-in, slide-up, bounce)
