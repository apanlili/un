# Data files the engine reads

Generated from the code, against `/mnt/user-data/uploads`.

**28 indices registered · 17 with a verified calculation structure · 16 reproducing their published score**


## How a file is used

Each index can have two files, and they do different jobs.

- **Metadata** — one row per indicator per country: the year, the source, whether the figure was reported or estimated. This is what the country-level findings are computed from.
- **Calculation** — the publisher's own workbook, with the scores and the arithmetic. This is what the construction findings come from, and what the self-check reproduces.

An index with only metadata is still assessed, but its construction criteria read `awaiting`. An index with only a calculation file has no country-level findings.


## Registered indices

| Index | Metadata file | Calculation file | Verified? |
|---|---|---|---|
| B-Ready | `—` | `05012025_simulator_b-ready_2025.xlsx` | yes — 101/101 rows |
| B2C E-Commerce Index | `B2C_E-Commerce_Index.xlsx` | `—` | not verified |
| Digital Accessibility Rights Evaluation | `Digital_Accessibility_Right_Evaluation.xlsx` | `—` | not verified |
| Doing Business Index | `Doing_Business_Index.xlsx` | `—` | not verified |
| E-Participation Index | `E-Participation_Index.xlsx` | `—` | not verified |
| FDI Restrictiveness Index | `FDI_Restrictiveness_Index.xlsx` | `—` | not verified |
| Gender Development Index | `Gender_Development_Index.xlsx` | `0605205_simulator__Gender_Development_Index_2025.xlsx` | yes — 184/184 rows |
| Global Competitiveness Index | `Global_Competitveness_Index.xlsx` | `—` | not verified |
| Global Gender Gap Index | `—` | `20250804_Gender_Gap_Simulator_2025.xlsx` | yes — 148/148 rows |
| Global Hunger Index | `—` | `Global_Hunger_Index_simulator_2025.xlsx` | yes — 123/123 rows |
| Global Innovation Index | `Global_Innovation_Index.xlsx` | `simulator2025-Global_Innovation_Index_2025.xlsx` | yes — 139/139 rows |
| Global Knowledge Index | `Global_Knowledge_Index.xlsx` | `Adjusted_Global_Knowledge_Index_2024.xlsx` | partly (resolution only) |
| GovTech Maturity Index | `GovTech_Maturity_Index.xlsx` | `World_Bank_-GovTech_2022.xlsx` | yes — 197/197 rows |
| Government AI Readiness Index | `—` | `OI_Government_AI_Readiness_2024_v11022025.xlsx` | yes — 188/188 rows |
| Human Capital Index | `Human_Capital_Index.xlsx` | `20230330_simulator_Human_Capital_Index.xlsx` | yes — 174/174 rows |
| Human Development Index | `Human_Development_Index.xlsx` | `06052025_Simulator_Human_Development_Index_2025.xlsx` | yes — 193/193 rows |
| ICT Development Index | `ICT_Development_Index.xlsx` | `—` | not verified |
| Inclusive Internet Index | `Inclusive_Internet_Index.xlsx` | `—` | not verified |
| Logistics Performance Index | `logistic_performance_index.xlsx` | `—` | not verified |
| Network Readiness Index | `Network_Readiness_Index.xlsx` | `09022025_simulator_Network_Readiness_Index_2025.xlsx` | yes — 127/127 rows |
| Open Data Inventory Index | `Open_Data_Inventory_Index.xlsx` | `—` | not verified |
| Open Data Policies | `Open_Data_Policies.xlsx` | `—` | not verified |
| Planetary-adjusted HDI | `Planetary_Adjusted_Human_Development_Index.xlsx` | `06052025_simulator_Planetary_Pressures_adjusted-_Human_Development_Index_2025.xlsx` | yes — 156/156 rows |
| Sustainable Development Index | `Sustainable_Development_Index.xlsx` | `30062026_simulator_sustainable_development_index_2026.xlsx` | yes — 163/163 rows |
| Travel & Tourism Development Index | `Travel_and_Tourism_Development_Index.xlsx` | `04062024_simulator_Travel_and_Tourism_2024.xlsx` | yes — 119/119 rows |
| Women, Business and the Law | `Women_Business_and_the_Law_2_0.xlsx` | `03032026__Women_Business_and_the_Law_2026_2_0.xlsx` | yes — 130/130 rows |
| Women, Peace and Security Index | `Women_Peace_and_Security_Index.xlsx` | `07012025_simulator_Women_Peace_and_Security_2025.xlsx` | yes — 181/181 rows |
| World Press Freedom Index | `world_press_freedom.xlsx` | `18052026_simulator_world_Press_Freedom_Index_2026.xlsx` | yes — 179/180 rows |

