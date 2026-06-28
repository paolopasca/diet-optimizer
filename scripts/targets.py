#!/usr/bin/env python3
"""
targets.py — calcola kcal e macro target in modo deterministico.

Pensato per il caso "via di mezzo": l'utente CONOSCE il proprio metabolismo
basale (BMR, kcal a riposo). Questo script applica fattore di attivita' e
obiettivo, e deriva i grammi di macro. Niente aritmetica fatta a mano.

Uso:
    python3 targets.py --bmr 1700 --activity moderato --goal definizione --weight 78
    python3 targets.py --bmr 1700 --activity sedentario --goal mantenimento
    # oppure passa direttamente il TDEE se gia' lo conosci:
    python3 targets.py --tdee 2600 --goal massa --weight 80

Output: JSON con il blocco "targets" pronto da inserire nello spec di solve_diet.py.

Se manca --weight, le proteine sono stimate come % delle kcal (meno preciso);
con --weight si usano g/kg (standard).
"""
import sys
import json
import argparse

ACTIVITY = {           # moltiplicatori applicati al BMR
    "sedentario": 1.2,
    "leggero": 1.375,
    "moderato": 1.55,
    "intenso": 1.725,
    "atleta": 1.9,
}
GOAL_ADJ = {           # variazione kcal sul TDEE
    "definizione": -0.20,
    "mantenimento": 0.0,
    "massa": 0.10,
}


def compute(bmr=None, tdee=None, activity="moderato", goal="mantenimento",
            weight=None, protein_g_per_kg=1.8, fat_pct=0.25, fiber_min=28):
    if tdee is None:
        if bmr is None:
            raise ValueError("Serve --bmr oppure --tdee.")
        if activity not in ACTIVITY:
            raise ValueError(f"activity sconosciuta: {activity}. Usa {list(ACTIVITY)}")
        tdee = bmr * ACTIVITY[activity]
    if goal not in GOAL_ADJ:
        raise ValueError(f"goal sconosciuto: {goal}. Usa {list(GOAL_ADJ)}")

    kcal = tdee * (1 + GOAL_ADJ[goal])

    # proteine
    if weight:
        protein_g = protein_g_per_kg * weight
    else:
        protein_g = (0.30 * kcal) / 4.0  # fallback: 30% kcal
    # grassi
    fat_g = (fat_pct * kcal) / 9.0
    if weight:
        fat_g = max(fat_g, 0.8 * weight)  # minimo fisiologico
    # carboidrati = resto
    carb_kcal = kcal - protein_g * 4 - fat_g * 9
    carb_g = max(carb_kcal / 4.0, 0.0)

    return {
        "_derivation": {
            "tdee": round(tdee, 0),
            "goal": goal,
            "goal_adjust_pct": round(GOAL_ADJ[goal] * 100, 0),
            "protein_basis": f"{protein_g_per_kg} g/kg" if weight else "30% kcal",
        },
        "targets": {
            "kcal": round(kcal, 0),
            "protein_g": round(protein_g, 0),
            "carb_g": round(carb_g, 0),
            "fat_g": round(fat_g, 0),
            "fiber_g_min": fiber_min,
        },
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bmr", type=float, help="metabolismo basale, kcal a riposo")
    ap.add_argument("--tdee", type=float, help="fabbisogno totale (salta il calcolo da BMR)")
    ap.add_argument("--activity", default="moderato", choices=list(ACTIVITY))
    ap.add_argument("--goal", default="mantenimento", choices=list(GOAL_ADJ))
    ap.add_argument("--weight", type=float, help="peso in kg (per proteine g/kg)")
    ap.add_argument("--protein-per-kg", type=float, default=1.8)
    ap.add_argument("--fat-pct", type=float, default=0.25)
    ap.add_argument("--fiber-min", type=float, default=28)
    a = ap.parse_args()
    try:
        out = compute(bmr=a.bmr, tdee=a.tdee, activity=a.activity, goal=a.goal,
                      weight=a.weight, protein_g_per_kg=a.protein_per_kg,
                      fat_pct=a.fat_pct, fiber_min=a.fiber_min)
    except ValueError as e:
        sys.stderr.write(str(e) + "\n")
        sys.exit(2)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
