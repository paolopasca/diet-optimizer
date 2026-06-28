#!/usr/bin/env python3
"""
solve_diet.py — esatto, deterministico. NON inventa numeri.

Risolve il "diet problem" nella forma robusta: i cibi (e i loro valori
nutrizionali) sono FISSATI a monte dall'LLM; questo script decide solo le
QUANTITA' (grammi, o porzioni intere) che centrano kcal e macro.

Uso:
    python3 solve_diet.py spec.json          # legge da file
    cat spec.json | python3 solve_diet.py    # legge da stdin
    python3 solve_diet.py spec.json --pretty # output umano oltre al JSON

Backend: scipy.optimize.linprog (HiGHS). LP se tutte le quantita' sono
continue, MILP se almeno un cibo ha "integer": true.

--------------------------------------------------------------------------
SCHEMA DELLO SPEC (input)
{
  "targets": {                 # tutti opzionali tranne kcal
    "kcal": 2200,
    "protein_g": 165,          # se assente -> non vincolato
    "carb_g": 220,
    "fat_g": 70,
    "fiber_g_min": 25          # solo minimo, opzionale
  },
  "tolerance": {               # banda accettabile, frazione del target
    "kcal": 0.03,              # default 0.03 (=±3%)
    "macro": 0.07              # default 0.07 (=±7%)
  },
  "foods": [
    {
      "name": "Petto di pollo",
      "per100g": {"kcal": 100, "protein_g": 23, "carb_g": 0, "fat_g": 1, "fiber_g": 0},
      "min_g": 0, "max_g": 300,   # vincoli fisici per cibo (default 0..1000)
      "meal": "pranzo",           # opzionale, per raggruppare e bilanciare i pasti
      "integer": false,           # opzionale, porzioni intere
      "serving_g": 100,           # richiesto se integer: true (grammi per porzione)
      "cost": null                # opzionale, costo per 100g
    }
  ],
  "meals": {                      # opzionale: quota kcal desiderata per pasto
    "colazione": 0.25, "pranzo": 0.40, "cena": 0.35
  },
  "objective": "balance"          # "balance" (min scostamento macro) | "cost"
}
--------------------------------------------------------------------------
Garanzia: i "totals" in output sono calcolati dal solver sui grammi scelti,
NON vanno ricalcolati a mano. Presentare l'output cosi' com'e'.
"""
import sys
import json

try:
    import numpy as np
    from scipy.optimize import linprog
except ImportError:
    sys.stderr.write(
        "Manca scipy. Installa con: python3 -m pip install scipy numpy\n")
    sys.exit(2)

MACROS = ["protein_g", "carb_g", "fat_g"]
KCAL_PER_G = {"protein_g": 4.0, "carb_g": 4.0, "fat_g": 9.0}


def _num(v, default=0.0):
    try:
        return float(v)
    except (TypeError, ValueError):
        return float(default)


