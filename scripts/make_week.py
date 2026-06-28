#!/usr/bin/env python3
"""Esempio: piano 7 giorni (adatta foods e target alle preferenze dell'utente).
Grammi su griglia pratica, frutti grandi a pezzi, cibi in confezione a unita'.
Ogni giorno passa dal solver (solve_diet.solve). Output /tmp/week_plan.json."""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from solve_diet import solve

DB = {f["name"]: f for f in json.load(open(os.path.join(HERE, "..", "data", "foods.json")))["foods"]}

def F(name):
    if name in DB:
        return DB[name]
    cand = [n for n in DB if name.lower() in n.lower()]
    if not cand:
        raise SystemExit(f"NON TROVATO: '{name}'")
    cand.sort(key=len)
    return DB[cand[0]]

def step_for(name):
    n = name.lower()
    if "olio" in n:
        return 5
    if any(k in n for k in ["mandorl", "noci", "pistacch", "miele", "olive"]):
        return 5
    if "uova" in n:
        return 55  # 1 uovo
    # frutti grandi: enumerati a pezzi (serving = peso medio di 1 frutto)
    if "banane" in n or "banana" in n:
        return 120
    if "pesche" in n or "pesca" in n:
        return 150
    if n.startswith("mela") or "mele" in n:
        return 150
    if "arance" in n or "arancia" in n:
        return 200
    if n.startswith("pere") or n.startswith("pera"):
        return 170
    # cibi venduti a unita': tonno in scatoletta, legumi in barattolo -> a unita' intere
    if "tonno" in n:
        return 52    # 1 scatoletta al naturale sgocciolata (~52 g)
    if "ceci" in n and "scatola" in n:
        return 240   # 1 barattolo scolato (~240 g)
    if "lenticchie" in n and "scatola" in n:
        return 120   # 1/2 barattolo scolato
    if any(k in n for k in ["orata", "merluzzo", "nasello", "gamberi", "branzino", "spigola"]):
        return 25    # pesce (anche surgelato): grammature piu' tonde
    # verdure/patate passo 50; pane passo 50 (0 oppure >=50); avocado 25
    if "avocado" in n:
        return 25
    if "pane" in n:
        return 50
    if any(k in n for k in ["patate", "zucchin", "melanzan", "peperon", "pomodor",
                            "cetriol", "lattuga", "rucola", "fagiolin", "spinaci",
                            "carote", "insalata", "broccol", "finocch"]):
        return 50
    return 10

def item(name, meal, lo, hi, step=None):
    f = F(name)
    s = step if step else step_for(f["name"])
    return {"name": f["name"], "per100g": f["per100g"], "min_g": lo, "max_g": hi,
            "meal": meal, "integer": True, "serving_g": s}

T = {"kcal": 2400, "protein_g": 150, "fat_g": 67, "carb_g": 300, "fiber_g_min": 30}
MS = {"colazione": 0.25, "pranzo": 0.33, "merenda": 0.12, "cena": 0.30}
T_SAT = {"kcal": 1650, "protein_g": 105, "fat_g": 48, "carb_g": 205, "fiber_g_min": 22}
MS3 = {"colazione": 0.32, "pranzo": 0.45, "merenda": 0.23}

