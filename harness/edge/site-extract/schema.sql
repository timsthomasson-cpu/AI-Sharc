-- Database objects used by the site-extract edge function (test project, 2026-11-24).
-- Migrations: tx_place_reference_tables, site_extractions, extraction_zips_function, apply_extracted_service_areas.
-- Reference data: harness/reference/tx_zips.csv and tx_place_names.csv (loaded into tx_zips / tx_place_names).
-- Deployed function imports extract.ts from this repo pinned by commit; see the import line in the deployed index.ts.

-- site_extractions: one row per firm per extraction run (see the migration for all columns).
--   sa_places / sa_counties / sa_zips_explicit: service area as written on the site, with page URL and how it was found
--   address_*: address found on the site (JSON-LD first, then page text)
--   insurance_* / epa_* / tacl_licences / financing_* / rebates_* / free_estimate_*: advice rows, wording + URL kept
--   estimate_includes: {permits|old_unit_removal|thermostat|ductwork: {wording, url}} for C4.3 notes

-- extraction_zips(extraction_id) -> text[]: place names to ZIPs (postal city, then alias, then other accepted
--   city names), counties to all their ZIPs, plus Texas ZIPs written out on the page.

-- extraction_queue + dispatch_extractions(run_label, batch): same pattern as snapshot_queue / dispatch_snapshots.

-- apply_extracted_service_areas(run_label): writes firms.service_area_* from the latest extraction, setting
--   service_area_source to 'website service-area page', 'website (other pages)' or 'website: none stated'.
--   Never overwrites a service area checked another way (hand-checked firms keep theirs).

-- Example run:
-- insert into extraction_queue (firm_id, run_label) select firm_id, 'extract-2026-11-24' from snapshot_queue where run_label = 'full-2026-11-23';
-- select cron.schedule('extract-2026-11-24', '* * * * *', $$ select case when exists (select 1 from public.extraction_queue
--   where run_label = 'extract-2026-11-24' and status in ('pending','dispatched')) then public.dispatch_extractions('extract-2026-11-24', 100)
--   else (select 0 from cron.unschedule('extract-2026-11-24')) end; $$);
-- select public.apply_extracted_service_areas('extract-2026-11-24');

-- 2026-11-25: ZIP reach for choosing shopping-query ZIPs.
-- tx_zips gained lat/lng (harness/reference/tx_zip_coords.csv); miles(lat1,lng1,lat2,lng2) = great-circle miles.
-- firm_zip_basis (view): website service-area ZIPs kept only within 100 miles of the firm's home (ZIP on file, website
--   address, home-town centre, else the median point of its own list); 1-350 ZIPs left -> 'website', otherwise the
--   home-town proxy (every ZIP of its postal town, else its own ZIP).
-- zip_reach (table) + build_zip_reach_v2(): companies per ZIP, companies counted from a website area, unique ZIPs and
--   2010 population reached by those companies. Built one ZIP at a time in memory; build_zip_reach() (v1) needs large
--   temp files and ran the test database out of disk on 2026-11-25 - do not use it.
