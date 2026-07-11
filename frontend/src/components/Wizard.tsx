// Wizard.tsx — the AI estimation wizard (tasks T3.2–T3.4, spec F1 + E2).
//
// The four steps from the spec, as one state machine:
//   input   -> photo and/or text                       (T3.2 step 1)
//   loading -> waiting on the AI
//   review  -> estimate card + editable values         (T3.2 step 2, T3.3 step 3)
//   [save]  -> POST /entries with source ai/label      (T3.3 step 4)
// Failure paths (T3.4): AI errors show a retry + "enter manually" escape;
// kind=unknown drops straight into manual-entry mode inside the wizard.
//
// The cardinal rule (spec): NOTHING is saved until the user hits Save —
// the wizard talks to /estimate (read-only) until that final confirm.

import { useState } from "react";
import { createEntry, estimateMeal } from "../api";
import type { Entry, EstimateResult } from "../types";

interface WizardProps {
  date: string; // the local_date the entry will be logged under
  onSaved: (entry: Entry) => void; // Today adds the entry to its list
  onClose: () => void;
}

type Step = "input" | "loading" | "review";

// Editable number fields as strings (HTML inputs hold text).
interface Values {
  description: string;
  calories: string;
  protein_g: string;
  carbs_g: string;
  fat_g: string;
}