DAYS = [
("Lunedi", T, MS, [  # PESCE
  item("Latte di vacca, UHT, parzialmente scremato","colazione",250,300),
  item("Corn flakes","colazione",30,60),
  item("Miele","colazione",0,20),
  item("Banane, fresche","colazione",0,120),   # max 1 frutto
  item("Mandorle dolci, secche","colazione",0,15),
  item("Tonno in salamoia, sgocciolato","pranzo",120,150),
  item("Pasta di semola, integrale","pranzo",90,120),  # pasta fredda con tonno
  item("Pomodorini ciliegino, freschi","pranzo",150,260),
  item("Rucola o Ruchetta, fresca","pranzo",0,50),
  item("Olio di oliva extra vergine","pranzo",5,15),
  item("Yogurt greco, 0% lipidi","merenda",150,220),
  item("Pesche, fresche, con buccia","merenda",0,300),  # 1 solo frutto
  item("Orata, filetti","cena",160,230),
  item("Patate","cena",150,350),
  item("Zucchine, chiare","cena",0,250),
  item("Avocado, fresco","cena",0,80),               # fonte di grassi
  item("Olio di oliva extra vergine","cena",5,18),
]),  # cena: solo patate (no pane)
("Martedi", T, MS, [  # POLLO + TZATZIKI ; merenda salata
  item("Latte di vacca, UHT, parzialmente scremato","colazione",250,300),
  item("Corn flakes","colazione",30,60),
  item("Banane, fresche","colazione",0,120),
  item("Miele","colazione",0,20),
  item("Pollo, petto, crudo","pranzo",200,290),
  item("Pasta di semola","pranzo",100,120),
  item("Peperoni, crudi","pranzo",0,200),
  item("Olio di oliva extra vergine","pranzo",5,12),
  item("Cetrioli, freschi","pranzo",80,180),       # tzatziki
  item("Yogurt greco, 0% lipidi","pranzo",80,150),  # tzatziki
  item("Pane di tipo integrale","merenda",50,90),   # merenda salata (no yogurt)
  item("Ricotta di pecora","merenda",100,180),       # ricotta (basso sodio) al posto della bresaola
  item("Uova di gallina, intero","cena",110,165),
  item("Patate","cena",100,300),
  item("Lattuga, fresca","cena",0,150),
  item("Pomodori, da insalata, freschi","cena",50,200),
  item("Avocado, fresco","cena",0,60),
  item("Olio di oliva extra vergine","cena",0,8),
]),
("Mercoledi", T, MS, [  # BURRITO + TZATZIKI
  item("Latte di vacca, UHT, parzialmente scremato","colazione",250,300),
  item("Corn flakes","colazione",30,60),
  item("Miele","colazione",0,20),
  item("Banane, fresche","colazione",0,120),
  # BURRITO (ricetta dell'utente, quantita' quasi fisse)
  item("Piadina romagnola (da etichetta)","pranzo",100,120),
  item("Macinato di bovino magro (~5% grassi)","pranzo",180,200),
  item("Peperoni, crudi","pranzo",60,160),
  item("Cetrioli, freschi","pranzo",80,180),       # tzatziki
  item("Yogurt greco, 0% lipidi","pranzo",80,150),  # tzatziki
  item("Olio di oliva extra vergine","pranzo",5,15),
  item("Yogurt greco, 0% lipidi","merenda",150,220),
  item("Uva, fresca","merenda",0,150),              # 1 solo frutto
  item("Merluzzo o nasello","cena",160,280),
  item("Pasta di semola, integrale","cena",80,120),
  item("Patate","cena",0,250),
  item("Fagiolini, freschi","cena",0,200),
  item("Olio di oliva extra vergine","cena",5,18),
]),  # cena: pasta + eventuali patate (no pane)
("Giovedi", T, MS, [  # GRECA + GAMBERI ; merenda salata
  item("Latte di vacca, UHT, parzialmente scremato","colazione",250,300),
  item("Corn flakes","colazione",30,60),
  item("Banane, fresche","colazione",0,120),
  item("Noci, secche","colazione",0,12),
  # INSALATA GRECA
  item("Feta","pranzo",70,110),
  item("Tonno in salamoia, sgocciolato","pranzo",60,120),
  item("Pomodori, da insalata, freschi","pranzo",150,300),
  item("Cetrioli, freschi","pranzo",100,220),
  item("Olive, nere","pranzo",10,25),
  item("Olio di oliva extra vergine","pranzo",4,12),
  item("Pane di tipo integrale","pranzo",50,120),
  item("Pane di tipo integrale","merenda",50,90),   # merenda salata
  item("Uova di gallina, intero","merenda",110,165),  # uova sode (basso sodio) al posto del prosciutto
  item("Gamberi sgusciati, surgelati","cena",180,280),
  item("Pasta di semola","cena",80,120),
  item("Zucchine, chiare","cena",0,250),
  item("Pomodorini ciliegino, freschi","cena",0,150),
  item("Olio di oliva extra vergine","cena",6,16),
]),
("Venerdi", T, MS, [  # MANZO: pranzo tagliata+patate, cena pasta
  item("Latte di vacca, UHT, parzialmente scremato","colazione",250,300),
  item("Corn flakes","colazione",30,60),
  item("Miele","colazione",0,20),
  item("Banane, fresche","colazione",0,120),
  item("Mandorle dolci, secche","colazione",0,12),
  item("Bovino adulto o vitellone, costata, crudo","pranzo",170,240),
  item("Patate","pranzo",200,400),                  # tagliata + patate (no pasta/pane)
  item("Rucola o Ruchetta, fresca","pranzo",0,50),
  item("Pomodori, da insalata, freschi","pranzo",0,150),
  item("Olio di oliva extra vergine","pranzo",3,10),
  item("Yogurt greco, 0% lipidi","merenda",150,220),
  item("Albicocche, fresche","merenda",0,300),      # 1 solo frutto
  item("Pasta di semola, integrale","cena",80,120), # cena: pasta al posto del pane
  item("Bresaola della Valtellina IGP","cena",60,100),
  item("Mozzarella di vacca","cena",40,80),
  item("Pomodori, da insalata, freschi","cena",100,250),
  item("Olio di oliva extra vergine","cena",0,6),
]),
("Sabato", T_SAT, MS3, [  # sgarro a cena ; pranzo con pasta
  item("Latte di vacca, UHT, parzialmente scremato","colazione",250,300),
  item("Corn flakes","colazione",30,60),
  item("Banane, fresche","colazione",0,120),
  item("Pasta di semola, integrale","pranzo",80,120),  # pasta integrale (piu' fibra), al posto del pane
  item("Prosciutto crudo di Parma DOP, sgrassato","pranzo",80,120),
  item("Mozzarella di vacca","pranzo",70,130),
  item("Pomodori, da insalata, freschi","pranzo",150,250),
  item("Cetrioli, freschi","pranzo",100,200),
  item("Rucola o Ruchetta, fresca","pranzo",0,50),
  item("Olio di oliva extra vergine","pranzo",5,12),
  item("Cocomero, fresco","merenda",200,500),       # 1 solo frutto
]),
("Domenica", T, MS, [  # LEGUMI (solo ceci) + pesce ; merenda salata
  item("Latte di vacca, UHT, parzialmente scremato","colazione",250,300),
  item("Corn flakes","colazione",30,60),
  item("Miele","colazione",0,20),
  item("Pesche, fresche, con buccia","colazione",0,150),  # max 1 frutto
  # insalata fredda di ceci e tonno (solo ceci, no lenticchie)
  item("Ceci, in scatola, scolati","pranzo",240,240),  # 1 barattolo scolato
  item("Tonno in salamoia, sgocciolato","pranzo",52,160),  # 1-3 scatolette
  item("Pomodori, da insalata, freschi","pranzo",100,250),
  item("Cetrioli, freschi","pranzo",0,150),
  item("Avocado, fresco","pranzo",0,90),
  item("Olio di oliva extra vergine","pranzo",5,20),
  item("Pane di tipo integrale","merenda",50,90),    # merenda salata
  item("Ricotta di pecora","merenda",100,180),        # ricotta (basso sodio) al posto del salmone
  item("Orata, filetti","cena",150,240),
  item("Pasta di semola","cena",80,120),
  item("Patate","cena",0,250),
  item("Melanzane, cotte, in padella","cena",0,200),
  item("Olio di oliva extra vergine","cena",5,20),
]),  # cena: pasta + eventuali patate (no pane)
]