def solve(spec):
    foods = spec.get("foods", [])
    if not foods:
        return {"status": "error", "message": "Nessun cibo nello spec."}

    targets = spec.get("targets", {})
    kcal_t = _num(targets.get("kcal"), 0.0)
    if kcal_t <= 0:
        return {"status": "error", "message": "targets.kcal mancante o non valido."}

    tol = spec.get("tolerance", {})
    tol_kcal = _num(tol.get("kcal"), 0.03)
    tol_macro = _num(tol.get("macro"), 0.07)
    objective = spec.get("objective", "balance")

    n = len(foods)

    # Per ogni cibo, contributo per grammo (o per porzione se integer).
    # x[i] = grammi (continuo) oppure n. porzioni (intero).
    is_int = [bool(f.get("integer")) for f in foods]
    unit_g = []          # grammi rappresentati da un'unita' di x[i]
    for i, f in enumerate(foods):
        if is_int[i]:
            sg = _num(f.get("serving_g"), 0.0)
            if sg <= 0:
                return {"status": "error",
                        "message": f"'{f.get('name')}' ha integer:true ma serving_g mancante."}
            unit_g.append(sg)
        else:
            unit_g.append(1.0)  # x in grammi

    def per_unit(f, i, key):
        # valore del nutriente per unita' di x[i]
        p100 = _num(f.get("per100g", {}).get(key), 0.0)
        return p100 / 100.0 * unit_g[i]

    kcal_u = np.array([per_unit(f, i, "kcal") for i, f in enumerate(foods)])
    macro_u = {m: np.array([per_unit(f, i, m) for i, f in enumerate(foods)])
               for m in MACROS}
    fiber_u = np.array([per_unit(f, i, "fiber_g") for i, f in enumerate(foods)])
    cost_u = np.array([_num(f.get("cost"), 0.0) / 100.0 * unit_g[i]
                       for i, f in enumerate(foods)])

    # bounds su x[i] (in unita': grammi o porzioni)
    bounds = []
    for i, f in enumerate(foods):
        lo_g = _num(f.get("min_g"), 0.0)
        hi_g = _num(f.get("max_g"), 1000.0)
        if is_int[i]:
            bounds.append((max(0, int(np.floor(lo_g / unit_g[i]))),
                           int(np.ceil(hi_g / unit_g[i]))))
        else:
            bounds.append((lo_g, hi_g))

    # ---- variabili di scostamento (soft) ----
    # ordine variabili: [x_0..x_{n-1},
    #                     kcal+, kcal-,
    #                     per ogni macro con target: m+, m-,
    #                     per ogni pasto con quota: meal+, meal-]
    soft = []  # (label, vec, target, peso_eccesso, peso_difetto) in kcal-equiv
    soft.append(("kcal", kcal_u, kcal_t, 3.0, 3.0))  # kcal pesata di piu' = piu' stretta

    active_macros = []
    for m in MACROS:
        if targets.get(m) is not None:
            t = _num(targets.get(m))
            # peso in kcal-equivalente cosi' i macro sono comparabili tra loro
            soft.append((m, macro_u[m], t, KCAL_PER_G[m], KCAL_PER_G[m]))
            active_macros.append(m)

    meals_spec = spec.get("meals") or {}
    meal_terms = []
    for meal_name, share in meals_spec.items():
        share = _num(share)
        if share <= 0:
            continue
        coeff = np.array([kcal_u[i] if foods[i].get("meal") == meal_name else 0.0
                          for i in range(n)])
        if coeff.sum() == 0:
            continue  # nessun cibo in quel pasto, salta
        soft.append((f"meal:{meal_name}", coeff, share * kcal_t, 0.5, 0.5))
        meal_terms.append(meal_name)

    # fibra: minimo SOFT. Penalizza solo lo scarto SOTTO il minimo (eccesso libero),
    # cosi' non causa mai infeasibility: il solver da' sempre un piano e riporta lo scarto.
    fiber_min = _num(targets.get("fiber_g_min")) if targets.get("fiber_g_min") else 0.0
    if fiber_min > 0:
        soft.append(("fiber", fiber_u, fiber_min, 0.0, 2.0))

    n_soft = len(soft)
    n_var = n + 2 * n_soft

    # ---- costruzione matrici ----
    A_eq = np.zeros((n_soft, n_var))
    b_eq = np.zeros(n_soft)
    c = np.zeros(n_var)

    for j, (label, vec, t, w_plus, w_minus) in enumerate(soft):
        A_eq[j, :n] = vec
        dplus = n + 2 * j     # eccesso (sum > target)
        dminus = n + 2 * j + 1  # difetto (sum < target)
        A_eq[j, dplus] = -1.0
        A_eq[j, dminus] = +1.0
        b_eq[j] = t
        c[dplus] = w_plus
        c[dminus] = w_minus

    # nessun vincolo hard sui nutrienti: tutto soft -> mai infeasible coi bound validi
    A_ub = None
    b_ub = None

    # se objective = cost, aggiungi costo con peso piccolo (tie-break secondario)
    if objective == "cost" and cost_u.any():
        c[:n] += cost_u * 0.001

    var_bounds = list(bounds) + [(0, None)] * (2 * n_soft)

    integrality = np.zeros(n_var)
    for i in range(n):
        if is_int[i]:
            integrality[i] = 1

    res = linprog(c, A_ub=A_ub, b_ub=b_ub, A_eq=A_eq, b_eq=b_eq,
                  bounds=var_bounds, integrality=integrality, method="highs")

    if not res.success:
        return {"status": "infeasible",
                "message": res.message,
                "hint": "Allarga i max_g, aggiungi cibi, o rilassa le tolleranze."}

    x = res.x[:n]

    # ---- ricostruzione risultati (tutto calcolato, niente a mano) ----
    grams = [round(x[i] * unit_g[i], 1) for i in range(n)]
    servings = [int(round(x[i])) if is_int[i] else None for i in range(n)]

    def total(vec):
        return float(np.dot(x, vec))

    totals = {
        "kcal": round(total(kcal_u), 1),
        "protein_g": round(total(macro_u["protein_g"]), 1),
        "carb_g": round(total(macro_u["carb_g"]), 1),
        "fat_g": round(total(macro_u["fat_g"]), 1),
        "fiber_g": round(total(fiber_u), 1),
    }

    # scostamenti vs target e flag tolleranza
    deviations = {}
    within = True
    checks = [("kcal", kcal_t, tol_kcal)] + \
             [(m, _num(targets.get(m)), tol_macro) for m in active_macros]
    for label, t, tolf in checks:
        got = totals["kcal"] if label == "kcal" else totals[label]
        diff = got - t
        frac = (diff / t) if t else 0.0
        ok = abs(frac) <= tolf + 1e-9
        within = within and ok
        deviations[label] = {
            "target": round(t, 1), "got": round(got, 1),
            "diff": round(diff, 1), "pct": round(frac * 100, 1),
            "within_tolerance": ok,
        }

    # fibra: minimo soft, riportato come info (non fa fallire within_tolerance)
    if fiber_min > 0:
        fg = totals["fiber_g"]
        deviations["fiber_g"] = {
            "target_min": round(fiber_min, 1), "got": round(fg, 1),
            "diff": round(fg - fiber_min, 1),
            "within_tolerance": fg >= fiber_min - 1e-6,
        }

    # raggruppamento per pasto
    by_meal = {}
    for i, f in enumerate(foods):
        if grams[i] <= 0.05:
            continue
        meal = f.get("meal", "—")
        by_meal.setdefault(meal, {"items": [], "kcal": 0.0,
                                  "protein_g": 0.0, "carb_g": 0.0, "fat_g": 0.0})
        item = {"name": f.get("name"), "grams": grams[i]}
        if servings[i] is not None:
            item["servings"] = servings[i]
        item["kcal"] = round(x[i] * kcal_u[i], 1)
        by_meal[meal]["items"].append(item)
        by_meal[meal]["kcal"] += x[i] * kcal_u[i]
        for m in MACROS:
            by_meal[meal][m] += x[i] * macro_u[m][i]
    for meal in by_meal.values():
        for k in ("kcal", "protein_g", "carb_g", "fat_g"):
            meal[k] = round(meal[k], 1)

    suggestions = []
    for label, dv in deviations.items():
        if "pct" not in dv:            # la fibra ha una struttura diversa, gestita sotto
            continue
        if not dv["within_tolerance"]:
            direction = "troppo alto" if dv["diff"] > 0 else "troppo basso"
            suggestions.append(
                f"{label}: {dv['got']} vs target {dv['target']} ({dv['pct']:+}%, {direction}). "
                f"Aggiungi/rimuovi cibi ricchi di {label} o allarga i bound.")
    if fiber_min > 0 and totals["fiber_g"] < fiber_min - 1e-6:
        suggestions.append(
            f"fibra: {totals['fiber_g']} g sotto il minimo {round(fiber_min, 1)} g. "
            f"Aggiungi verdura, legumi o cereali integrali con max_g alti.")

    return {
        "status": "ok" if within else "ok_out_of_tolerance",
        "within_tolerance": within,
        "totals": totals,
        "deviations": deviations,
        "by_meal": by_meal,
        "plan": [{"name": foods[i].get("name"), "grams": grams[i],
                  **({"servings": servings[i]} if servings[i] is not None else {})}
                 for i in range(n) if grams[i] > 0.05],
        "suggestions": suggestions,
    }


