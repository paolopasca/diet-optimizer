#!/usr/bin/env python3
"""
build_db_from_crea.py — costruisce data/foods.json dalle tabelle CREA ufficiali.

Fonte: https://www.alimentinutrizione.it (Tabelle di Composizione degli Alimenti,
CREA, ex INRAN). Valori per 100 g di parte edibile. Scarica le schede una volta e
le mette in cache locale, poi parsa i nutrienti. NON inventa nulla: ogni numero
viene dalla scheda CREA corrispondente (campo crea_id per tracciabilita').

Uso:
    python3 build_db_from_crea.py                 # usa cache, scarica i mancanti
    python3 build_db_from_crea.py --refresh       # riscarica tutto

Rigenera data/foods.json. Lo schema resta compatibile con solve_diet.py:
ogni voce ha name, category, per100g{kcal,protein_g,carb_g,fat_g,fiber_g}.
"""
import re, os, sys, json, time, html, urllib.request

BASE = "https://www.alimentinutrizione.it"
LIST_URL = BASE + "/tabelle-nutrizionali/ricerca-per-categoria"
DETAIL = BASE + "/tabelle-nutrizionali/%s"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "data", "foods.json")
CACHE = os.path.join("/tmp", "crea_cache")
UA = {"User-Agent": "Mozilla/5.0 (dieta DB build)"}

CATMAP = {
    "01": "Cereali e derivati", "02": "Legumi", "03": "Verdure e ortaggi",
    "04": "Frutta", "05": "Frutta secca a guscio e semi oleaginosi",
    "06": "Carni fresche", "07": "Carni trasformate e conservate",
    "08": "Fast-food a base di carne", "09": "Frattaglie",
    "10": "Prodotti della pesca", "11": "Latte e yogurt",
    "12": "Formaggi e latticini", "13": "Uova", "14": "Oli e grassi",
    "15": "Dolci", "16": "Prodotti vari", "17": "Bevande alcoliche",
    "18": "Alimenti Etnici", "19": "Ricette Italiane", "20": "Alimenti Tradizionali",
}


def fetch(url, retries=3):
    for k in range(retries):
        try:
            req = urllib.request.Request(url, headers=UA)
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.read().decode("utf-8", "replace")
        except Exception as e:
            if k == retries - 1:
                raise
            time.sleep(1.0 + k)


def clean_name(s):
    s = html.unescape(re.sub(r"\s+", " ", s)).strip()
    # artefatti tipo  "|Caramelle tipo ""mou""|"
    s = s.strip('"').strip("|").strip()
    s = s.replace('""', '"')
    return s


def num(label, h):
    # cella valore: "353&nbsp;" oppure "tr&nbsp;" (tracce = trascurabile -> 0.0)
    m = re.search(r"<td[^>]*>" + re.escape(label) +
                  r"</td><td>[^<]*</td><td>\s*([^<&]+)", h)
    if not m:
        return None
    v = m.group(1).strip()
    if v.lower() in ("tr", "tracce"):
        return 0.0
    try:
        return float(v.replace(",", "."))
    except ValueError:
        return None


def main():
    refresh = "--refresh" in sys.argv
    os.makedirs(CACHE, exist_ok=True)

    cat_html = fetch(LIST_URL)
    rows = re.findall(
        r'href="/tabelle-nutrizionali/(\d{6})">\s*(.*?)\s*<span class="categoria">(\d{2})?</span>',
        cat_html, re.S)
    # dedup mantenendo l'ordine
    seen, items = set(), []
    for fid, name, cat in rows:
        if fid in seen:
            continue
        seen.add(fid)
        items.append((fid, clean_name(name), CATMAP.get(cat, "Altro")))
    print(f"alimenti in elenco: {len(items)}", flush=True)

    foods, missing = [], []
    for i, (fid, name, cat) in enumerate(items, 1):
        cp = os.path.join(CACHE, fid + ".html")
        if refresh or not (os.path.exists(cp) and os.path.getsize(cp) > 2000):
            try:
                h = fetch(DETAIL % fid)
            except Exception as e:
                missing.append((fid, name, f"fetch fail: {e}"))
                continue
            with open(cp, "w", encoding="utf-8") as f:
                f.write(h)
            time.sleep(0.2)
        else:
            h = open(cp, encoding="utf-8", errors="replace").read()

        kcal = num("Energia (kcal)", h)
        prot = num("Proteine (g)", h)
        fat = num("Lipidi (g)", h)
        carb = num("Carboidrati disponibili (g)", h)
        fiber = num("Fibra totale (g)", h)
        if kcal is None or prot is None or carb is None or fat is None:
            missing.append((fid, name, f"valori mancanti k={kcal} p={prot} c={carb} f={fat}"))
            continue
        foods.append({
            "name": name, "category": cat, "crea_id": fid,
            "per100g": {"kcal": kcal, "protein_g": prot, "carb_g": carb,
                        "fat_g": fat, "fiber_g": fiber if fiber is not None else 0.0},
        })
        if i % 100 == 0:
            print(f"  {i}/{len(items)} processati, {len(foods)} ok", flush=True)

    # unisci alimenti extra (non-CREA: prodotti commerciali, ricette personali)
    extra_path = os.path.join(HERE, "..", "data", "foods_extra.json")
    n_extra = 0
    if os.path.exists(extra_path):
        try:
            ex = json.load(open(extra_path, encoding="utf-8"))
            for e in ex.get("foods", []):
                foods.append(e)
                n_extra += 1
            print(f"  + {n_extra} alimenti extra da foods_extra.json")
        except Exception as ex_e:
            print(f"  (foods_extra.json non caricato: {ex_e})")

    out = {
        "source": "Tabelle di Composizione degli Alimenti CREA (alimentinutrizione.it), "
                  "valori per 100 g di parte edibile. Importato da build_db_from_crea.py. "
                  "Eventuali alimenti non-CREA arrivano da foods_extra.json.",
        "note": "Ogni voce ha crea_id per tracciabilita'. I numeri vengono dalla scheda "
                "CREA, non da stime. Per alimenti non presenti vedi references/formulation.md.",
        "schema": "name, category, crea_id, per100g{kcal,protein_g,carb_g,fat_g,fiber_g}",
        "count": len(foods),
        "foods": foods,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"\nSCRITTO {OUT}")
    print(f"  alimenti validi: {len(foods)}")
    print(f"  scartati (valori incompleti o fetch fail): {len(missing)}")
    if missing:
        with open(os.path.join(CACHE, "missing.txt"), "w", encoding="utf-8") as f:
            for m in missing:
                f.write(f"{m[0]}\t{m[1]}\t{m[2]}\n")
        print("  lista scartati: /tmp/crea_cache/missing.txt")
        for m in missing[:8]:
            print("   -", m[0], m[1], "|", m[2])


if __name__ == "__main__":
    main()
