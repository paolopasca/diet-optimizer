# Database alimenti

Il database `foods.json` **non è incluso** nel repository: contiene i valori
nutrizionali delle tabelle CREA, che non ridistribuiamo. Lo generi tu in locale.

## Generarlo

```bash
python3 scripts/build_db_from_crea.py
```

Lo script scarica le schede da [alimentinutrizione.it](https://www.alimentinutrizione.it)
(con cache locale in `/tmp/crea_cache/` e una pausa tra le richieste, sii
rispettoso del server), parsa i valori per 100 g e scrive `data/foods.json`
(~832 alimenti italiani). Per rigenerarlo da zero: `--refresh`.

## Cosa c'è già nel repo

- `foods_extra.json` — alimenti NON CREA (prodotti commerciali / ricette
  personali, es. piadina e macinato magro) con valori **da etichetta tipica**,
  stimati. Vengono uniti automaticamente a `foods.json` dal builder. Sostituisci
  con i valori del tuo brand se vuoi precisione.

## Schema di `foods.json`

```json
{
  "count": 834,
  "foods": [
    {"name": "Pollo, petto, crudo", "category": "Carni fresche",
     "crea_id": "...", "per100g": {"kcal":100,"protein_g":23.3,"carb_g":0,"fat_g":0.8,"fiber_g":0}}
  ]
}
```

Il `crea_id` permette di risalire alla scheda originale (anche per dati non in
`foods.json`, es. il sodio: vedi le note sul sodio in `SKILL.md`).
