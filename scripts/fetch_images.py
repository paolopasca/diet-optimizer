#!/usr/bin/env python3
"""Scarica le foto cibo per il deck (make_pptx.py) da Unsplash (licenza libera).
Le salva in $DIETA_IMGDIR (default /tmp/dieta_img). Esegui prima di make_pptx.py.

NB: queste sono le immagini dell'esempio. Per un piano diverso, cambia le URL e
le chiavi in modo che combacino coi piatti realmente mangiati (vedi DAY_IMG in
make_pptx.py). Verifica sempre che ogni immagine corrisponda al cibo del giorno.
"""
import os, urllib.request

IMGDIR = os.environ.get("DIETA_IMGDIR", "/tmp/dieta_img")
IMG = {
    "hero":     "https://images.unsplash.com/photo-1490645935967-10de6ba17061",
    "fish":     "https://images.unsplash.com/photo-1467003909585-2f8a72700288",
    "chicken1": "https://images.unsplash.com/photo-1532550907401-a500c9a57435",
    "burrito":  "https://images.unsplash.com/photo-1626700051175-6818013e1d4f",
    "greek":    "https://images.unsplash.com/photo-1505253716362-afaea1d3d1af",
    "beef1":    "https://images.unsplash.com/photo-1546964124-0cce460f38ef",
    "caprese2": "https://images.unsplash.com/photo-1592417817098-8fd3d9eb14a5",
    "legumi":   "https://images.unsplash.com/photo-1515543237350-b3eea1ec8082",
    "veg":      "https://images.unsplash.com/photo-1512621776951-a57141f2eefd",
    "fruit":    "https://images.unsplash.com/photo-1502741224143-90386d7f8c82",
}


def main():
    os.makedirs(IMGDIR, exist_ok=True)
    ok = 0
    for k, base in IMG.items():
        url = base + "?w=1400&q=80&fm=jpg&fit=crop"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            data = urllib.request.urlopen(req, timeout=30).read()
            if data[:2] == b"\xff\xd8" and len(data) > 15000:
                open(os.path.join(IMGDIR, k + ".jpg"), "wb").write(data)
                ok += 1
                print(f"{k}: ok ({len(data)//1024} KB)")
            else:
                print(f"{k}: SCARTATO (non e' un JPEG valido)")
        except Exception as e:
            print(f"{k}: FALLITO {e}")
    print(f"\n{ok}/{len(IMG)} immagini in {IMGDIR}")


if __name__ == "__main__":
    main()
