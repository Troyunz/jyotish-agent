# Ashtakavarga - bindu strength and how to judge transits with it

Ashtakavarga ("eight-fold division") is the classical system for measuring how much benefic
support each sign and bhava receives. It answers a question that house position alone cannot:
*this transit looks bad on paper - will it actually bite?* A planet crossing a sign with high
bindus gives cleaner results than the same planet crossing a weak sign. This is the standard
reason why two people with similar charts experience the same transit very differently.

## How the points are generated

Seven grahas (Sun, Moon, Mars, Mercury, Jupiter, Venus, Saturn) each cast benefic points
("bindus") into specific signs, counted from **eight reference points**: the seven grahas plus
the Lagna. Each planet has its own classical table of which houses (counted from each reference
point) receive a bindu. The result per planet is its **Bhinnashtakavarga (BAV)** - a grid of 0 to
8 points per sign. Adding all seven BAV grids gives the **Sarvashtakavarga (SAV)** - 0 to 56
points per sign.

Classical totals, which are a useful correctness check on any implementation:

| Planet | Total bindus in its own BAV |
|---|---|
| Sun | 48 |
| Moon | 49 |
| Mars | 39 |
| Mercury | 54 |
| Jupiter | 56 |
| Venus | 52 |
| Saturn | 39 |
| **SAV (all seven)** | **337** |

If a program produces anything other than 337 in the SAV, its tables have an error somewhere.
(Different published editions word a few rows differently, so minor per-planet variation exists
between sources; the totals are the invariant to check.)

## Reading the numbers

The tool computes both BAV (per planet, per sign) and SAV (per sign), and reports them by bhava
using whole-sign houses. Grade the ground before interpreting a transit:

| SAV bindus in the sign/bhava | Reading |
|---|---|
| 28 or more | strong support - the house delivers well, transits here are productive |
| 25-27 | good - generally supportive |
| 22-24 | average - mixed, results depend entirely on the dasha and the transiting planet |
| below 22 | weak / friction - transits here test the house; effort and remedies are needed |

For a specific transit, read **the transiting planet's own BAV** first, then the SAV:

- **High BAV for that planet + high SAV** - the transit delivers its promise cleanly.
- **High BAV for that planet, low SAV** - the planet itself means well but the house as a whole is
  under-supported; expect results with effort.
- **Low BAV for that planet** - the transit is weak in effect. Two useful principles: a planet
  transiting a sign with **zero or very few bindus** tends to produce little (or obstructive)
  results; and the transit becomes more reliable when it crosses a sign where the **planet's own
  natal lord** is strong.
- Always check whether the sign in question also holds bindus for the planet's enemies - SAV
  aggregates everything, so the BAV tells you *whose* support is present.

## Combining Ashtakavarga with dasha and gochara

The classical order of judgement does not change: **dasha gives permission, transit triggers, and
Ashtakavarga grades the ground**. Practical sequence:

1. Confirm from the dasha that the matter is promised at all (a marriage dasha, a career dasha).
2. Identify the relevant transit (Saturn or Jupiter crossing the 7th, the 10th, the natal Moon).
3. Check the SAV bindus of the sign being crossed, and the transiting planet's own BAV.
4. Only then narrate the outcome - strong ground, clean delivery; weak ground, effortful and partial.

A Jupiter transit through a 30-bindu sign in a supportive dasha is one of the most reliable
"expansion windows" the classical system offers. Saturn crossing a sign with under 20 bindus, in
the antardasha of the 6th or 8th lord, is the configuration the texts describe as a genuinely
testing period - and even then the remedy is patience, discipline and service, not fear.

## Divisions within a sign - kakshya

Each sign is divided into eight **kakshyas** of 3°45', each owned by one of the seven grahas plus
the Lagna, in the order Saturn, Jupiter, Mars, Sun, Venus, Mercury, Moon, Lagna (this is the
standard Ashtakavarga order; some editions of the texts vary the sequence - state the convention
when you use it, and never mix two conventions in one judgment). When a transiting planet enters a
kakshya whose lord has placed a bindu in that sign in the planet's own BAV, the result is
favourable; if that kakshya has no bindu, the period of passage is unfavourable. Kakshya analysis
is how electional work (muhurta) and precise transit timing are refined - it needs an accurate
birth time and an accurate ephemeris, so do not attempt it when the birth time is uncertain.

## Sodhya pinda and reduction

The classical texts further reduce the grids into **Sodhya Pinda** (the planet's "purified" value
after trikona and ekadhipatya reductions), used for fine-grained transit judgement and for
comparing two charts. It is an advanced refinement; if it has not been computed, do not invent it.

## Ashtakavarga in the divisional charts

The classical texts also prescribe Ashtakavarga in the vargas (especially the D9 and D10) for
judging the strength of a planet in the specific life area the varga governs. If only the D1
Ashtakavarga has been computed, say so - do not present Rashi Ashtakavarga results as though they
were varga-specific.

## Honest limitations

- Ashtakavarga measures *relative support*, not events. It never overrides the dasha.
- Published tables differ in a few rows between editions (for example, certain rows for the Moon
  and Venus). Any implementation should be validated by checking the classical totals, and the
  planetary BAV totals reported alongside the grid.
- A low-bindu transit is not a curse; it means the house in question asks for conscious effort,
  patience and remedial discipline during that passage.
