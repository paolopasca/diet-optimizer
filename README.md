# dieta — pianifica la dieta come problema di ottimizzazione

Skill per [Claude Code](https://docs.claude.com/en/docs/claude-code) (ma gli
script girano anche da soli) che costruisce piani alimentari trattandoli come un
**problema di ricerca operativa risolto da un solver esatto**, invece di lasciare
all'LLM il calcolo dei grammi.

## L'idea

Un LLM non sa fare constraint satisfaction su molti cibi: se scrive "dieta da
2400 kcal, 150 g di proteine" a mano, la riga dei totali **sembra** giusta ma non
somma. È un'allucinazione travestita da precisione.

Qui i due lavori sono separati:

- **L'LLM sceglie i cibi** (capisce le preferenze, monta i pasti, li mappa al DB).
- **Il solver calcola i grammi esatti** che centrano kcal e macro (LP/MILP con
  `scipy`/HiGHS, ottimo certificato).

I numeri vengono da un **database nutrizionale** (tabelle CREA), non dalla memoria
del modello. Risultato: porzioni che sommano davvero, in numeri pesabili.

## Setup

```bash
pip install -r requirements.txt
python3 scripts/build_db_from_crea.py     # genera data/foods.json (~832 alimenti CREA)
```

Il database non è nel repo (non ridistribuiamo i dati CREA): lo generi tu in
locale. Vedi [data/README.md](data/README.md).

## Come funziona (pipeline)

```
input utente → targets.py → scegli i cibi dal DB → solve_diet.py → presenta
   (BMR/obiettivo) (kcal+macro)   (spec con pasti e bound)  (grammi esatti)
```

1. **Target** (deterministici):
   ```bash
   python3 scripts/targets.py --bmr 1750 --activity moderato --goal mantenimento --weight 70
   ```
2. **Costruisci lo spec** (quali cibi, in che pasto, con che bound) e **risolvi**:
   ```bash
   echo '{"targets":{"kcal":2400,"protein_g":150,"carb_g":300,"fat_g":67},
          "foods":[ ... ]}' | python3 scripts/solve_diet.py
   ```
   Schema completo in testa a `scripts/solve_diet.py` e in
   [references/formulation.md](references/formulation.md).
3. **Piano settimanale + deck**: `scripts/make_week.py` è un esempio di piano 7
   giorni (ogni giorno passa dal solver). Poi:
   ```bash
   python3 scripts/make_week.py                 # -> /tmp/week_plan.json
   python3 scripts/fetch_images.py              # foto cibo (Unsplash, libere)
   python3 scripts/make_pptx.py                 # -> deck PowerPoint
   python3 scripts/make_md.py                   # -> versione markdown
   # PDF: soffice --headless --convert-to pdf <file>.pptx
   ```

## Principi (perché i numeri sono usabili)

- **Niente conti a mano**: il modello non ricalcola né arrotonda l'output del
  solver, lo presenta così com'è.
- **Numeri pesabili**: tutto su griglia (olio/frutta secca a 5 g, resto a 10 g).
  Uova e frutti grandi a **pezzi** ("2 pesche"). Tonno in **scatolette**, legumi
  in **barattoli**, verdure/pane a passo grande (mai porzioni-residuo da 10 g).
- **Pesi coerenti**: a crudo pasta/cereali/carne/pesce; legumi e tonno in scatola
  pesati da confezione (già cotti/sgocciolati).
- **Vincoli soft**: il solver non va mai in "infeasible", dà sempre il miglior
  compromesso e segnala gli scostamenti.

Le regole su realismo, varietà, sodio e presentazione sono in
[SKILL.md](SKILL.md) (è anche il prompt che guida l'agente).

## Struttura

```
SKILL.md                 istruzioni per l'agente + regole
scripts/
  solve_diet.py          il solver (LP/MILP, scipy/HiGHS)
  targets.py             BMR/TDEE + obiettivo -> kcal/macro
  build_db_from_crea.py  genera data/foods.json dalle tabelle CREA
  make_week.py           esempio: piano 7 giorni
  make_pptx.py           genera il deck PowerPoint
  make_md.py             genera la versione markdown
  fetch_images.py        scarica le foto (Unsplash)
data/
  foods_extra.json       alimenti non-CREA (piadina, macinato): valori stimati
  README.md              come generare foods.json
references/formulation.md matematica, schema, parametri
```

## Dati e licenza

Codice sotto licenza MIT (vedi [LICENSE](LICENSE)). I valori nutrizionali sono
del **CREA** (Centro di ricerca Alimenti e Nutrizione,
[alimentinutrizione.it](https://www.alimentinutrizione.it)) e **non** sono
inclusi nel repo: l'utente li genera in locale ed è responsabile del rispetto
dei termini della fonte.

## Disclaimer

Strumento informativo, non consulenza medica. Per patologie, gravidanza o
obiettivi clinici, rivolgiti a un medico o a un dietista.
