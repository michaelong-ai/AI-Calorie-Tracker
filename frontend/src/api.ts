// api.ts — the frontend's ONLY door to the backend.
//
// Every screen calls these functions instead of using fetch() directly.
// That gives us one place to set the server address, handle errors the same
// way everywhere, and swap localhost for the real deployed URL later (T0.4).

import type {
  CalcInput,
  CalcResult,
  DaySummary,
  Entry,
  EntryInput,
  EstimateResult,
  Goal,
  GoalInput,
  TrendsData,
  WeightEntry,
} from "./types";

// Where the backend lives. import.meta.env is Vite's way of injecting
// build-time configuration: in development this falls back to localhost,
// and at deploy time we set VITE_API_URL without touching code.
const API_BASE: string = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

/**
 * Shared request helper all API functions funnel through.
 *
 * Inputs: an URL path like "/entries", and optional fetch options (method,
 * body). Returns the response parsed as JSON, typed as T for the caller.
 * Throws an Error with a readable message when the server answers with a
 * failure status — callers catch it and show the message to the user.
 */
async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    // Tell the server we're sending/expecting JSON.
    headers: { "Content-Type": "application/json" },
    ...options,
  });

  if (!response.ok) {
    // Try to extract FastAPI's error message ({"detail": "..."}); if the
    // body isn't JSON, fall back to the HTTP status text.
    let detail = response.statusText;
    try {
      const body = await response.json();
      if (body.detail) detail = JSON.stringify(body.detail);
    } catch {
      /* body wasn't JSON — keep statusText */
    }
    throw new Error(`API error ${response.status}: ${detail}`);
  }

  // DELETE returns "204 No Content" — there is no body to parse.
  if (response.status === 204) return undefined as T;

  return response.json() as Promise<T>;
}

// --- Health -----------------------------------------------------------------

/** Ask the backend if it's alive. Returns e.g. {status: "ok", service: "..."}. */
export function fetchHealth(): Promise<{ status: string; service: string }> {
  return request("/health");
}

// --- Entries (backend endpoints built in task T1.1) --------------------------

/** List all entries logged on one local calendar day, oldest first. */
export function listEntries(localDate: string): Promise<Entry[]> {
  return request(`/entries?local_date=${localDate}`);
}

/** Create a new entry; returns it with its database id filled in. */
export function createEntry(input: EntryInput): Promise<Entry> {
  return request("/entries", { method: "POST", body: JSON.stringify(input) });
}

/** Overwrite an existing entry's editable fields; returns the updated row. */
export function updateEntry(id: number, input: EntryInput): Promise<Entry> {
  return request(`/entries/${id}`, { method: "PUT", body: JSON.stringify(input) });
}

/** Delete an entry permanently. Returns nothing (HTTP 204). */
export function deleteEntry(id: number): Promise<void> {
  return request(`/entries/${id}`, { method: "DELETE" });
}

// --- Goals (Sprint 2) -----------------------------------------------------------

/** Ask the backend to compute suggested targets from stats. Saves nothing. */
export function calculateTargets(input: CalcInput): Promise<CalcResult> {
  return request("/goals/calculate", { method: "POST", body: JSON.stringify(input) });
}

/** Save a goal as a NEW version (goals are never overwritten). */
export function saveGoal(input: GoalInput): Promise<Goal> {
  return request("/goals", { method: "POST", body: JSON.stringify(input) });
}

/** The goal active on a given day — or null if that day predates all goals. */
export function fetchActiveGoal(localDate: string): Promise<Goal | null> {
  return request(`/goals/active?local_date=${localDate}`);
}

/** Every goal version ever saved, newest first. */
export function fetchGoalHistory(): Promise<Goal[]> {
  return request("/goals");
}

// --- Weights & history (Sprint 4) --------------------------------------------------

/** Record a body weight for a day. */
export function logWeight(weightKg: number, localDate: string): Promise<WeightEntry> {
  return request("/weights", {
    method: "POST",
    body: JSON.stringify({ weight_kg: weightKg, local_date: localDate }),
  });
}

/** All weight readings, newest first. */
export function listWeights(): Promise<WeightEntry[]> {
  return request("/weights");
}

/** Delete a weight reading (typo fix). */
export function deleteWeight(id: number): Promise<void> {
  return request(`/weights/${id}`, { method: "DELETE" });
}

/** Per-day totals + applicable target for a date range, newest day first. */
export function fetchDaySummaries(start: string, end: string): Promise<DaySummary[]> {
  return request(`/days?start=${start}&end=${end}`);
}

/** Weekly intake averages + weight series for the last N weeks (T4.3). */
export function fetchTrends(weeks = 8): Promise<TrendsData> {
  return request(`/trends?weeks=${weeks}`);
}

/**
 * URL of the downloadable HTML progress report (T5.1). Used as a plain
 * <a href> — the backend sets Content-Disposition: attachment, so the
 * browser saves the file rather than navigating to it.
 */
export function reportUrl(weeks = 8): string {
  return `${API_BASE}/report?weeks=${weeks}`;
}

// --- AI estimation (Sprint 3) ----------------------------------------------------

/**
 * Send a meal photo and/or text description for AI estimation.
 *
 * This one does NOT go through request(): file uploads use FormData
 * (multipart), and crucially we must NOT set a Content-Type header — the
 * browser generates it, including the "boundary" string that separates the
 * parts. Setting it by hand is the classic file-upload bug.
 */
export async function estimateMeal(
  imageFile: File | null,
  text: string,
): Promise<EstimateResult> {
  const form = new FormData();
  if (imageFile) form.append("image", imageFile);
  if (text.trim()) form.append("text", text.trim());

  const response = await fetch(`${API_BASE}/estimate`, {
    method: "POST",
    body: form, // browser sets Content-Type: multipart/form-data; boundary=...
  });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      if (body.detail) detail = String(body.detail);
    } catch {
      /* keep statusText */
    }
    throw new Error(detail);
  }
  return response.json();
}

// --- Date helper --------------------------------------------------------------

/**
 * Today's date in the USER'S timezone as "YYYY-MM-DD".
 *
 * This is the client-side capture of `local_date` — a core design decision
 * (see ARCHITECTURE.md "day boundary"): the calendar day is determined by
 * the phone's clock at logging time, never by the server's timezone.
 * Note: date.toISOString() would be WRONG here — it converts to UTC first,
 * which flips to the wrong day for evening times east of Greenwich.
 */
export function toLocalDate(date: Date): string {
  const year = date.getFullYear();
  // getMonth() is 0-based (January = 0); padStart keeps two digits ("07").
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}
