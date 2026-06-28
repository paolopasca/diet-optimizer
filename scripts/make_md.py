#!/usr/bin/env python3
"""Esporta il piano (output del solver) in markdown. Legge /tmp/week_plan.json. Output ~/Desktop/dieta/dieta_paolo.md"""
import json, os
HERE = os.path.dirname(os.path.abspath(__file__))
d = json.load(open("/tmp/week_plan.json"))
DB = {f["name"]: f for f in json.load(open(os.path.join(HERE, "..", "data", "foods.json")))["foods"]}
SHORT = {
 "Latte di vacca, UHT, parzialmente scremato": "latte p.s.", "Yogurt greco, 0% lipidi": "yogurt greco 0%",
 "Yogurt greco, da latte intero": "yogurt greco", "Corn flakes": "corn flakes",
 "Olio di oliva extra vergine": "olio EVO", "Pane di tipo integrale": "pane integrale",
 "Pasta di semola, integrale": "pasta integrale", "Pasta di semola": "pasta",
 "Tonno in salamoia, sgocciolato": "tonno al naturale", "Pollo, petto, crudo": "pollo",
 "Bovino adulto o vitellone, costata, crudo": "manzo (tagliata)",
 "Macinato di bovino magro (~5% grassi)": "macinato magro", "Orata, filetti": "orata",
 "Merluzzo o nasello": "merluzzo", "Gamberi sgusciati, surgelati": "gamberi",
 "Prosciutto crudo di Parma DOP, sgrassato": "prosciutto crudo", "Bresaola della Valtellina IGP": "bresaola",
 "Mozzarella di vacca": "mozzarella", "Feta": "feta", "Uova di gallina, intero": "uova",
 "Ceci, in scatola, scolati": "ceci", "Lenticchie, in scatola, scolate": "lenticchie",
 "Fagiolini, freschi": "fagiolini", "Pomodorini ciliegino, freschi": "pomodorini",
 "Pomodori, da insalata, freschi": "pomodori", "Cetrioli, freschi": "cetrioli",
 "Zucchine, chiare": "zucchine", "Melanzane, cotte, in padella": "melanzane",
 "Peperoni, crudi": "peperoni", "Lattuga, fresca": "lattuga", "Rucola o Ruchetta, fresca": "rucola",
 "Banane, fresche": "banana", "Pesche, fresche, con buccia": "pesca", "Cocomero, fresco": "cocomero",
 "Uva, fresca": "uva", "Mirtilli, freschi": "mirtilli", "Albicocche, fresche": "albicocche",
 "Avocado, fresco": "avocado", "Mandorle dolci, secche": "mandorle", "Noci, secche": "noci",
 "Miele": "miele", "Gelato confezionato, fior di latte, in vaschetta": "gelato fiordilatte",
}
PLUR = {"banana": "banane", "pesca": "pesche", "mela": "mele", "pera": "pere", "arancia": "arance"}
TAG = {"Lunedi": "pesce", "Martedi": "pollo + tzatziki", "Mercoledi": "burrito + tzatziki",
       "Giovedi": "greca + gamberi", "Venerdi": "manzo", "Sabato": "sgarro a cena", "Domenica": "legumi + pesce"}
ORD = ["colazione", "pranzo", "merenda", "cena"]

def sh(n):
    return SHORT.get(n, n.split("(")[0].split(",")[0].strip().lower())

def label(it):
    nm = sh(it["name"]); sv = it.get("servings")
    if nm in PLUR and sv:
        return f"{sv} {nm if sv == 1 else PLUR[nm]}"
    if "uova" in it["name"].lower() and sv:
        return "1 uovo" if sv == 1 else f"{sv} uova"
    low = it["name"].lower()
    if "tonno" in low and sv:
        return f"{nm} {sv} {'scatoletta' if sv == 1 else 'scatolette'}"
    if ("ceci" in low or "lenticchie" in low) and "scatola" in low and sv:
        return f"{nm} {sv} {'barattolo' if sv == 1 else 'barattoli'}"
    return f"{nm} {int(round(it['grams']))}g"

L = ["# Dieta Paolo — estiva, ricomposizione\n",
     "~2400 kcal/g · proteine ~150 · grassi ~67 (25%) · carbo ~300 · fibra >=30. Sabato 3 pasti ~1650 + cena sgarro.",
     "Pesi **a crudo**. Frutti grandi a pezzi. Verdura libera. Ogni giorno dal solver esatto sui dati CREA.\n"]
for day, r in d["week"].items():
    t = r["totals"]
    L.append(f"## {day} — {TAG[day]}")
    L.append(f"**{t['kcal']:.0f} kcal · P {t['protein_g']:.0f} · C {t['carb_g']:.0f} · G {t['fat_g']:.0f} · fibra {t['fiber_g']:.0f}**\n")
    for m in ORD:
        if m in r["by_meal"]:
            L.append(f"- **{m.capitalize()}**: " + ", ".join(label(x) for x in r["by_meal"][m]["items"]))
    if day == "Sabato":
        L.append("- **Cena**: sgarro libero (~700-800 kcal)")
    alt = r.get("cena_alt")
    if alt and alt.get("by_meal"):
        L.append(f"- **Alternativa cena** ({alt['label']}): " + ", ".join(label(x) for x in alt["by_meal"]["items"]))
    L.append("")
shop = d["shopping"]; bycat = {}
for n, g in shop.items():
    bycat.setdefault(DB.get(n, {}).get("category", "Altro"), []).append((n, g))
order = ["Carni fresche", "Prodotti della pesca", "Formaggi e latticini", "Latte e yogurt", "Uova",
         "Cereali e derivati", "Legumi", "Verdure e ortaggi", "Frutta", "Oli e grassi",
         "Frutta secca a guscio e semi oleaginosi", "Dolci"]
L.append("## Lista della spesa (settimana, a crudo)\n")
for c in order:
    if c in bycat:
        L.append(f"- **{c}**: " + ", ".join(
            (f"{sh(n)} {g/1000:.1f} kg" if g >= 1000 else f"{sh(n)} {int(g)} g")
            for n, g in sorted(bycat[c], key=lambda x: -x[1])))
L += ["\n## Note", "- Pesi a crudo: pasta, farro, couscous, carne e pesce. Ceci e lenticchie in scatola scolati (gia' cotti). Tonno sgocciolato; salumi/formaggi/feta come stanno.",
      "- Frutti grandi (banana, pesca) a numero, non a grammi.",
      "- Verdura libera: aumentala quanto vuoi.",
      "- Numeri piccoli di miele/mandorle/olio/olive sono condimenti, vanno bene piccoli.",
      "- Tzatziki (mar/mer): cetrioli + yogurt greco 0% + aglio, limone, menta.",
      "- Sodio: niente sale a tonno/feta/salumi; sciacqua tonno e legumi.",
      "- Taratura: 2 settimane di peso; stabile = ok; sale -> -150 kcal; scende -> +150."]
out = os.path.join(os.environ.get("DIETA_OUTDIR", os.path.expanduser("~/Desktop/dieta")), "dieta.md")
os.makedirs(os.path.dirname(out), exist_ok=True)
open(out, "w").write("\n".join(L))
print("scritto", out)
