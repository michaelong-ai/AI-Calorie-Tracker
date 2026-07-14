// QuickPick.tsx — the food-library dropdown (task T6.4, from idea E6).
//
// "If I ate it before, I shouldn't need to call the AI again." This dropdown
// lists foods the user has already logged — each option shows the AI-given
// name and its calories — and picking one hands the food's full nutrition
// values to the parent form. The parent pre-fills its fields; the user can
// still edit (today's portion may differ) and saves through the normal
// entries write path. Zero AI calls, instant, works offline from the API's
// point of view.
//
// Used in BOTH manual-entry spots: Today's "Add manually" form and the
// wizard's manual fallback.

import { useEffect, useState } from "react";
import { fetchFrequentFoods } from "../api";
import type { FrequentFood } from "../types";

function QuickPick({ onPick }: { onPick: (food: FrequentFood) => void }) {
  const [foods, setFoods] = useState<FrequentFood[]>([]);

  // Load the library once when the form opens. Failure is non-fatal — the
  // form simply appears without a dropdown, manual typing still works.
  useEffect(() => {
    fetchFrequentFoods().then(setFoods).catch(() => {});
  }, []);

  // First-ever meal: no history yet, so render nothing rather than an
  // empty dropdown (empty-state rule, T5.2).
  if (foods.length === 0) return null;

  return (
    <label>
      Quick pick from your history
      {/* value="" pins the select to the placeholder — picking an option
          fires onChange (filling the form) but the select snaps back, so
          it reads as a command ("fill from…"), not a stored value. */}
      <select
        value=""
        onChange={(e) => {
          const i = Number(e.target.value);
          if (!Number.isNaN(i) && foods[i]) onPick(foods[i]);
        }}
      >
        <option value="" disabled>
          Eaten before? Pick it — no AI needed
        </option>
        {foods.map((f, i) => (
          <option key={f.description} value={i}>
            {f.description} — {Math.round(f.calories)} kcal
            {f.times_logged > 1 ? ` (×${f.times_logged})` : ""}
          </option>
        ))}
      </select>
    </label>
  );
}

export default QuickPick;
