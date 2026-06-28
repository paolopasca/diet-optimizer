# Formulazione, schema e personalizzazione

Riferimento di dettaglio per `dieta`. Leggilo quando devi capire la
matematica, tarare i parametri, gestire casi difficili, o espandere il DB.

## Indice
1. Il modello di ottimizzazione
2. Gestione dell'infeasibility
3. Schema completo dello spec (input di `solve_diet.py`)
4. Output di `solve_diet.py`
5. `targets.py`: formule e flag
6. Espandere il database alimenti
7. Pattern utili

---

## 1. Il modello di ottimizzazione

Forma "robusta" del diet problem: i cibi sono fissati a monte, le variabili
decisionali sono solo le **quantità**.

Variabili: `x_i` = quantità del cibo *i*. Continua (grammi) di default, intera
(porzioni) se `integer: true`; in quel caso `grammi = x_i * serving_g`.

Per ogni cibo conosciamo il contributo per unità di nutriente *m*
(`a_{m,i}`, da `per100g`). Per ogni nutriente con target `t_m`:

    somma_i a_{m,i} * x_i  +  s⁻_m  −  s⁺_m  =  t_m

dove `s⁺_m, s⁻_m ≥ 0` sono gli scostamenti (sopra/sotto il target). I vincoli
sui nutrienti sono quindi **soft**: il modello li centra se può, altrimenti
minimizza lo scostamento. I bound fisici `min_g ≤ x_i ≤ max_g` sono invece
**hard** (sono gli unici vincoli rigidi).

Obiettivo (minimizzare):

    Σ_m  w_m · (s⁺_m + s⁻_m)   [+ 0.001 · costo  se objective = "cost"]

Pesi `w_m`, scelti per rendere i nutrienti comparabili e per tenere le kcal più
strette dei macro:

- kcal: peso 3 (per kcal di scostamento);
- proteine/carbo: peso 4; grassi: peso 9 — cioè ogni grammo di macro è pesato
  in **kcal-equivalente** (4/4/9 kcal/g), così uno scostamento di 1 g di grasso
  conta come 9 di kcal. Questo evita che il solver sacrifichi sistematicamente il
  macro con i numeri più piccoli.

Vincoli aggiuntivi:

