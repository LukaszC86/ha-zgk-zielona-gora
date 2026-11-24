<img src="icon.png" alt="" width="96" align="right">

# ZGK Zielona Góra – odbiór odpadów

Integracja Home Assistant z terminami odbioru odpadów z wyszukiwarki
[ZGK Zielona Góra](https://www.zgk.net.pl/odbior-odpadow). Pokazuje **wszystkie**
odbiory, także te, które ZGK podaje tylko jako dzień tygodnia (zwykle odpady
zmieszane i BIO, np. „środa”).

## Co dostajesz

Dla każdego adresu:

| Encja | Opis |
|---|---|
| `calendar.…_odpady_zmieszane`, `…_odpady_selektywne`, `…_odpady_bio`, `…_gabaryty` | osobny kalendarz dla każdego rodzaju; w panelu Kalendarz każdy ma swój kolor i można go odznaczyć |
| `calendar.…_wszystkie_odbiory` | wszystkie odbiory w jednym kalendarzu (domyślnie wyłączony, włączysz go w ustawieniach encji) |
| `sensor.…_odpady_zmieszane`, `…_selektywne`, `…_bio`, `…_gabaryty` | data najbliższego odbioru; atrybuty `dni`, `wyliczony`, `swieto`, `harmonogram`, `kolejne` |
| `sensor.…_najblizszy_odbior` | najbliższy dzień z jakimkolwiek odbiorem; atrybuty `dni`, `rodzaje` |
| `sensor.…_komunikat_zgk` | ostatni komunikat ZGK o zmianach w harmonogramie (z linkiem) |

Rodzaje, których nie potrzebujesz (np. BIO, jeśli kompostujesz), odznacz w opcjach
integracji. Ich kalendarz i sensor znikną, a „Najbliższy odbiór” przestanie je brać pod uwagę.

## Jak czytane są dane ZGK

| Zapis w ZGK | Co robi integracja |
|---|---|
| lista dat `13.01.2026, 27.01.2026, …` | bierze daty wprost |
| dzień tygodnia `środa`, `poniedziałek, piątek` (także literówki typu `czawartek`) | wylicza odbiór co tydzień na N tygodni naprzód (domyślnie 26) |
| `sobota co dwa tygodnie, zgodnie z harmonogramem…` | używa dat odpadów zmieszanych z tego adresu |
| `BRAK`, `-`, puste | brak odbioru |
| data z nieprawdopodobnym rokiem (np. `29.12.2034`) | pomija |
| data poza kolejnością (np. `01.11.2026` między 17.11 a 15.12) | zostawia, oznacza ⚠ w opisie wydarzenia |

### Święta

ZGK przy dniach wolnych zmienia harmonogram zmieszanych i BIO tylko dla części ulic
i ogłasza to w [aktualnościach](https://www.zgk.net.pl/aktualnosci) (PDF z listą ulic).
Dla odbiorów **wyliczonych** z dnia tygodnia, które wypadają w dzień wolny, możesz
w opcjach wybrać:

- **Zostaw i oznacz ⚠** (domyślnie) – wydarzenie „⚠ Odpady zmieszane (święto)” z linkiem do komunikatu,
- **Przesuń na następny dzień roboczy**,
- **Pomiń**.

Daty podane przez ZGK wprost nie są przesuwane.

### Ręczne zmiany

W opcjach integracji (Ustawienia → Urządzenia i usługi → ZGK → Konfiguruj), jedna zmiana w linii:

```
11.11.2026 > 12.11.2026            # przesuń wszystkie odbiory z tego dnia
zmieszane 11.11.2026 > 12.11.2026  # tylko jeden rodzaj
bio 11.11.2026 > brak              # odwołaj
+ 14.11.2026 gabaryty              # dodaj
selektywne 01.11.2026 > 01.12.2026 # popraw literówkę ZGK
```

Rodzaje: `zmieszane`, `selektywne`, `bio`, `gabaryty`.

## Instalacja

### HACS (własne repozytorium)

1. HACS → ⋮ → *Custom repositories* → adres tego repozytorium, typ *Integration*.
2. Zainstaluj „ZGK Zielona Góra – odbiór odpadów” i zrestartuj Home Assistant.

### Ręcznie

Skopiuj `custom_components/zgk_zielona_gora` do katalogu `custom_components`
w konfiguracji Home Assistant i zrestartuj.

### Konfiguracja

Ustawienia → Urządzenia i usługi → Dodaj integrację → „ZGK Zielona Góra”. Wpisz
adres tak, jak w wyszukiwarce ZGK (np. `AKADEMICKA 1`) albo samą ulicę i wybierz
budynek z listy. Można dodać kilka adresów.

## Przykład automatyzacji

Powiadomienie wieczorem dzień przed odbiorem:

```yaml
automation:
  - alias: Wystaw śmieci
    triggers:
      - trigger: time
        at: "19:00:00"
    conditions:
      - condition: template
        value_template: "{{ state_attr('sensor.odbior_odpadow_akademicka_1_najblizszy_odbior', 'dni') == 1 }}"
    actions:
      - action: notify.notify
        data:
          title: Jutro odbiór odpadów
          message: "{{ state_attr('sensor.odbior_odpadow_akademicka_1_najblizszy_odbior', 'rodzaje') | join(', ') }}"
```

## Testy

```
pip install -r requirements_test.txt
pytest
```

Integracja nie jest powiązana z ZGK Sp. z o.o.; korzysta z publicznej wyszukiwarki na ich stronie.