function Wizard({ date, onSaved, onClose }: WizardProps) {
  const [step, setStep] = useState<Step>("input");
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [text, setText] = useState("");
  const [estimate, setEstimate] = useState<EstimateResult | null>(null);
  const [values, setValues] = useState<Values>({
    description: "", calories: "", protein_g: "", carbs_g: "", fat_g: "",
  });
  // For label scans: how much the user actually had, in basis units
  // (servings / grams / packages). Numbers are scaled = base × factor.
  const [quantity, setQuantity] = useState("1");
  const [error, setError] = useState<string | null>(null);
  // true when the AI failed or said "unknown" and the user is typing
  // values by hand INSIDE the wizard (the F1 fallback requirement).
  const [manualMode, setManualMode] = useState(false);

  /** Step 1 -> 2: send the inputs to the AI. */
  async function runEstimate() {
    if (!imageFile && !text.trim()) {
      setError("Add a photo or describe the meal first.");
      return;
    }
    setStep("loading");
    setError(null);
    try {
      const result = await estimateMeal(imageFile, text);
      setEstimate(result);
      if (result.kind === "unknown") {
        // AI couldn't identify food: fall into manual mode with a note,
        // not a dead end (T3.4).
        setManualMode(true);
        setValues({
          description: text.trim(), calories: "", protein_g: "", carbs_g: "", fat_g: "",
        });
      } else {
        // Pre-fill the editable fields with the AI's numbers.
        setManualMode(false);
        setQuantity(defaultQuantity(result));
        setValues(valuesFrom(result, Number(defaultQuantity(result))));
      }
      setStep("review");
    } catch (e) {
      setError((e as Error).message);
      setStep("input"); // back to step 1 with the error + inputs intact
    }
  }

  /** The natural starting quantity for each label basis. */
  function defaultQuantity(r: EstimateResult): string {
    if (r.kind !== "label" || !r.label_basis) return "1";
    return r.label_basis.per === "100g" ? "100" : "1";
  }

  /** Scale the AI's base numbers by the chosen quantity into form values. */
  function valuesFrom(r: EstimateResult, qty: number): Values {
    // For estimates the numbers are already the whole portion (factor 1);
    // for labels: factor = servings, grams/100, or packages.
    let factor = 1;
    if (r.kind === "label" && r.label_basis) {
      factor = r.label_basis.per === "100g" ? qty / 100 : qty;
    }
    const round1 = (n: number) => String(Math.round(n * factor * 10) / 10);
    return {
      description: r.description,
      calories: round1(r.calories),
      protein_g: round1(r.protein_g),
      carbs_g: round1(r.carbs_g),
      fat_g: round1(r.fat_g),
    };
  }

  /** Label scans: changing "how much did you have?" rescales the fields. */
  function changeQuantity(q: string) {
    setQuantity(q);
    const n = Number(q);
    if (estimate && !Number.isNaN(n) && n > 0) {
      setValues(valuesFrom(estimate, n));
    }
  }

  /** Step 4: the explicit confirm — the only write in the whole wizard. */
  async function save() {
    const payload = {
      description: values.description.trim(),
      calories: Number(values.calories),
      protein_g: Number(values.protein_g),
      carbs_g: Number(values.carbs_g),
      fat_g: Number(values.fat_g),
      local_date: date,
      // Provenance: label transcription, AI estimate, or manual fallback.
      source: (manualMode
        ? "manual"
        : estimate?.kind === "label"
          ? "label"
          : "ai") as "manual" | "ai" | "label",
    };
    if (!payload.description) {
      setError("Description is required.");
      return;
    }
    if ([payload.calories, payload.protein_g, payload.carbs_g, payload.fat_g].some(Number.isNaN)) {
      setError("All nutrition values must be numbers (0 is fine).");
      return;
    }
    try {
      const entry = await createEntry(payload); // same single write path as manual entry
      onSaved(entry);
      onClose();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  // ---------------------------------------------------------------- render

  if (step === "loading") {
    return (
      <div className="card form">
        <h3>🔍 Analyzing…</h3>
        <p className="muted">The AI is looking at your {imageFile ? "photo" : "description"}.</p>
      </div>
    );
  }

  if (step === "review") {
    return (
      <div className="card form">
        {/* The estimate card: what the AI thinks + HOW it got there (T3.2) */}
        {manualMode ? (
          <>
            <h3>✏️ Enter manually</h3>
            <p className="muted">
              The AI couldn't identify food in that input — type the values
              yourself, or go back and try another photo.
            </p>
          </>
        ) : (
          <>
            <h3>{estimate?.kind === "label" ? "🏷️ Read from label" : "🤖 AI estimate"}</h3>
            <p className="muted">
              {estimate?.description} · confidence: {estimate?.confidence}
            </p>
            {estimate && estimate.assumptions.length > 0 && (
              <ul className="assumptions">
                {estimate.assumptions.map((a) => (
                  <li key={a} className="muted">{a}</li>
                ))}
              </ul>
            )}
            {/* Label scans: the serving-size question (E2). */}
            {estimate?.kind === "label" && estimate.label_basis && (
              <label>
                How much did you have?{" "}
                {estimate.label_basis.per === "100g"
                  ? "(grams)"
                  : estimate.label_basis.per === "serving"
                    ? `(servings${estimate.label_basis.serving_size_g ? `, 1 = ${estimate.label_basis.serving_size_g}g` : ""})`
                    : "(packages)"}
                <input inputMode="decimal" value={quantity}
                  onChange={(e) => changeQuantity(e.target.value)} />
              </label>
            )}
          </>
        )}

        {/* Step 3: every value editable before anything is saved (T3.3) */}
        <label>
          Description
          <input value={values.description}
            onChange={(e) => setValues({ ...values, description: e.target.value })} />
        </label>
        {([
          ["calories", "Calories (kcal)"],
          ["protein_g", "Protein (g)"],
          ["carbs_g", "Carbs (g)"],
          ["fat_g", "Fat (g)"],
        ] as const).map(([field, label]) => (
          <label key={field}>
            {label}
            <input inputMode="decimal" value={values[field]}
              onChange={(e) => setValues({ ...values, [field]: e.target.value })} />
          </label>
        ))}

        {error && <p className="error">{error}</p>}
        <div className="form-actions">
          <button type="button" onClick={() => setStep("input")}>Back</button>
          <button type="button" onClick={onClose}>Cancel</button>
          <button type="button" className="primary" onClick={save}>Save to tracker</button>
        </div>
      </div>
    );
  }

  // step === "input"
  return (
    <div className="card form">
      <h3>📷 Scan a meal</h3>
      <p className="muted">
        Snap the food or a nutrition label — or just describe what you ate.
      </p>

      {/* capture="environment" hints phones to open the rear camera. */}
      <label>
        Photo (food or nutrition label)
        <input
          type="file"
          accept="image/*"
          capture="environment"
          onChange={(e) => setImageFile(e.target.files?.[0] ?? null)}
        />
      </label>
      {imageFile && <p className="muted">Selected: {imageFile.name}</p>}

      <label>
        Description (optional — helps the AI)
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="e.g. chicken rice, extra rice, no skin"
        />
      </label>

      {error && (
        <>
          <p className="error">{error}</p>
          {/* T3.4: an AI failure must never trap the user — offer the
              manual escape hatch right next to retry. */}
          <button type="button" onClick={() => {
            setManualMode(true);
            setEstimate(null);
            setValues({ description: text.trim(), calories: "", protein_g: "", carbs_g: "", fat_g: "" });
            setError(null);
            setStep("review");
          }}>
            ✏️ Enter values manually instead
          </button>
        </>
      )}

      <div className="form-actions">
        <button type="button" onClick={onClose}>Cancel</button>
        <button type="button" className="primary" onClick={runEstimate}>
          Estimate
        </button>
      </div>
    </div>
  );
}

export default Wizard;