- **Fibra minima**: minimo **soft**, penalizza solo lo scarto sotto
  `fiber_g_min` (l'eccesso è libero). Non causa infeasibility: il solver dà
  comunque un piano e riporta lo scarto in `deviations.fiber_g` e nei
  `suggestions`. Non fa fallire `within_tolerance` (resta legato a kcal e macro).
- **Bilanciamento pasti** (se `meals` è presente): per ogni pasto con quota
  `share`, le sue kcal sono un termine soft verso `share · kcal_target`
  (peso 0.5, basso: è una preferenza, non un dogma). Le quote dovrebbero
  sommare ~1.

Solver: `scipy.optimize.linprog(method="highs")`. LP se tutte le `x_i` sono
continue, **MILP** (HiGHS branch-and-bound) se almeno una è intera. Esatto e
deterministico: stesso input → stesso output.

### Perché HiGHS e non CP-SAT o Hexaly
Questo è un LP convesso piccolo (~10-50 variabili continue, vincoli lineari).
Per questa classe il solver exact LP/MILP è il fit corretto: dà l'**ottimo
globale certificato** senza arrotondamenti sui coefficienti, è gratuito e
portabile (zero licenze, scipy è già richiesto).
- **CP-SAT** (OR-Tools) lavora su interi: useresti grammi discreti e
  coefficienti nutrizionali scalati a interi → arrotondamenti sui dati, proprio
  ciò che questa skill vuole evitare. La sua forza (propagazione, learning) è
  inutile su un poliedro convesso.
- **Hexaly** è local-search commerciale per problemi grossi/non-convessi: non
  certifica l'ottimo globale di default e richiede licenza. Overkill qui.

**Quando migrare a CP-SAT**: solo se il modello acquisisce vincoli combinatori
duri (es. "esattamente N cibi per pasto", "non ripetere lo stesso secondo per 2
giorni", "minimizza il numero di prodotti distinti", logica if-then sui cibi).
Lì il combinatorio domina e CP-SAT batte un MILP con binarie + big-M. Finché il
problema resta "scegli i grammi", HiGHS è la scelta giusta.

### Perché soft e non hard sui macro
Con vincoli hard su kcal *e* tre macro *e* bound stretti, il poliedro è quasi
sempre vuoto → "infeasible" e nessun piano. I vincoli soft garantiscono che esca
**sempre** il miglior compromesso, con la misura esatta di quanto si è lontani
(`deviations`). La tolleranza decide solo se chiamarlo `ok` o
`ok_out_of_tolerance`; non cambia la soluzione.

---

## 2. Gestione dell'infeasibility

Tutti i nutrienti (kcal, macro, fibra) sono soft, quindi con bound validi il
solver **non ritorna mai `infeasible`**: dà sempre il miglior compromesso. L'unico
caso residuo di `infeasible` è un input malformato (es. `min_g > max_g` su un
cibo). In pratica vedrai sempre `ok` o `ok_out_of_tolerance`.

Più comune è `ok_out_of_tolerance`: soluzione trovata ma un target fuori banda.
Diagnosi nel campo `suggestions`. Mosse tipiche:

- **kcal troppo basse / un macro troppo basso**: manca capacità → alza qualche
  `max_g` o aggiungi un cibo ricco di quel nutriente.
- **kcal troppo alte**: i `min_g` forzano troppo cibo → abbassa qualche `min_g`.
- **grassi alti, proteine basse**: paniere sbilanciato → aggiungi una fonte
  proteica magra (albume, merluzzo, petto di pollo, yogurt greco).
- **carbo non centrati**: aggiungi/togli una fonte di carbo con range ampio.

Poi **rilancia il solver**. Non aggiustare i numeri a mano.

---

## 3. Schema completo dello spec

```jsonc
{
  "targets": {
    "kcal": 2200,           // obbligatorio
    "protein_g": 165,       // opzionali: se assenti, quel macro non è vincolato
    "carb_g": 220,
    "fat_g": 70,
    "fiber_g_min": 25       // opzionale: solo minimo
  },
  "tolerance": {            // opzionale; frazione del target
    "kcal": 0.03,           // default 0.03
    "macro": 0.07           // default 0.07
  },
  "objective": "balance",   // "balance" (default) | "cost" (richiede "cost" sui cibi)
  "meals": {                // opzionale: quota kcal per pasto (somma ~1)
    "colazione": 0.25, "pranzo": 0.40, "cena": 0.35
  },
  "foods": [
    {
      "name": "Petto di pollo",
      "per100g": {"kcal":100,"protein_g":23,"carb_g":0,"fat_g":1,"fiber_g":0},
      "min_g": 120,         // default 0
      "max_g": 300,         // default 1000
      "meal": "pranzo",     // opzionale
      "integer": false,     // opzionale
      "serving_g": 100,     // obbligatorio se integer:true
      "cost": null          // opzionale, costo per 100 g (per objective:"cost")
    }
  ]
}
```

Note:
- `fiber_g` nel `per100g` è opzionale (default 0); serve solo se usi
  `fiber_g_min`.
- Per le porzioni intere i bound `min_g/max_g` vengono convertiti in numero di
  porzioni (floor/ceil) — tienine conto: `max_g 360` con `serving_g 60` ⇒ max 6.

---

## 4. Output di `solve_diet.py`

```jsonc
{
  "status": "ok" | "ok_out_of_tolerance" | "infeasible" | "error",
  "within_tolerance": true,
  "totals": {"kcal":2200.0,"protein_g":165.0,"carb_g":220.0,"fat_g":70.0,"fiber_g":26.7},
  "deviations": {"kcal":{"target":2200,"got":2200,"diff":0,"pct":0,"within_tolerance":true}, ...},
  "by_meal": {"colazione":{"items":[...],"kcal":...,"protein_g":...}, ...},
  "plan": [{"name":"...","grams":...,"servings":...}],
  "suggestions": ["..."]   // popolato solo se fuori tolleranza
}
```

`totals`, `by_meal` e `plan` sono calcolati dal solver sui grammi scelti.
Presentali verbatim.

---

## 5. `targets.py`: formule e flag

```
TDEE   = BMR × fattore_attività          (oppure passato diretto con --tdee)
kcal   = TDEE × (1 + aggiustamento_obiettivo)
prot_g = peso × g/kg        (se --weight)   |   30% kcal / 4   (se manca il peso)
fat_g  = max(fat_pct × kcal / 9, 0.8 × peso)   (il minimo solo se c'è --weight)
carb_g = (kcal − prot_g×4 − fat_g×9) / 4
```

Fattori attività (sul BMR): sedentario 1.2, leggero 1.375, moderato 1.55,
intenso 1.725, atleta 1.9.
Aggiustamento obiettivo: definizione −20%, mantenimento 0, massa +10%.

Flag:
- `--bmr N` oppure `--tdee N` (uno dei due obbligatorio)
- `--activity {sedentario,leggero,moderato,intenso,atleta}` (default moderato)
- `--goal {definizione,mantenimento,massa}` (default mantenimento)
- `--weight KG` (consigliato)
- `--protein-per-kg` (default 1.8; range tipico 1.6–2.2)
- `--fat-pct` (default 0.25)
- `--fiber-min` (default 28)

Sono default ragionevoli per un adulto sano, non prescrizioni cliniche.

---

## 6. Il database alimenti

`data/foods.json` contiene **832 alimenti** importati dalle tabelle CREA
ufficiali (alimentinutrizione.it) tramite `scripts/build_db_from_crea.py`. Ogni
voce ha `name` (italiano), `category` (uno dei 20 gruppi CREA), `crea_id` per
tracciabilità, e `per100g`. Per rigenerarlo da zero:

```bash
python3 scripts/build_db_from_crea.py           # usa la cache in /tmp/crea_cache
python3 scripts/build_db_from_crea.py --refresh # riscarica tutte le schede
```

Il seed curato originale (48 voci con bound consigliati) resta in
`data/foods_seed_backup.json` come riferimento.

### Aggiungere alimenti non CREA
Se serve un cibo fuori dalle tabelle CREA (es. un prodotto di marca):

1. Prendi i valori da una fonte affidabile. Usa i valori per **100 g di parte
   edibile**, **crudo** salvo indicarlo nel nome (es. "Riso basmati (crudo)").
2. Aggiungi una voce con lo schema:
   ```json
   {"name":"...", "category":"...", "aliases":["..."],
    "per100g":{"kcal":0,"protein_g":0,"carb_g":0,"fat_g":0,"fiber_g":0},
    "typical_min_g":0, "typical_max_g":0}
   ```
3. Verifica che il file resti JSON valido:
   `python3 -c "import json; json.load(open('data/foods.json'))"`

Non aggiungere voci con valori non verificati. Meglio un DB piccolo e corretto
che grande e inventato.

---

## 7. Pattern utili

- **Solo proteine alte, kcal libere**: ometti `carb_g`/`fat_g` dai target,
  imposta `protein_g` e `kcal`. Il solver centra quei due e lascia liberi gli
  altri.
- **Vincolo di budget**: metti `cost` (€/100 g) sui cibi e `objective:"cost"`:
  tra le soluzioni che centrano i nutrienti, sceglie la più economica.
- **Pochi pasti / spuntini**: aggiungi voci `meal:"spuntino"` e una quota in
  `meals`.
- **"Voglio almeno X g di verdura"**: dai `min_g` alto a una verdura, o più
  verdure con `min_g` ciascuna.
- **Test di sanità**: dopo ogni run controlla che `within_tolerance` sia true e
  che `by_meal` rispetti grosso modo le quote `meals`.
