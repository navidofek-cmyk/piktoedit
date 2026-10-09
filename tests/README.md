# Zkousky

Zkousky bezi bez zobrazeni okna (`QT_QPA_PLATFORM=offscreen`) a editor
ovladaji **skutecnymi udalostmi mysi** - stisk, pohyb, pusteni. Diky tomu
prochazi i vyber nastroje, prichytavani a rozhodovani podle toho, kam se
kliklo, ne jen vypocty uvnitr. Vetsina chyb, ktere se v editoru nasly,
byla prave v teto vrstve a na primem volani funkci by nebyla videt.

## Spusteni

```powershell
./spustit_testy.ps1              # vsechny sady, kolem 17 s
./spustit_testy.ps1 --rychle     # bez nahodne zkousky
./spustit_testy.ps1 nuz          # jen sady s "nuz" v nazvu
```

Nebo primo:

```powershell
python tests\vse.py
python tests\nuz.py              # jedna sada, s podrobnym vypisem
python tests\nuz_nahodne.py 7 500   # jiny zarodek a pocet kol
```

Navratovy kod je pocet sad, ktere neprosly, takze to jde zaradit do
dalsiho skriptu.

## Co je kde

| Soubor | Co zkousi |
|---|---|
| `spolecne.py` | spolecny zaklad: okno, udalosti mysi, nastroje, kontroly |
| `zaklad.py` | SVG tam a zpet, parser cest, sablony a jejich dily, popisek, vypln, zive upravy v panelu |
| `prevod.py` | prevod tvaru na krivku a navazna uprava uzlu |
| `mys.py` | kresleni tuzkou a rez pres udalosti mysi vcetne cuknuti ruky |
| `guma.py` | guma na care, vyplni, tahu, pri priblizeni, na otocenem tvaru, text, zpet |
| `nuz.py` | zakladni rezani: kusy, kolecko, obdelnik, Shift, tazeni, zoom, bezier |
| `nuz_okrajove.py` | vlastni krizeni tahu, klik u pruseciku, T spoje, klik vedle |
| `nuz_spoje.py` | spoj typu Y pro ruzne husty tah a ruzne presahy |
| `nuz_znovu.py` | rezani kusu, ktery sam vznikl predchozim rezem |
| `nuz_uhly.py` | uhel krizeni 10 az 45 stupnu, krizeni u konce tahu, nedojeta hrana |
| `nuz_nahodne.py` | nahodne kresby; overuje, ze zmizel prave kus pod kurzorem, ze se nezmenil jiny tah a ze nezustal drobek |

## Jak pridat zkousku

```python
"""Co se zkousi."""

from spolecne import *

app, window, view = start()

case("popis pripadu")          # zalozi prazdnou kresbu
add(LineShape(QLineF(100, 500, 900, 500), TAH, "cara"))
knife(QPointF(500, 500))       # klik nozem vcetne cuknuti ruky
check("neco plati", podminka, "podrobnost do vypisu")

raise SystemExit(summary())
```

Novou sadu pak staci dopsat do seznamu `SUITES` v `vse.py`.

Uzitecne pomucky ze `spolecne.py`: `pencil`, `knife`, `knife_drag`, `erase`,
`click`, `drag`, `double_click`, `named`, `covered`, `spans`, `parts`,
`nearest_gap`, `path_length`, `straight`, `wobbly`, `render`.

## Nahodna zkouska

`nuz_nahodne.py` generuje kresby s nahodnou tloustkou tahu, zvlnenim,
poctem reznych hran i mistem kliknuti. Prvni beh teto zkousky nasel
13 chyb z 220 kol; dnes prochazi. Kdyz se neco rozbije, vypise zarodek
a cislo kola, takze se pripad da zopakovat:

```powershell
python tests\nuz_nahodne.py 20261005 200
```