# Cene alternative (intercambiabili): stessi macro, l'utente sceglie A o B
ALT_CENA = {
  "Giovedi": ("Shrimp & mango salad", [   # in alternativa a gamberi+zucchine
    item("Gamberi sgusciati, surgelati","cena",180,280),
    item("Pasta di semola","cena",80,120),
    item("Mango, fresco","cena",80,180),
    item("Cipolle, crude","cena",20,60),
    item("Pomodori, da insalata, freschi","cena",100,250),
    item("Avocado, fresco","cena",0,90),  # opzionale
    item("Olio di oliva extra vergine","cena",5,15),
  ]),
}

def run():
    week, shopping = {}, {}
    for dayname, tgt, ms, foods in DAYS:
        spec = {"targets": tgt, "tolerance": {"kcal": 0.06, "macro": 0.12},
                "meals": ms, "foods": foods}
        r = solve(spec)
        week[dayname] = r
        for it in r.get("plan", []):
            shopping[it["name"]] = round(shopping.get(it["name"], 0) + it["grams"], 0)
        # cena alternativa: ri-solve il giorno con la cena B, salva solo la cena
        if dayname in ALT_CENA:
            altlabel, altcena = ALT_CENA[dayname]
            altfoods = [f for f in foods if f["meal"] != "cena"] + altcena
            ralt = solve({"targets": tgt, "tolerance": {"kcal": 0.06, "macro": 0.12},
                          "meals": ms, "foods": altfoods})
            week[dayname]["cena_alt"] = {"label": altlabel,
                                         "by_meal": ralt["by_meal"].get("cena"),
                                         "status": ralt["status"],
                                         "totals": ralt["totals"]}
        t = r["totals"]
        fib = r["deviations"].get("fiber_g", {})
        pct = round((t['fat_g'] * 9) / t['kcal'] * 100) if t['kcal'] else 0
        print(f"{dayname:10} [{r['status']:20}] kcal {t['kcal']:>6} | P {t['protein_g']:>5} C {t['carb_g']:>5} G {t['fat_g']:>5} ({pct}% gr) | fib {t['fiber_g']:>4}"
              + (f"  <fibra {fib.get('got')}/{fib.get('target_min')}>" if fib and not fib.get('within_tolerance') else ""))
    json.dump({"week": week, "shopping": shopping}, open("/tmp/week_plan.json", "w"), ensure_ascii=False, indent=2)
    print("\nsalvato /tmp/week_plan.json")

if __name__ == "__main__":
    run()
