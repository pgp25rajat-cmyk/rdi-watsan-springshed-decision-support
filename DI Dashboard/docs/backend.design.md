# Backend design

The canonical contract is [backend.design.packet.json](backend.design.packet.json). This separate local module never calls or writes to the original application at the repository root. Python standard-library HTTP and SQLite avoid a deployment burden for one computer. Authentication is omitted as requested; the service binds to loopback only.

The database holds sites, versioned setup, immutable submitted visits and corrections, drafts, evidence records, file metadata and environmental cache. Spring and handpump coordinates, measurements and response comparisons remain distinct. Additional linked handpumps retain their own identity and status. Setup is separate from recurring field visits.

`rules.py` validates portal fields and converts readings. `assessment.py` contains the independent comparisons, 11-indicator register and missing-data rules. `store.py` owns transactions and history. `weather.py` owns approved coordinate requests and cache lineage. `server.py` owns transport and file storage. UI modules separate forms, controls, maps, evidence and views. These modules can sit behind another API later; shared deployment would need authenticated roles and managed persistence.

Three readings receive equal weight. Comparable changes require matching season, point, procedure and distinct exact dates. Unknowns never become zeros. Source estimates and date windows remain useful context but cannot establish repeat measured change. Checked-line percentages show their denominator. There is no composite DI index or causal allocation to DI. Accounts of village life keep asset, source and date without inventing short-term statistics.

Initial records were manually reviewed against supplied forms and reports. The declarative intake retains original bytes, checksums, page/excerpt, date uncertainty and conflicts; a reviewed field entry can enter the assessment, while the file itself cannot. Portal uploads have no extraction path. Binary upload supports 25 MB files, SHA-256 retry deduplication and a supporting-file evidence entry. A photo upload can replace a site cover without losing the original file.

Open-Meteo rainfall uses pump GPS first and labels any spring-location proxy. Failed refreshes retain the cache. OpenStreetMap tiles are a separately approved browser request; local site labels are never sent. Both integrations expose unavailable states and cannot prove groundwater connection or DI causation.

Back up the SQLite snapshot, runtime/attachments, data/00_raw and public/photos together. CSV/XLSX review registers and JSON exports support handover. Source files and superseded records stay available for review.

## Public branch packaging

This branch distributes code only. Initial field records, original files, photographs, manifests, intake scripts and live runtime data remain local. A fresh checkout creates an empty database. The full source-review workflow described above is an optional local capability; no source dataset is bundled.