def _pretty(out):
    if out.get("status") == "error":
        return f"ERRORE: {out['message']}"
    if out.get("status") == "infeasible":
        return f"INFEASIBLE: {out['message']}\n{out.get('hint','')}"
    lines = []
    flag = "OK" if out["within_tolerance"] else "FUORI TOLLERANZA"
    lines.append(f"[{flag}]")
    for meal, d in out["by_meal"].items():
        lines.append(f"\n{meal.upper()}  ({d['kcal']} kcal | P {d['protein_g']} C {d['carb_g']} G {d['fat_g']})")
        for it in d["items"]:
            sv = f" ({it['servings']} porz.)" if "servings" in it else ""
            lines.append(f"  - {it['name']}: {it['grams']} g{sv}  [{it['kcal']} kcal]")
    t = out["totals"]
    lines.append(f"\nTOTALE GIORNO: {t['kcal']} kcal | "
                 f"P {t['protein_g']} g | C {t['carb_g']} g | G {t['fat_g']} g | fibra {t['fiber_g']} g")
    for label, dv in out["deviations"].items():
        mark = "ok" if dv["within_tolerance"] else "!!"
        lines.append(f"  [{mark}] {label}: {dv['got']} / {dv['target']} ({dv['pct']:+}%)")
    for s in out.get("suggestions", []):
        lines.append(f"  -> {s}")
    return "\n".join(lines)


def main():
    args = [a for a in sys.argv[1:]]
    pretty = "--pretty" in args
    args = [a for a in args if not a.startswith("--")]
    if args:
        with open(args[0], "r", encoding="utf-8") as fh:
            spec = json.load(fh)
    else:
        spec = json.load(sys.stdin)
    out = solve(spec)
    if pretty:
        sys.stderr.write(_pretty(out) + "\n")
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
