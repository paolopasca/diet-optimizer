---
name: dieta
description: >-
  Costruisce e aggiusta piani alimentari trattandoli come un problema di
  ottimizzazione con un solver esatto (scipy/HiGHS): l'LLM sceglie i cibi, il
  solver calcola i grammi che centrano davvero kcal e macro, invece di numeri
  stimati a occhio che non sommano. USA questa skill quando l'utente vuole
  COSTRUIRE o MODIFICARE una dieta/piano alimentare, o calcolare le PORZIONI per
  raggiungere un obiettivo nutrizionale: "fammi la dieta", "piano alimentare",
  "meal plan", "dieta da 2000 kcal", "quanti grammi di X devo mangiare per fare
  N kcal/proteine", "dammi i macro della giornata", "menù per
  definizione/massa/palestra", "dieta settimanale", "ricalcola/aggiusta la mia
  dieta". Quando un piano deve centrare kcal o macro NON improvvisarlo a mano: i
  totali scritti senza solver quasi sempre non sommano e i valori nutrizionali a
  memoria sono imprecisi, passa sempre dal solver e dal database. NON usarla per
  semplici lookup ("quante calorie ha una mela", "quante proteine nel pollo") né
  per pareri generici sulle diete ("fa bene la chetogenica?"): lì rispondi
  normalmente, non c'è nessuna porzione da ottimizzare.
---

# Diet Optimizer

## Perché esiste

Un LLM non sa fare constraint satisfaction su molti cibi: se scrive un piano "da
2000 kcal, 150 g proteine" a mano, la riga dei totali sembra giusta ma **non
somma davvero**. È un'allucinazione mascherata da precisione.

Questa skill separa i due lavori:

- **L'LLM (tu) fa quello in cui è bravo**: capire le preferenze, scegliere cibi
  e ricette sensate, mapparli al database nutrizionale.
- **Il solver fa quello in cui è bravo**: dati i cibi scelti, calcolare i
  **grammi esatti** che centrano kcal e macro, rispettando i vincoli.

Il database dei valori nutrizionali è la fonte di verità (tabelle italiane
CREA). Niente web nei numeri: i numeri vengono solo dal DB.

## La regola dura (non negoziabile)

I `totals` e i grammi che escono da `solve_diet.py` sono **già esatti**.
Presentali così come sono. **Non ricalcolare le kcal a mano, non arrotondare i
macro, non "aggiustare" i grammi dopo.** Se rifai i conti tu, reintroduci
esattamente l'allucinazione che questa skill esiste per eliminare. Se qualcosa
non torna, cambia lo *spec* e **rilancia il solver**, non la matematica a penna.

## Pipeline

```
input utente ──> targets.py ──> scegli cibi dal DB ──> solve_diet.py ──> presenta
   (BMR,         (kcal+macro)     (costruisci spec       (grammi esatti)
   obiettivo)                      con pasti e bound)
```

Tutti gli script sono in `scripts/`. Eseguili con `python3`. Dipendenza unica:
`scipy` (+ numpy), già richiesta dal solver.

### Step 0 — Raccogli gli input

Servono, chiedendoli se mancano (non assumere):

- **Fabbisogno**: il BMR (kcal a riposo) **oppure** il TDEE se l'utente lo
  conosce già. Più il **livello di attività** (`sedentario|leggero|moderato|
  intenso|atleta`) e l'**obiettivo** (`definizione|mantenimento|massa`).
- **Peso in kg** (opzionale ma consigliato: serve per le proteine in g/kg).
- **Preferenze e vincoli**: cibi graditi/sgraditi, esclusioni (no maiale,
  vegetariano, no lattosio…), numero di pasti, eventuale budget.
- **Orizzonte**: un giorno singolo o più giorni con varietà.

### Step 1 — Calcola i target (deterministico)

```bash
python3 scripts/targets.py --bmr 1700 --activity moderato --goal definizione --weight 78
```

Se l'utente dà direttamente kcal+macro, **salta questo step** e usa i suoi
numeri. Se conosce il TDEE ma non il BMR, usa `--tdee 2600`. L'output contiene
il blocco `targets` pronto da incollare nello spec. Mostra all'utente la
derivazione (TDEE, aggiustamento obiettivo) così sa da dove vengono le kcal.

Default usati (modificabili da flag, vedi `references/formulation.md`):
proteine 1.8 g/kg, grassi 25% kcal (min 0.8 g/kg), carbo = resto, fibra ≥ 28 g.

### Step 2 — Scegli i cibi e costruisci lo spec

Apri `data/foods.json` (832 alimenti dalle tabelle CREA ufficiali, valori per
100 g, ognuno con `crea_id` e `category`). Cerca per nome (sono in italiano, es.
"Pollo, petto", "Salmone", "Riso brillato") e scegli un **paniere realistico**
coerente col prompt e con le preferenze, distribuito sui pasti. Per ogni cibo
copia il blocco `per100g` dal DB e aggiungi:

- `meal`: a quale pasto appartiene (per bilanciare la giornata);
- `min_g` / `max_g`: bound realistici che decidi tu (es. l'olio non deve
  esplodere a 200 g; una fonte proteica 100-300 g; verdura con `max_g` alto);
- `integer` + `serving_g`: solo se vuoi porzioni intere (es. uova).

**Crudo vs cotto**: il DB CREA ha spesso entrambe le versioni (es. "Riso,
brillato" e "Riso, brillato, cotto, bollito"). Scegli quella coerente con come
l'utente pesa il cibo e dillo nel piano. Default sensato: valori **crudi** per
ciò che si pesa da crudo (pasta, riso, legumi secchi) e indica "peso a crudo";
usa le versioni cotte solo se l'utente pesa il piatto pronto. Mischiarle falsa i
numeri anche se il solver è esatto.

Costruisci un file JSON `spec` (schema completo in cima a `scripts/solve_diet.py`
e in `references/formulation.md`). Forma minima:

```json
{
  "targets": { "...": "da targets.py o dall'utente" },
  "tolerance": {"kcal": 0.03, "macro": 0.07},
  "meals": {"colazione": 0.25, "pranzo": 0.40, "cena": 0.35},
  "foods": [
    {"name": "Petto di pollo", "per100g": {"kcal":100,"protein_g":23,"carb_g":0,"fat_g":1,"fiber_g":0}, "min_g":120, "max_g":300, "meal":"pranzo"}
  ]
}
```

**Scegli abbastanza leve.** Il solver decide solo i grammi: se dai pochi cibi o
bound troppo stretti, non riesce a centrare i target. Regola pratica: almeno una
fonte proteica, una di carbo e una di grassi *per pasto*, con range di grammi
ampi su almeno qualche cibo. Verdura a volontà (`max_g` alto) costa poche kcal e
aiuta la fibra.

**Numeri pratici (multipli di 5-10 g) e pezzi.** Una dieta con "olio 16,5 g" o
"patate 37 g" è infattibile da pesare. Metti ogni cibo su griglia con
`integer: true` + `serving_g` = passo pratico: olio e frutta secca a 5 g, tutto
il resto a 10 g. **Uova e frutti grandi (banana, pesca, mela, pera, arancia)**
vanno a PEZZI: `integer: true` con `serving_g` = peso medio di un pezzo (uovo
~55, banana ~120, pesca/mela ~150, pera ~170, arancia ~200) e si presentano a
numero ("2 pesche", "1 banana"), mai a grammi. Con tutto su griglia allarga le
tolleranze (kcal ±5-6%, macro ±10-12%): centri comunque i target con numeri
tondi. L'utente accetta una banda (es. 2300-2500 kcal), non serve l'esattezza al
grammo.

**Cibi venduti a confezione → unità intere.** Quello che si compra a unità non va
in grammi arbitrari ("2/3 di scatoletta" è inutile): tonno in scatoletta
(`serving_g` ~52, peso sgocciolato di una latta al naturale, mostra "N
scatolette"), legumi in barattolo (~240 g scolato, "N barattoli"). Verdure e
patate a passo 50 g, pane a 50 g (0 oppure ≥50, mai pezzetti). La **carne** resta
a grammi (si pesa). Coerenza pesi: a crudo pasta/cereali/carne/pesce fresco;
**tonno e legumi in scatola sono già cotti/sgocciolati** (peso preso dalla
confezione scolata), non a crudo.

### Step 3 — Risolvi

```bash
python3 scripts/solve_diet.py /tmp/spec.json --pretty
```

`--pretty` stampa una versione leggibile su stderr; lo stdout resta JSON. Leggi
il campo `status`:

- `ok` → i target sono centrati entro tolleranza. Presenta il piano.
- `ok_out_of_tolerance` → il solver ha trovato il miglior compromesso ma almeno
  un target è fuori banda. Leggi `deviations` e `suggestions`: di solito manca
  una leva (aggiungi un cibo ricco del macro mancante, allarga un `max_g`),
  modifica lo spec e **rilancia**. Non spacciarlo per centrato.
- `infeasible` / `error` → leggi `message`/`hint` e correggi lo spec.

### Step 4 — Presenta

Mostra il piano raggruppato per pasto (grammi per cibo) e la riga **TOTALE**
con kcal e macro **presi dall'output del solver**. Indica esplicitamente che i
totali sono garantiti dal solver. Se `status` non è `ok`, dillo e spiega cosa
manca.

## Realismo, preferenze e sodio

Il solver centra i numeri; tocca a te rendere il piano vivibile. Regole generali
(e ogni preferenza nuova dell'utente va aggiunta qui o nel paniere):

- **Frutta sostenibile**: a colazione max 1 frutto, a merenda un solo tipo di
  frutto. Non impilare 3-4 frutti in un giorno.
- **Niente doppio carbo voluminoso nello stesso pasto**: se c'è la patata non
  mettere anche il pane (scegline uno). Pasta + un po' di patate va bene;
  patate + pane no.
- **Pasta**: se l'utente la vuole spesso, mettila fino a ~1 volta al giorno, max
  ~120 g a crudo (d'estate spesso come pasta fredda, poca cucina).
- **Varia le merende**: non sempre yogurt. Alterna yogurt+frutta con merende
  salate (pane + una proteina). Per le merende salate preferisci proteine a
  **basso sodio (uova, ricotta)** invece di salumi/affumicati se il sodio della
  settimana è già alto.
- **Cottura minima** (estate): privilegia piatti freddi/già pronti (tonno,
  salumi magri, feta, mozzarella, legumi in scatola, insalate) e cotture rapide.
- **Alternative intercambiabili**: se l'utente vuole due versioni di un pasto,
  risolvi DUE volte la giornata cambiando solo quel pasto, ciascuna allo stesso
  target, così le opzioni sono davvero scambiabili. Vedi `cena_alt` in
  `make_week.py`.

**Sodio.** Il DB non contiene il sodio (solo kcal/macro/fibra), ma le schede CREA
in cache (`/tmp/crea_cache/<crea_id>.html`) sì: campo "Sodio (mg)". Se serve,
parsalo da lì e somma il sodio settimanale (sale g = sodio mg × 2.5 / 1000).
Riferimento WHO: <2000 mg sodio/giorno (5 g sale). Cibi salati da sorvegliare:
tonno in salamoia, feta, salumi, affumicati, formaggi, pane, legumi in scatola
(sciacquandoli ~−30-40%). Per un atleta sano normoteso il limite WHO è
conservativo: l'eccesso di sodio dà soprattutto ritenzione idrica estetica e
temporanea, non un rischio di salute. Per chi ha/sospetta ipertensione, basso.

## Piano settimanale e presentazione PPTX

Per una dieta su più giorni usa lo **stesso pattern deterministico** di
`scripts/make_week.py`: definisce i panieri per giorno, chiama `solve()` per
ognuno e aggrega la lista della spesa. Ogni giorno passa dal solver: **non
scrivere mai grammi o totali a mano**, nemmeno nel piano testuale.

Quando l'utente vuole un piano "bello" da tenere, genera un **PowerPoint** in
stile diet-template (sfondo crema, accenti verde/arancio, foto cibo) con
`scripts/make_pptx.py`. Deve contenere:

- una **slide per giorno** coi badge dei macro **precisi** (kcal, proteine,
  carboidrati, grassi) e i pasti (colazione/pranzo/merenda/cena) con le
  quantità: grammi tondi, e a pezzi per uova e frutti grandi;
- una slide **lista della spesa** aggregata per categoria (pesi a crudo);
- una slide **note** (pesi a crudo, frutti a pezzi, verdura libera, taratura).

Immagini: prendile dal web da fonti libere (Unsplash/Pexels/Wikimedia), **verifica
che scarichino come JPEG validi** prima di inserirle, e **abbinale al piatto
realmente mangiato** quel giorno (no pasta al pesto se quel giorno non c'è pesto).
I numeri nelle slide vengono SEMPRE da `/tmp/week_plan.json` (output del solver),
mai riscritti a mano.

Versione testo: `scripts/make_md.py` (markdown). Per il **PDF** converti il pptx
con LibreOffice headless:
`soffice --headless --convert-to pdf --outdir <dir> <file>.pptx`
(su macOS il binario è `/Applications/LibreOffice.app/Contents/MacOS/soffice`).
**Verifica** sempre il risultato aprendo qualche pagina del PDF prima di
consegnarlo (così controlli foto, impaginazione e refusi). Output in una cartella
dedicata (es. `~/Desktop/dieta/`).

## Cibi non presenti nel DB

Se l'utente vuole un cibo che non è in `data/foods.json`: **non inventare i
valori nutrizionali.** Hai due opzioni oneste:

1. cerca i valori CREA ufficiali e aggiungi la voce a `data/foods.json` (stesso
   schema), poi usala;
2. se non puoi verificarli, dillo all'utente e proponi il sostituto più simile
   già presente nel DB.

Inventare un `per100g` distrugge la garanzia anti-allucinazione anche se poi il
solver è esatto: garbage in, garbage out.

## Più giorni / varietà

Il solver lavora su una giornata. Per una settimana, costruisci spec diversi con
panieri diversi (ruota le fonti proteiche e i contorni) e risolvi ognuno. Non
chiedere al solver la varietà: è un vincolo che gestisci tu nella scelta dei
cibi, lui ottimizza i grammi del paniere che gli dai.

## Dettagli e personalizzazione

`references/formulation.md` copre: la matematica esatta (obiettivo, vincoli
soft/hard, come gestiamo l'infeasibility), tutti i flag di `targets.py`, lo
schema completo dello spec, e come espandere il database.

## Disclaimer

Questa skill produce stime nutrizionali a scopo informativo, non è consulenza
medica. Per patologie, gravidanza, o obiettivi clinici, l'utente deve sentire un
medico o un dietista. Dillo quando il contesto lo richiede.