## Files present but not read

Every workbook in the folder that no index uses, with the reason.

| File | Why not |
|---|---|
| `01032026_Women_Business_and_the_Law1_0.xlsx` | superseded edition, or not yet registered |
| `06052025_simulator_world_Press_Freedom_Index_2025.xlsx` | superseded edition, or not yet registered |
| `14072025_simulator_sustainable_development_index_2025.xlsx` | superseded edition, or not yet registered |
| `20241112_simulator_EGDI-2024.xlsx` | superseded edition, or not yet registered |
| `2025_Government_AI_Readiness_Index_Indicator-Level_data.xlsx` | superseded edition, or not yet registered |
| `E-Government_Development_Index.xlsx` | superseded edition, or not yet registered |
| `Finanacial_Inclusiveness_Index_.xlsx` | superseded edition, or not yet registered |
| `Financial_Inclusiveness_Index_2025_Final_to_Share.xlsx` | superseded edition, or not yet registered |
| `Global_Knowledge_Index_2022_v27052024.xlsx` | superseded edition, or not yet registered |
| `Global_development_index_-_2023_database_for_ISPAR__10-10-2025_.xlsx` | ESCWA's own index — out of scope, the tool assesses external indices |
| `Index_Suitability_Framework.xlsx` | output of this tool, not an input |
| `LNOB_Matrix_Dec_2025.xlsx` | ESCWA's own index — out of scope |
| `Public_Administartion_Index.xlsx` | ESCWA's own composite — out of scope |
| `Women_Business_and_the_Law_1_0.xlsx` | superseded edition, or not yet registered |

## Checksums

So a later run can be compared against the same inputs. Verify with `sha256sum <file>`.

