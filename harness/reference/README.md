# Reference data

- `tx_zips.csv` — Texas residential ZIP codes (ZCTAs with population > 0) with postal city, county and 2010 Census population. Source: the open uszipcode database (github.com/MacHu-GWU/uszipcode-project), simple_db 1.0.1.
- `tx_place_names.csv` — place names that map to those ZIPs:
  - `city`: the ZIP's postal city
  - `common`: other city names the Postal Service accepts for the ZIP
  - `county`: the county name without "County"
  - `alias`: unincorporated places and villages with no postal city of their own, mapped to the postal city they sit in (for example Cinco Ranch → Katy, Four Corners → Houston)

Used to turn the towns and counties a firm's website names into ZIP codes. Loaded into the `tx_zips` and `tx_place_names` tables. 2020 Census population needs census.gov access or a Census API key and can replace the 2010 figures later.
- `tx_zip_coords.csv` — latitude and longitude of each ZIP centre (same source), used to drop service-area ZIPs more than 100 miles from a firm's home.
