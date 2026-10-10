# PiktoEdit

Vektorovy editor AAC a VOKS piktogramu. Kresli se primo do SVG, takze ulozeny
soubor je zaroven pracovni soubor. Ovladani je mix presneho kresleni (mrizka,
prichytavani, ciselne rozmery) a volneho kresleni jako v Malovani.

## Spusteni

Hotovy program je `dist\PiktoEdit.exe`. Bezi i na pocitaci bez Pythonu,
staci ho zkopirovat a spustit. Sablony si pri prvnim spusteni rozbali do
slozky `sablony\` vedle sebe, takze se daji doplnovat o vlastni.

Ze zdrojaku:

```powershell
python main.py
```

Nebo rovnou s otevrenim souboru:

```powershell
python main.py piktogramy\mama.svg
```

Potreba je Python 3.10+ a PySide6 (`pip install -r requirements.txt`).

## Zkousky

```powershell
./spustit_testy.ps1
```

Zkousky bezi bez zobrazeni okna a ovladaji editor skutecnymi udalostmi
mysi, takze overuji i vyber nastroje a prichytavani, ne jen vypocty
uvnitr. Deset sad probehne kolem sedmnacti sekund, jedna z nich generuje
nahodne kresby. Podrobnosti v `tests/README.md`.

### Sestaveni .exe

```powershell
./build_exe.ps1
```

Vola `python -m PyInstaller --noconfirm --clean PiktoEdit.spec` a vysledek
polozi do `dist\PiktoEdit.exe` (kolem 44 MB, jeden soubor). Nastaveni je
v `PiktoEdit.spec`; nepotrebne casti Qt (web, multimedia, databaze) jsou tam
vyrazene, aby soubor zbytecne nenarostl.

## K cemu to je

Sada fotorealistickych scen v `Documents\Codex` je dobra pro tisk kartiek,
ale pro aplikaci a pro VOKS se hodi ploche piktogramy: cerny obrys, plne
barvy, popisek pod obrazkem. Tenhle editor slouzi k jejich tvorbe, at uz
obkreslenim existujiciho obrazku, nebo kreslenim od nuly.

## Nastroje

| Klavesa | Nastroj | Poznamka |
|---|---|---|
| `V` | Sipka | vyber, posun, zmena velikosti, otaceni |
| `N` | Uzly | editace krivky po uzlech a ridicich ramenech |
| `L` | Cara | Shift drzi smer po 45° |
| `P` | Lomena cara | klikani bod po bodu, `Enter` ukonci, `Backspace` vrati bod |
| `G` | Mnohouhelnik | jako lomena cara, ale uzavrena a vyplnena |
| `K` | Krivka (pero) | klik = rohovy uzel, klik s tazenim = hladky uzel |
| `H` | Hladka krivka | krivka podle bodu, rezim se prepina v horni liste |
| `R` | Obdelnik | Shift drzi ctverec |
| `E` | Elipsa | Shift drzi kruh |
| `B` | Tuzka | volna ruka, body se automaticky zjednodusi |
| `F` | Kyblik | vypln tvaru i plochy mezi carami, Shift obrys, Alt naber barvu |
| `Z` | Nuz | rez krivky v krizeni, Shift jen rozdeli, tazeni reze carou |
| `X` | Guma | tahem odmaze cast tvaru, se Shiftem cely objekt |
| `T` | Text | klik vlozi text a rovnou ho da do editace |

Otaceni je kulatym uchytem nad vyberem, se Shiftem po 15°.
Dvojklik na text ho otevre k prepsani.

### Krivky a uzly

Nastrojem `N` se klikne na krivku a ukazou se jeji uzly:

- tazeni za uzel s nim pohne, tazeni za ridici rameno meni oblouk,
- dvojklik na krivku prida novy uzel presne v miste kliku,
- `Delete` vybrany uzel odebere,
- `S` z uzlu udela hladky (ramena se srovnaji do primky), `C` rohovy,
- Shift pri tazeni ramena drzi obe ramena symetricka.

Obdelnik, elipsu, caru i text jde na krivku prevest pres
`Objekt / Prevest na krivku` (`Ctrl+Shift+K`). Uzlovy nastroj to nabidne sam,
kdyz kliknete na tvar, ktery jeste krivka neni.

### Hladka krivka: dva rezimy

V horni liste se prepina, jak se maji zadane body pouzit:

- **prochazi body** - krivka jde presne zadanymi body (Catmull-Rom),
  vhodne pri obkreslovani predlohy,
- **body jen ridi (B-spline)** - uniformni kubicky B-spline, krivka je
  hladsi, ale body jsou jen ridici, jako u ridiciho polygonu.

Oboji se uklada jako bezne bezierove segmenty (`C` v atributu `d`), takze
soubor zustava obycejnym SVG. Prave NURBS s vahami a vlastnim uzlovym
vektorem to zatim neni.

## Orezani, napojeni, vypln

Menu `Objekt`:

| Prikaz | Klavesa | Co dela |
|---|---|---|
| Sjednotit | `Ctrl+Shift+U` | slouci vybrane tvary do jednoho |
| Odecist (orezat) | `Ctrl+Shift+O` | od spodniho tvaru odectene vsechny nad nim |
| Prunik | `Ctrl+Shift+I` | zustane jen spolecna cast |
| Vyloucit | `Ctrl+Shift+X` | zustane vse krome spolecne casti |
| Napojit krivky | `Ctrl+J` | spoji konce car a krivek do jedne |
| Uzavrit a vyplnit | `Ctrl+Shift+J` | uzavre krivku a da ji vypln |
| Prevest na krivku | `Ctrl+Shift+K` | z tvaru nebo textu udela editovatelnou krivku |

Napojeni bere konce, ktere lezi bliz nez 12 px. Pokud se nekolik casti spojit
nepodari, editor to napise ve stavovem radku. Kdyz po napojeni vyjde uzavrena
smycka, dostane rovnou vypln - to je ta cesta, jak z par car udelat plochu,
kterou lze vybarvit.

Guma pracuje dvema zpusoby podle toho, co maze:

- **vyplneny tvar** - vymazana plocha se od tvaru odectene,
- **cara bez vyplne** - cara se v miste gumy rozdeli na dva kusy.

Prumer gumy se nastavuje v horni liste. Se Shiftem guma maze cele objekty.

### Rezani krivek

Nuz (`Z`) resi to, cemu se v CADu rika oriznuti:

- **klik na krivku** - editor najde vsechna mista, kde se krivka krizi
  s jinymi, a odebere jen ten kousek, na ktery jste klikli,
- **Shift+klik** - krivku ve stejnem miste jen rozdeli a oba kusy nechá,
- **tazeni** - cara nozem rozrizne vsechno, co protne, v mistech pruniku,
- **klik na krivku bez krizeni** - krivka se rozdeli presne v miste kliknuti.

Rozrezane kusy zustavaji krivkami, takze na nich dal funguji uzly i napojeni.

### Kyblik a hranice vyplne

Kyblik (`F`) zkousi tri veci v tomhle poradi:

1. **Klik na tvar** - prebarvi jeho vypln. Tim se meni to, co uz vyplnene je.
2. **Klik dovnitr uzavreneho tvaru bez vyplne** - tvar se najde podle obrysu
   a dostane vypln. Vysledek zustava jeden objekt, zadny novy nevznika.
3. **Klik do plochy ohranicene vice samostatnymi carami** - tam uz zadny
   jeden tvar neexistuje, takze editor kresbu vykresli do pomocneho rastru,
   najde souvislou plochu kolem kliknuti, prevede jeji obrys zpet na krivku
   a vlozi ji jako novou vypln pod obrysy.

Dalsi moznosti: Shift+klik meni obrys, Alt+klik naopak barvu z tvaru prevezme
jako aktualni, Ctrl+klik vynuti bod 3 i tam, kde by se jinak prebarvil cely
tvar - to je zpusob, jak vyplnit jen cast uz vyplnene plochy rozdelenou carou.

Vypln z bodu 3 se zasouva o kousek pod obrys, takze mezi vyplni a carou
nezustava svetla spara.

**Kdyz hranice netesni**, plocha by pretekla pres celou kresbu. To editor
pozna a misto vyplneni napise do stavoveho radku, ze oblast neni uzavrena.
Mezeru pak staci dokreslit, nebo cary spojit pres `Objekt / Napojit krivky`
(`Ctrl+J`). Je to stejna logika jako hlaseni o neuzavrene hranici v CADu.

## Historie operaci

Zalozka **Historie** vypisuje kazdou upravu jako jeden radek, zapsany
jako prikaz:

```text
12:31:34  obdelnik 256 256 448 336 --vypln #ffffff --obrys #000000 --tloustka 8
12:31:40  nuz "Krivka" --v 520,500 --krizeni 2 --zbylo 2
12:31:52  guma --tah 799,450 799,550 --prumer 50
12:32:01  popisek "KOCKA" --velikost 96 --odsazeni 60
```

Z historie je tedy videt nejen *ze* se neco stalo, ale i s cim a jak.
Zapis je zamerne psany jako prikaz, protoze stejnou podobu ma pozdeji
pouzivat prikazova radka a generovani - historie tak nebude jen popis,
ale i navod, jak kresbu zopakovat.

Pri ulozeni kresby se historie ulozi i vedle ni jako
`nazev.svg.historie.txt`. Tlacitkem v panelu jde ulozit kamkoliv jinam.

## Presne kresleni

- **Mrizka** (`Ctrl+G`) a **prichytavani k mrizce** (`F9`) - krok mrizky se meni
  v `Zobrazeni / Nastaveni kresby`.
- **Prichytavani k objektum** (`F3`) - chyta rohy, stredy a poloviny stran
  existujicich tvaru, prichyceny bod se ukaze oranzovym ctverecem.
- **Panel Rozmery a poloha** - X, Y, sirka, vyska a uhel jdou zapsat cislem.
- Sipky posunuji vyber o krok mrizky, se Shiftem po jednom pixelu. V uzlovem
  nastroji stejne sipky posunuji vybrany uzel.

Vsechna cisla i posuvniky se do kresby promitaji okamzite pri psani, ne az po
potvrzeni. Do historie se zapise az hotova uprava, takze tazeni posuvnikem
nebo dopsani cisla je jeden krok zpet, ne padesat.

## Obkresleni predlohy

Zalozka **Predloha**:

1. `Nacist obrazek…` nebo klik na nahled ve slozce (vychozi je `source_example`).
2. Obrazek se vlozi pod kresbu, ztlumeny a nekliknutelny.
3. Posuvnikem `Kryti` se da ztlumit vic nebo min, zaskrtavatkem schovat.

Predloha je jen pomucka. Do SVG se uklada pouze cesta k souboru v atributu
`pikto:reference`, samotny obrazek se do vystupu nezapisuje.

## Popisek pod obrazkem

Zalozka **Popisek** (`Ctrl+L`): napsany text se vlozi pod piktogram, vodorovne
na stred, a drzi se tam i pri zmene velikosti pisma. Da se nastavit font,
velikost, rez, barva a odsazeni od spodni hrany. Prepinac
`Prevest na velka pismena` odpovida stylu VOKS kartiček.

V kresbe je popisek oznaceny jako `pikto:role="caption"`, takze ho editor po
znovuotevreni souboru zase najde. Jinak je to bezny text a jde s nim pracovat
jako s kazdym jinym objektem.

## Sablony

Zalozka **Sablony** ma dve urovne:

1. **Sablony** - nahledy souboru, nahore se prepina kategorie.
2. **Dily** - dvojklik na sablonu ji rozbali na jednotlive pojmenovane
   objekty, kazdy s vlastnim nahledem. Tlacitkem `← Zpet na sablony` se
   vratite o uroven vys.

Vlozit jde oboji:

- **dvojklik** vlozi dil doprostred toho, co prave vidite, a rovnou ho vybere,
- **tazeni mysi** z panelu polozi sablonu nebo dil presne tam, kam ho pustite,
- tlacitko `Vlozit do kresby` pracuje s tim, co je v seznamu vybrane.

Takze obliceje se skladaji tak, ze se z `oblicej_dily` pretahne oko, druhe oko,
nos a usta rovnou na spravna mista. Cele piktogramy jako `kocka` nebo `auto`
ma smysl vkladat celé.

Kategorie je proste podslozka v `sablony/`:

| Kategorie | Obsah |
|---|---|
| `oblicej` | oci, zornice, oboci, nosy, usta, usi, vlasy, hlavy, krk, ramena |
| `postavy` | dospely a dite rozlozeni po dilech (hlava, telo, ruce, nohy) |
| `zvirata` | kocka, pes, ryba, ptak |
| `doprava` | auto, autobus, kolo, vlak, letadlo |
| `prostredi` | slunce, mrak, dum, strom, okno, stul, zidle, postel |
| `karty` | prazdne platno s popiskem, ramecek karty VOKS |
| `tvary` | obdelnik, elipsa, trojuhelnik, srdce, krivky |

Dily maji smysluplne nazvy, takze se v zalozce `Objekty` da rychle najit,
co je co. Z dilu se piktogram sklada tak, ze se sablona vlozi do kresby,
nepotrebne casti se smazou a zbytek se posune a prebarvi.

Vlastni sablona = jakekoliv SVG ulozene do `sablony/`. Kdyz se da do
podslozky, zalozi tim novou kategorii; `Obnovit seznam` ji nacte.

`Vlozit do kresby` prida tvary do rozdelane prace, `Nova kresba ze sablony`
zalozi novy dokument.

## Ukladani

- **SVG** je nativni format (`Ctrl+S`). Soubor otevre i prohlizec nebo Inkscape.
- **PNG** se da vyexportovat v `Soubor / Export do PNG…` s volitelnym nasobkem
  velikosti; predloha se do exportu nezapocitava.
- WMF/EMF zatim neni. Slo by doplnit pres Inkscape CLI, ktery ale na tomhle
  pocitaci zatim neni nainstalovany.

## Struktura projektu

```text
vector_graphics_editor/
  main.py               spousteci skript
  build_exe.ps1         sestaveni .exe
  PiktoEdit.spec        nastaveni PyInstalleru
  dist/PiktoEdit.exe    hotovy program
  tests/                zkousky, spousti je spustit_testy.ps1
  piktoedit/
    app.py              vytvoreni QApplication
    mainwindow.py       okno, menu, panely, prace se soubory
    canvas.py           scena s mrizkou, pohled, uchyty, prichytavani, guma
    tools.py            kreslici a editacni nastroje
    nodes.py            uzly krivek, hladke krivky, napojeni, orezani, rezani
    regionfill.py       hledani uzavrene plochy pro kyblik
    preview.py          nahledy sablon
    journal.py          viditelna historie operaci
    paths.py            cesty ke slozkam, i uvnitr .exe
    shapes.py           objekty na platne a jejich prevod na SVG
    svgio.py            cteni a zapis SVG, transformace, viewBox
    pathdata.py         parser a zapis atributu d
    style.py            vypln, obrys, sirka cary, pruhlednost
    panels.py           postranni panely
    undo.py             zpet a znovu pres snimky dokumentu
  sablony/              sablony ve formatu SVG
  piktogramy/           vychozi slozka pro ulozene kresby
  source_example/       predlohy k obkresleni
```

## Poznamky k SVG

Zapisuji se bezne elementy `rect`, `ellipse`, `line`, `path` a `text`, takze
vysledek je citelny i mimo editor. Navic editor uklada nekolik atributu ve
vlastnim jmennem prostoru, ktere ostatni programy ignoruji:

| Atribut | Vyznam |
|---|---|
| `pikto:name` | nazev objektu v seznamu |
| `pikto:kind` | typ tvaru |
| `pikto:role` | `background` pro pozadi, `caption` pro popisek |
| `pikto:grid` | krok mrizky |
| `pikto:reference` | cesta k predloze |

Pri otevirani ciziho SVG editor rozumi i `circle`, `polyline`, `polygon`,
skupinam `g`, atributu `viewBox` a transformacim `translate`, `rotate`,
`scale`, `matrix`, `skewX`, `skewY`. Zkosene nebo nerovnomerne zvetsene tvary
se prevedou na krivku, aby zustal zachovany tvar.