| File | SHA-256 (first 16) | Used by |
|---|---|---|
| `03032026__Women_Business_and_the_Law_2026_2_0.xlsx` | `87357bbe9ae26f1a` | Women, Business and the Law (calculation) |
| `04062024_simulator_Travel_and_Tourism_2024.xlsx` | `d8003786eee43f94` | Travel & Tourism Development Index (calculation) |
| `05012025_simulator_b-ready_2025.xlsx` | `1c49504931c8b6f9` | B-Ready (calculation) |
| `06052025_Simulator_Human_Development_Index_2025.xlsx` | `d72d81ce61193406` | Human Development Index (calculation) |
| `06052025_simulator_Planetary_Pressures_adjusted-_Human_Development_Index_2025.xlsx` | `3185bb63b13f834c` | Planetary-adjusted HDI (calculation) |
| `0605205_simulator__Gender_Development_Index_2025.xlsx` | `5a4c9c76b76b7746` | Gender Development Index (calculation) |
| `07012025_simulator_Women_Peace_and_Security_2025.xlsx` | `5ac6c96966d87c51` | Women, Peace and Security Index (calculation) |
| `09022025_simulator_Network_Readiness_Index_2025.xlsx` | `ea0202406b32343a` | Network Readiness Index (calculation) |
| `18052026_simulator_world_Press_Freedom_Index_2026.xlsx` | `4151062500011b5b` | World Press Freedom Index (calculation) |
| `20230330_simulator_Human_Capital_Index.xlsx` | `7077f732afda94e5` | Human Capital Index (calculation) |
| `20250804_Gender_Gap_Simulator_2025.xlsx` | `c83a4bda7dde4c3e` | Global Gender Gap Index (calculation) |
| `30062026_simulator_sustainable_development_index_2026.xlsx` | `369d5ea0d679d1ef` | Sustainable Development Index (calculation) |
| `Adjusted_Global_Knowledge_Index_2024.xlsx` | `ba4a4e4222d10f02` | Global Knowledge Index (calculation) |
| `B2C_E-Commerce_Index.xlsx` | `4f12eb29283dee65` | B2C E-Commerce Index (metadata) |
| `Digital_Accessibility_Right_Evaluation.xlsx` | `47fef2ca4c97d330` | Digital Accessibility Rights Evaluation (metadata) |
| `Doing_Business_Index.xlsx` | `eb0df9369e54ce88` | Doing Business Index (metadata) |
| `E-Participation_Index.xlsx` | `cb13637d6198ea61` | E-Participation Index (metadata) |
| `FDI_Restrictiveness_Index.xlsx` | `c35505c3aab9c7cd` | FDI Restrictiveness Index (metadata) |
| `Gender_Development_Index.xlsx` | `dd253f86acd2b449` | Gender Development Index (metadata) |
| `Global_Competitveness_Index.xlsx` | `eb69115383642bf4` | Global Competitiveness Index (metadata) |
| `Global_Hunger_Index_simulator_2025.xlsx` | `ec51475737fc7b10` | Global Hunger Index (calculation) |
| `Global_Innovation_Index.xlsx` | `533750734788da81` | Global Innovation Index (metadata) |
| `Global_Knowledge_Index.xlsx` | `f333202100b4aca3` | Global Knowledge Index (metadata) |
| `GovTech_Maturity_Index.xlsx` | `e1d1a13c7ef8cab3` | GovTech Maturity Index (metadata) |
| `Human_Capital_Index.xlsx` | `d5f834d2f4448e0f` | Human Capital Index (metadata) |
| `Human_Development_Index.xlsx` | `4aaad6929a460a67` | Human Development Index (metadata) |
| `ICT_Development_Index.xlsx` | `905c72b9e7184440` | ICT Development Index (metadata) |
| `Inclusive_Internet_Index.xlsx` | `8760258b5ce49f69` | Inclusive Internet Index (metadata) |
| `Network_Readiness_Index.xlsx` | `7a7907689540c390` | Network Readiness Index (metadata) |
| `OI_Government_AI_Readiness_2024_v11022025.xlsx` | `08615050b37b8ae8` | Government AI Readiness Index (calculation) |
| `Open_Data_Inventory_Index.xlsx` | `6eace61448b84bf5` | Open Data Inventory Index (metadata) |
| `Open_Data_Policies.xlsx` | `f79b4809472f3bfd` | Open Data Policies (metadata) |
| `Planetary_Adjusted_Human_Development_Index.xlsx` | `b91a7b7968dc208a` | Planetary-adjusted HDI (metadata) |
| `Sustainable_Development_Index.xlsx` | `7fd46c069f780be2` | Sustainable Development Index (metadata) |
| `Travel_and_Tourism_Development_Index.xlsx` | `1e52214547521deb` | Travel & Tourism Development Index (metadata) |
| `Women_Business_and_the_Law_2_0.xlsx` | `ed889364c0bb8efb` | Women, Business and the Law (metadata) |
| `Women_Peace_and_Security_Index.xlsx` | `fdacb26aa880c70c` | Women, Peace and Security Index (metadata) |
| `World_Bank_-GovTech_2022.xlsx` | `d5fcccdebb7e4619` | GovTech Maturity Index (calculation) |
| `logistic_performance_index.xlsx` | `9736d65f3f5e0f85` | Logistics Performance Index (metadata) |
| `simulator2025-Global_Innovation_Index_2025.xlsx` | `622db1d7eaa830a0` | Global Innovation Index (calculation) |
| `world_press_freedom.xlsx` | `a239a39f200eebf4` | World Press Freedom Index (metadata) |

## Known gaps in the current files

These are data problems, not code problems. Each was found by comparing the metadata against the publisher's own file.

**GovTech — seven indicators missing.** The publisher's 2022 sheet has 201 indicator columns; the metadata has 194 rows per country, identically for all 22 countries. The missing eight (net seven, one possibly reworded) sit in adjacent columns, which points to one skipped block during transcription. See `govtech_gap_diagnosis.md`.

**Network Readiness Index — no countries.** The `Arab Countries` column is empty for all 52 rows, so NRI contributes no country-level findings at all.

**Three indices have no files.** WJP Rule of Law, BTI and any newer GovTech edition are not in the folder. Adding an index is one line in `REGISTRY` in `isf/engine_core/corpus.py`, but the file has to exist first.


## Adding an index

1. Put the metadata file (and the calculation file, if there is one) in the data folder.
2. Add one line to `REGISTRY` in `isf/engine_core/corpus.py`:

   ```python
   "WJP Rule of Law": ("Rule_of_Law_metadata.xlsx", "Rule_of_Law_calc.xlsx"),
   ```

3. Run `python -m isf.build_export`. The country-level and construction findings compute immediately. The five read-from-methodology criteria show `awaiting` until someone reads the publisher's documentation — the tool will not invent them.
4. Only once the self-check reproduces the published score, add a `VERIFIED_STRUCTURES` entry. That entry is a claim the guard checks on every run.
